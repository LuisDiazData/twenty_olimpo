"""
Agente 4 — Identificación del agente y asignación automática.

Endpoint: POST /api/v1/agentes/asignacion

Cierra el pipeline de procesamiento:
  1. Lee datos consolidados de tramites_pipeline (Supabase)
  2. Verifica confianza ≥ 75, no duplicado, datos mínimos presentes
  3. Búsqueda en cascada del agente en Twenty:
       email exacto → CUA → nombre fuzzy (LLM, umbral 85%)
  4. Consulta analista activo hoy (con sustitución por cobertura)
  5. Crea el Trámite en Twenty CRM
  6. Genera folio interno y calcula SLA
  7. Registra en historial_asignaciones y actualiza tramites_pipeline

GraphQL endpoint real de Twenty: /graphql  (no /api — ese retorna 404)
Todos los campos verificados via introspección real antes de crear mutaciones.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import litellm
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

class MatchAgente(BaseModel):
    company_id: Optional[str] = Field(None, description="uuid si supera 85% de similitud, o null")
    company_name: Optional[str] = Field(None, description="string o null")
    confidence: int = Field(0, description="0-100")

from supabase_client import supabase as _sb

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Config ─────────────────────────────────────────────────────────────────────

TWENTY_API_URL = os.getenv("TWENTY_API_URL", "http://localhost:3000")
TWENTY_API_KEY = os.getenv("TWENTY_API_KEY", "")
LLM_MODEL      = os.getenv("LLM_MODEL", "openai/gpt-4o")

_TWENTY_HEADERS = {
    "Authorization": f"Bearer {TWENTY_API_KEY}",
    "Content-Type": "application/json",
}

# ── Enum / value normalization ─────────────────────────────────────────────────

# Maps free-text ramo values (from LLM Agente 1) → Twenty TramiteRamoEnum
_RAMO_MAP: dict[str, str] = {
    "vida":     "VIDA",
    "gmm":      "GMM",
    "gastos médicos": "GMM",
    "gastos medicos": "GMM",
    "autos":    "AUTOS",
    "auto":     "AUTOS",
    "automóvil": "AUTOS",
    "automovil": "AUTOS",
    "pyme":     "PYME",
    "pymes":    "PYME",
    "daños":    "DANOS",
    "danos":    "DANOS",
    "daños materiales": "DANOS",
    "siniestros": None,   # no es ramo sino tipo
}

_TIPO_MAP: dict[str, str] = {
    "nueva_poliza":      "NUEVA_POLIZA",
    "nueva poliza":      "NUEVA_POLIZA",
    "nueva póliza":      "NUEVA_POLIZA",
    "endoso":            "ENDOSO",
    "renovacion":        "RENOVACION",
    "renovación":        "RENOVACION",
    "cancelacion":       "CANCELACION",
    "cancelación":       "CANCELACION",
    "siniestro":         "SINIESTRO",
    "cotizacion_pyme":   "COTIZACION_PYME",
    "cotizacion pyme":   "COTIZACION_PYME",
    "cotización pyme":   "COTIZACION_PYME",
    "reembolso":         "SINIESTRO",    # closest
    "reclamacion":       "SINIESTRO",
    "reclamación":       "SINIESTRO",
    "cotizacion":        "COTIZACION_PYME",
}

# SLA días hábiles por ramo
_SLA_DIAS: dict[str, int] = {
    "VIDA":  5,
    "GMM":   3,
    "AUTOS": 4,
    "PYME":  7,
    "DANOS": 5,
}


def _normalizar_ramo(raw: str | None) -> str | None:
    if not raw:
        return None
    key = _strip_accents(raw.strip().lower())
    # Direct lookup
    for k, v in _RAMO_MAP.items():
        if key == _strip_accents(k):
            return v
    # Partial match
    for k, v in _RAMO_MAP.items():
        if _strip_accents(k) in key:
            return v
    return None


def _normalizar_tipo(raw: str | None) -> str | None:
    if not raw:
        return None
    key = _strip_accents(raw.strip().lower())
    for k, v in _TIPO_MAP.items():
        if key == _strip_accents(k):
            return v
    for k, v in _TIPO_MAP.items():
        if _strip_accents(k) in key:
            return v
    return None


def _strip_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _add_business_days(start: date, days: int) -> date:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


# ── GraphQL helper ─────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _do_request_gql(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{TWENTY_API_URL}/graphql",
            json=payload,
            headers=_TWENTY_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()

async def _gql(query: str, variables: dict | None = None, retry_flag: bool = True) -> dict:
    """
    Execute a GraphQL query/mutation against Twenty /graphql endpoint.
    Uses Tenacity for exponential backoff retries.
    Raises ValueError on GraphQL errors[], HTTPException on network failure.
    """
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        if retry_flag:
            body = await _do_request_gql(payload)
        else:
            # Try only once manually if requested
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(f"{TWENTY_API_URL}/graphql", json=payload, headers=_TWENTY_HEADERS)
                resp.raise_for_status()
                body = resp.json()
    except Exception as exc:
        logger.warning(f"Twenty API failed after retries: {exc}")
        raise HTTPException(503, f"Twenty API no disponible: {exc}") from exc

    if "errors" in body and body["errors"]:
        # Log full error for debugging
        logger.error(f"GQL errors for query snippet={query[:120]!r}: {body['errors']}")
        raise ValueError(f"GraphQL errors: {body['errors']}")

    return body.get("data", {})


# ── Folio generation ───────────────────────────────────────────────────────────

async def _generar_folio(year: int | None = None) -> str:
    """
    Generate next sequential folio: TRM-{YYYY}-{NNNNN}.
    Queries existing tramites by folioInterno prefix (correct field name).
    """
    y = year or datetime.utcnow().year
    prefix = f"TRM-{y}-"

    data = await _gql(
        """
        query GetFoliosAnio($filter: TramiteFilterInput) {
          tramites(filter: $filter) {
            edges { node { id folioInterno } }
          }
        }
        """,
        {"filter": {"folioInterno": {"like": f"{prefix}%"}}},
    )
    edges = data.get("tramites", {}).get("edges", [])
    nums: list[int] = []
    for edge in edges:
        f = (edge.get("node") or {}).get("folioInterno", "")
        if f.startswith(prefix):
            try:
                nums.append(int(f[len(prefix):]))
            except ValueError:
                pass

    next_n = (max(nums) + 1) if nums else 1
    return f"{prefix}{next_n:05d}"


# ── Agent search (cascade) ─────────────────────────────────────────────────────

async def _buscar_agente_por_email(email: str) -> str | None:
    """
    Try 1: Search for a Person whose primaryEmail matches, then return their company.
    Also try searching Company directly by emailPrincipal.
    Returns company_id (Twenty Company) or None.
    """
    if not email:
        return None

    # Search Person first
    try:
        data = await _gql(
            """
            query FindPersonByEmail($filter: PersonFilterInput) {
              people(filter: $filter) {
                edges {
                  node {
                    id
                    company { id name cua }
                  }
                }
              }
            }
            """,
            {"filter": {"emails": {"primaryEmail": {"eq": email}}}},
        )
        edges = data.get("people", {}).get("edges", [])
        if edges:
            company = (edges[0].get("node") or {}).get("company")
            if company and company.get("id"):
                logger.info(f"Agente encontrado via email Person: {company['name']!r}")
                return company["id"]
    except Exception as exc:
        logger.warning(f"Person email search failed: {exc}")

    # Search Company by emailPrincipal
    try:
        data = await _gql(
            """
            query FindCompanyByEmail($filter: CompanyFilterInput) {
              companies(filter: $filter) {
                edges { node { id name cua } }
              }
            }
            """,
            {"filter": {"emailPrincipal": {"primaryEmail": {"eq": email}}}},
        )
        edges = data.get("companies", {}).get("edges", [])
        if edges:
            node = edges[0].get("node") or {}
            logger.info(f"Agente encontrado via emailPrincipal Company: {node.get('name')!r}")
            return node.get("id")
    except Exception as exc:
        logger.warning(f"Company email search failed: {exc}")

    return None


async def _buscar_agente_por_cua(cua: str) -> str | None:
    """Try 2: Search Company by CUA field. Returns company_id or None."""
    if not cua:
        return None
    try:
        data = await _gql(
            """
            query FindCompanyByCua($filter: CompanyFilterInput) {
              companies(filter: $filter) {
                edges { node { id name cua } }
              }
            }
            """,
            {"filter": {"cua": {"eq": cua}}},
        )
        edges = data.get("companies", {}).get("edges", [])
        if edges:
            node = edges[0].get("node") or {}
            logger.info(f"Agente encontrado via CUA: {node.get('name')!r}")
            return node.get("id")
    except Exception as exc:
        logger.warning(f"CUA search failed: {exc}")
    return None


async def _buscar_agente_fuzzy(nombre: str) -> str | None:
    """
    Try 3: Fuzzy name match via LLM.
    Pre-filters Fifty companies using ILIKE to avoid missing candidates via hard limit.
    Then asks LLM to find best match via Pydantic structured output.
    Returns company_id if confidence >= 85, else None.
    """
    if not nombre:
        return None

    # Attempt to grab the first word to do a broad match
    fragmento = nombre.strip().split()[0]

    try:
        # Buscamos primero con filtro ilike del primer nombre, y bajamos 150 para asegurar cobertura
        data = await _gql(
            """
            query FindFuzzyCompanies($like: String!) {
              companies(first: 150, filter: { deletedAt: { is: NULL }, name: { ilike: $like } }) {
                edges { node { id name } }
              }
            }
            """,
            {"like": f"%{fragmento}%"}
        )
        edges = data.get("companies", {}).get("edges", [])

        # Fallback if the ILIKE was too strict (e.g. they misspelled the first word)
        if not edges:
            data = await _gql(
                """
                {
                  companies(first: 150, filter: { deletedAt: { is: NULL } }) {
                    edges { node { id name } }
                  }
                }
                """
            )
            edges = data.get("companies", {}).get("edges", [])
        
        if not edges:
            return None

        lista = [
            {"id": (e.get("node") or {}).get("id"), "name": (e.get("node") or {}).get("name")}
            for e in edges
            if (e.get("node") or {}).get("id")
        ]
        lista_str = json.dumps(lista, ensure_ascii=False)

        prompt = (
            f"De esta lista de agentes: {lista_str}\n\n"
            f"¿Cuál coincide mejor probabilísticamente con el nombre '{nombre}'?\n"
            "Si ninguno parece ser la misma persona o supera 85% de similitud, indica null en company_id."
        )

        llm_resp = await litellm.acompletion(
            model=LLM_MODEL,
            response_format=MatchAgente,
            messages=[{"role": "user", "content": prompt}],
            timeout=20,
        )
        raw = llm_resp.choices[0].message.content or "{}"
        result = MatchAgente.model_validate_json(raw)

        if result.confidence >= 85 and result.company_id:
            logger.info(
                f"Agente encontrado via fuzzy LLM: {result.company_name!r} "
                f"confidence={result.confidence}"
            )
            return result.company_id
    except Exception as exc:
        logger.warning(f"Fuzzy agent search failed: {exc}")

    return None


async def _buscar_agente_cascada(
    email: str | None,
    cua: str | None,
    nombre: str | None,
) -> tuple[str | None, str]:
    """
    Run the 3-step cascade search. Returns (company_id | None, method_used).
    """
    if email:
        company_id = await _buscar_agente_por_email(email)
        if company_id:
            return company_id, "email"

    if cua:
        company_id = await _buscar_agente_por_cua(cua)
        if company_id:
            return company_id, "cua"

    if nombre:
        company_id = await _buscar_agente_fuzzy(nombre)
        if company_id:
            return company_id, "fuzzy_llm"

    return None, "not_found"


# ── Analyst lookup ─────────────────────────────────────────────────────────────

async def _buscar_analista(
    agente_company_id: str,
    ramo_enum: str,
) -> tuple[str | None, str]:
    """
    Find the assigned specialist for (agente, ramo) using the Asignacion object.
    Returns (workspace_member_id | None, error_message).
    """
    try:
        data = await _gql(
            """
            query GetAsignacion($filter: AsignacionFilterInput) {
              asignaciones(filter: $filter) {
                edges {
                  node {
                    id
                    especialista {
                      id
                      userEmail
                      name { firstName lastName }
                    }
                  }
                }
              }
            }
            """,
            {
                "filter": {
                    "and": [
                        {"agenteId": {"eq": agente_company_id}},
                        {"ramo": {"eq": ramo_enum}},
                        {"asignacionActiva": {"eq": True}},
                    ]
                }
            },
        )
        edges = data.get("asignaciones", {}).get("edges", [])
        if not edges:
            return None, f"Sin asignación configurada para agente {agente_company_id} en ramo {ramo_enum}"

        especialista = (edges[0].get("node") or {}).get("especialista") or {}
        esp_id = especialista.get("id")
        if not esp_id:
            return None, "Asignación encontrada pero sin especialista configurado"

        return esp_id, ""
    except Exception as exc:
        return None, f"Error consultando asignaciones: {exc}"


def _buscar_cobertura(analista_id: str, ramo: str) -> str | None:
    """
    Check Supabase for active coverage (vacations/substitution) for today.
    Returns sustituto_twenty_id if active coverage found, else None.
    """
    if not _sb:
        return None
    try:
        today = date.today().isoformat()
        resp = (
            _sb.table("cobertura_analistas")
            .select("sustituto_twenty_id")
            .eq("analista_twenty_id", analista_id)
            .eq("ramo", ramo)
            .eq("activo", True)
            .lte("fecha_inicio", today)
            .gte("fecha_fin", today)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if rows:
            return rows[0].get("sustituto_twenty_id")
    except Exception as exc:
        logger.warning(f"Cobertura check failed: {exc}")
    return None


# ── Twenty Tramite creation ────────────────────────────────────────────────────

async def _crear_tramite_twenty(
    folio: str,
    tipo_tramite: str | None,
    ramo: str | None,
    estado: str,
    agente_company_id: str | None,
    analista_id: str | None,
    nombre_asegurado: str | None,
    numero_poliza: str | None,
    notas: str | None,
    fecha_limite_sla: date | None,
) -> str:
    """
    Create a Tramite in Twenty CRM. Returns the new tramite ID.
    Only includes fields verified to exist in the schema.
    """
    display_name = folio
    if tipo_tramite:
        display_name = f"{folio} — {tipo_tramite}"

    data: dict = {
        "name":           display_name,
        "folioInterno":   folio,
        "estadoTramite":  estado,
        "fechaEntrada":   date.today().isoformat(),
    }

    # Optional fields — only add if they have a value
    if tipo_tramite:
        data["tipoTramite"] = tipo_tramite
    if ramo:
        data["ramo"] = ramo
    if agente_company_id:
        data["agenteTitularId"] = agente_company_id
    if analista_id:
        data["especialistaAsignadoId"] = analista_id
    if nombre_asegurado:
        data["nombreAsegurado"] = nombre_asegurado[:255]
    if numero_poliza:
        data["numPolizaGnp"] = numero_poliza[:100]
    if notas:
        data["notasAnalista"] = notas[:2000]
    if fecha_limite_sla:
        data["fechaLimiteSla"] = fecha_limite_sla.isoformat()

    result = await _gql(
        """
        mutation CreateTramite($data: TramiteCreateInput!) {
          createTramite(data: $data) {
            id
            folioInterno
            estadoTramite
          }
        }
        """,
        {"data": data},
    )
    tramite = result.get("createTramite") or {}
    tramite_id = tramite.get("id")
    if not tramite_id:
        raise ValueError(f"createTramite returned no id: {result}")
    return tramite_id


# ── Supabase helpers ────────────────────────────────────────────────────────────

def _registrar_historial(
    tramite_pipeline_id: str,
    twenty_tramite_id: str,
    analista_id: str,
    agente_id: str | None,
    tipo_asignacion: str,
    motivo: str,
    ramo: str | None,
) -> None:
    if not _sb:
        return
    try:
        _sb.table("historial_asignaciones").insert({
            "tramite_pipeline_id": tramite_pipeline_id,
            "twenty_tramite_id":   twenty_tramite_id,
            "analista_twenty_id":  analista_id,
            "agente_twenty_id":    agente_id,
            "tipo_asignacion":     tipo_asignacion,
            "motivo":              motivo,
            "asignado_por":        "sistema",
            "ramo":                ramo,
        }).execute()
    except Exception as exc:
        logger.warning(f"historial_asignaciones insert failed: {exc}")


def _actualizar_pipeline(
    tramite_id: str,
    status: str,
    twenty_tramite_id: str | None = None,
    agente_twenty_id: str | None = None,
    analista_twenty_id: str | None = None,
    motivo_revision: str | None = None,
) -> None:
    if not _sb:
        return
    update: dict = {
        "status":     status,
        "asignado_at": datetime.utcnow().isoformat(),
    }
    if twenty_tramite_id is not None:
        update["twenty_tramite_id"] = twenty_tramite_id
    if agente_twenty_id is not None:
        update["agente_twenty_id"] = agente_twenty_id
    if analista_twenty_id is not None:
        update["analista_twenty_id"] = analista_twenty_id
    if motivo_revision is not None:
        update["motivo_revision"] = motivo_revision
    try:
        _sb.table("tramites_pipeline").update(update).eq("id", tramite_id).execute()
    except Exception as exc:
        logger.warning(f"tramites_pipeline update failed: {exc}")


# ── Pydantic models ────────────────────────────────────────────────────────────

class AsignacionRequest(BaseModel):
    tramite_id: str


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/asignacion")
async def agente_asignacion(data: AsignacionRequest):
    """
    Agente 4 — Identificación y asignación.

    Lee tramites_pipeline, identifica al agente en Twenty CRM,
    consulta al analista activo hoy (considerando cobertura por vacaciones),
    crea el Trámite en Twenty y registra la asignación.
    """
    tramite_id = data.tramite_id
    logger.info(f"agente_asignacion tramite_id={tramite_id!r}")

    if not _sb:
        raise HTTPException(503, "Supabase no configurado")

    # ── Paso 3: Leer datos consolidados de Supabase ─────────────────────────
    try:
        resp = _sb.table("tramites_pipeline").select("*").eq("id", tramite_id).execute()
        rows = resp.data or []
    except Exception as exc:
        logger.error(f"Supabase read error: {exc}")
        raise HTTPException(503, f"Supabase no disponible: {exc}")

    if not rows:
        raise HTTPException(404, f"tramite_id {tramite_id!r} no encontrado en tramites_pipeline")

    datos = rows[0]

    remitente_email  = datos.get("correo_remitente") or ""
    agente_cua       = datos.get("agente_cua")
    nombre_asegurado = datos.get("nombre_asegurado")
    tipo_tramite_raw = datos.get("tipo_tramite")
    ramo_raw         = datos.get("ramo")
    numero_poliza    = datos.get("numero_poliza")
    confianza_global = datos.get("confianza_global") or 0
    es_duplicado     = datos.get("es_duplicado_posible") or False
    duplicado_ref    = datos.get("tramite_duplicado_ref")
    resumen          = datos.get("resumen") or datos.get("resumen_ia") or ""

    # Normalize to Twenty enum values
    ramo_enum  = _normalizar_ramo(ramo_raw)
    tipo_enum  = _normalizar_tipo(tipo_tramite_raw)

    # ── Paso 4: Verificaciones previas ──────────────────────────────────────
    motivo_revision: str | None = None

    if confianza_global < 75:
        motivo_revision = (
            f"Confianza insuficiente: {confianza_global}/100. "
            "Campos con baja confianza requieren revisión humana."
        )
    elif es_duplicado:
        motivo_revision = (
            f"Posible duplicado del trámite {duplicado_ref}. "
            "Revisar manualmente antes de procesar."
        )
    elif not tipo_tramite_raw or not ramo_raw:
        motivo_revision = (
            "No fue posible determinar el tipo de trámite o el ramo. "
            "El correo requiere revisión manual."
        )

    # ── Paso 5: Búsqueda cascada del agente (sólo si no hay revisión manual) ─
    agente_company_id: str | None = None

    if not motivo_revision:
        agente_company_id, search_method = await _buscar_agente_cascada(
            email=remitente_email or None,
            cua=agente_cua,
            nombre=nombre_asegurado,
        )
        if not agente_company_id:
            motivo_revision = (
                f"Agente no identificado. El remitente {remitente_email!r} "
                "no está registrado en el sistema."
            )
        else:
            logger.info(f"Agente identificado via {search_method}: {agente_company_id}")
            # Persist immediately
            _actualizar_pipeline(tramite_id, datos.get("status", "comprendido"),
                                  agente_twenty_id=agente_company_id)

    # ── Paso 6: Consultar analista activo ────────────────────────────────────
    analista_final_id: str | None = None
    tipo_asignacion = "automatica"

    if not motivo_revision and agente_company_id and ramo_enum:
        analista_titular_id, asignacion_error = await _buscar_analista(
            agente_company_id, ramo_enum
        )
        if not analista_titular_id:
            motivo_revision = asignacion_error
        else:
            # Check coverage/vacation substitution
            sustituto_id = await asyncio.to_thread(
                _buscar_cobertura, analista_titular_id, ramo_enum
            )
            if sustituto_id:
                analista_final_id = sustituto_id
                tipo_asignacion   = "cobertura"
                logger.info(
                    f"Cobertura activa: titular={analista_titular_id} → "
                    f"sustituto={sustituto_id}"
                )
            else:
                analista_final_id = analista_titular_id
                tipo_asignacion   = "automatica"

    # ── Paso 7 / 8: Crear Trámite en Twenty ─────────────────────────────────
    # Regardless of revision_manual, we always create the tramite in Twenty.
    estado_tramite = "EN_REVISION" if motivo_revision else "PENDIENTE"

    notas_analista = resumen
    if motivo_revision:
        notas_analista = f"REVISIÓN REQUERIDA: {motivo_revision}\n\n{resumen}"

    # Generate folio
    try:
        folio = await _generar_folio()
    except Exception as exc:
        logger.warning(f"Folio generation failed: {exc}. Using placeholder.")
        folio = f"TRM-{datetime.utcnow().year}-XXXXX"

    # Calculate SLA (inline, avoids circular HTTP call)
    dias_sla = _SLA_DIAS.get(ramo_enum or "", 5)
    fecha_limite_sla = _add_business_days(date.today(), dias_sla)

    try:
        twenty_tramite_id = await _crear_tramite_twenty(
            folio=folio,
            tipo_tramite=tipo_enum,
            ramo=ramo_enum,
            estado=estado_tramite,
            agente_company_id=agente_company_id,
            analista_id=analista_final_id,
            nombre_asegurado=nombre_asegurado,
            numero_poliza=numero_poliza,
            notas=notas_analista,
            fecha_limite_sla=fecha_limite_sla,
        )
        logger.info(f"Tramite creado en Twenty: {twenty_tramite_id} folio={folio}")
    except (ValueError, Exception) as exc:
        # Twenty mutation failure — mark pipeline as error and propagate
        error_msg = str(exc)
        logger.error(f"createTramite falló: {error_msg}")
        await asyncio.to_thread(
            _actualizar_pipeline, tramite_id, "error_agente4",
            motivo_revision=f"createTramite falló: {error_msg[:300]}"
        )
        raise HTTPException(
            500,
            {"error": f"No se pudo crear el trámite en Twenty: {error_msg}", "tramite_id": tramite_id}
        )

    # ── Paso 7d / 8b: Update tramites_pipeline ──────────────────────────────
    final_status = "revision_manual" if motivo_revision else "completado"
    await asyncio.to_thread(
        _actualizar_pipeline,
        tramite_id,
        final_status,
        twenty_tramite_id=twenty_tramite_id,
        agente_twenty_id=agente_company_id,
        analista_twenty_id=analista_final_id,
        motivo_revision=motivo_revision,
    )

    # ── Paso 7e / 8c: historial_asignaciones ────────────────────────────────
    hist_tipo    = "manual" if motivo_revision else tipo_asignacion
    hist_analista = analista_final_id or "pendiente"
    hist_motivo  = (
        motivo_revision
        if motivo_revision
        else f"Asignación automática. Ramo: {ramo_enum}"
    )
    await asyncio.to_thread(
        _registrar_historial,
        tramite_id,
        twenty_tramite_id,
        hist_analista,
        agente_company_id,
        hist_tipo,
        hist_motivo,
        ramo_enum,
    )

    # ── Respuesta ────────────────────────────────────────────────────────────
    if motivo_revision:
        return {
            "tramite_id":       tramite_id,
            "status":           "revision_manual",
            "motivo_revision":  motivo_revision,
            "twenty_tramite_id": twenty_tramite_id,
            "agente_twenty_id": None,
            "analista_twenty_id": None,
            "tipo_asignacion":  "manual",
            "folio":            folio,
        }

    return {
        "tramite_id":         tramite_id,
        "status":             "completado",
        "twenty_tramite_id":  twenty_tramite_id,
        "agente_twenty_id":   agente_company_id,
        "analista_twenty_id": analista_final_id,
        "tipo_asignacion":    tipo_asignacion,
        "folio":              folio,
    }
