import asyncio
import json
import os
import base64
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Optional

import httpx
import litellm
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential
import uvicorn

from agent_llm import extract_passwords_from_text
from agente_asignacion import router as asignacion_router
from agente_documentos import router as documentos_router
from extractor import process_attachments
from supabase_client import (
    check_existing_thread,
    log_attachment_processing,
    log_inline_images,
    save_reply_record,
    upload_file,
    upload_file_to_path,
    supabase as _sb,
)

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

TWENTY_API_URL = os.getenv("TWENTY_API_URL", "http://localhost:3000")
TWENTY_API_KEY = os.getenv("TWENTY_API_KEY", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Email Attachment Processor API")
app.include_router(documentos_router, prefix="/api/v1/agentes")
app.include_router(asignacion_router, prefix="/api/v1/agentes")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def extract_inline_images_from_html(body_html: str, email_id: str) -> list[dict]:
    """
    Extract base64-embedded inline images from HTML email body.
    Handles: <img src="data:image/jpeg;base64,...">
    Returns list of metadata dicts for each image successfully uploaded.
    """
    if not body_html:
        return []

    try:
        soup = BeautifulSoup(body_html, "lxml")
    except Exception:
        soup = BeautifulSoup(body_html, "html.parser")

    results: list[dict] = []
    inline_index = 1

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src.startswith("data:"):
            continue
        try:
            # Format: "data:{mime_type};base64,{data}"
            header, data_b64 = src.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]          # image/jpeg
            ext = mime_type.split("/")[-1].replace("jpeg", "jpg").lower()
            nombre = f"inline_{inline_index:03d}.{ext}"
            storage_path = f"{email_id}/inline/{nombre}"

            # Add padding to avoid base64 decode errors
            padding = 4 - len(data_b64) % 4
            if padding != 4:
                data_b64 += "=" * padding
            contenido = base64.b64decode(data_b64)

            path = upload_file_to_path(storage_path, contenido, mime_type)
            if path:
                results.append({
                    "nombre": nombre,
                    "storage_path": path,
                    "mime_type": mime_type,
                    "tamano_bytes": len(contenido),
                })
                inline_index += 1
        except Exception as e:
            logger.warning(f"Error extracting inline image {inline_index}: {e}")

    return results


async def _add_note_to_twenty(tramite_id: str, note_text: str) -> bool:
    """Create a note and link it to a tramite in Twenty CRM."""
    if not tramite_id or not TWENTY_API_KEY:
        return False

    headers = {
        "Authorization": f"Bearer {TWENTY_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Create note
            note_resp = await client.post(
                f"{TWENTY_API_URL}/rest/notes",
                json={"body": note_text},
                headers=headers,
            )
            if not note_resp.is_success:
                logger.warning(f"Failed to create note: {note_resp.status_code}")
                return False

            note_data = note_resp.json()
            note_id = (
                note_data.get("data", {}).get("note", {}).get("id")
                or note_data.get("data", {}).get("createNote", {}).get("id")
            )
            if not note_id:
                return False

            # 2. Link note to tramite
            await client.post(
                f"{TWENTY_API_URL}/rest/noteTargets",
                json={"noteId": note_id, "tramiteId": tramite_id},
                headers=headers,
            )
        return True
    except Exception as e:
        logger.warning(f"Error adding note to Twenty: {e}")
        return False


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/process-email")
async def process_email(
    # Formato n8n: JSON blob con adjuntos en base64
    email_data: str = Form(None),
    # Formato directo (UploadFile): campos separados
    email_id: str = Form(None),
    subject: str = Form(""),
    body: str = Form(""),
    body_html: str = Form(""),
    attachments: List[UploadFile] = File(None),
):
    """
    Recibe datos del correo + adjuntos desde n8n.
    Soporta dos formatos:
      1. email_data (JSON string): formato n8n con adjuntos en base64
      2. Campos Form separados + UploadFile: formato directo
    Proceso:
      1. Desencripta / extrae ZIP/RAR (extrae contraseña vía LLM si es necesario)
      2. Sube archivos procesados a Supabase Storage
      3. Extrae imágenes inline (base64) del cuerpo HTML
      4. Registra todo en attachments_log
    """
    raw_files: list[tuple[str, bytes]] = []

    if email_data:
        # Formato n8n: parsear JSON blob y reconstruir adjuntos desde base64
        try:
            data = json.loads(email_data)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"email_data JSON inválido: {e}")

        email_id = data.get("tramite_id") or data.get("email_id")
        if not email_id:
            raise HTTPException(422, "email_data debe contener 'tramite_id' o 'email_id'")

        subject = data.get("asunto") or data.get("subject", "")
        body = data.get("cuerpo") or data.get("body", "")
        body_html = data.get("cuerpo_html") or data.get("body_html", "")

        for adj in data.get("adjuntos", []):
            nombre = adj.get("nombre_archivo") or adj.get("filename", "adjunto")
            b64 = adj.get("datos_base64") or adj.get("data_base64", "")
            if not b64:
                continue
            # Corregir padding de base64 si es necesario
            padding = 4 - len(b64) % 4
            if padding != 4:
                b64 += "=" * padding
            try:
                file_bytes = base64.b64decode(b64)
                raw_files.append((nombre, file_bytes))
            except Exception as e:
                logger.warning(f"No se pudo decodificar base64 para '{nombre}': {e}")

        logger.info(f"process-email (formato n8n) id={email_id!r} subject={subject!r} adjuntos={len(raw_files)}")

    elif email_id:
        # Formato directo con UploadFile
        if attachments:
            raw_files = [(f.filename, await f.read()) for f in attachments]
        logger.info(f"process-email (formato directo) id={email_id!r} subject={subject!r} adjuntos={len(raw_files)}")

    else:
        raise HTTPException(422, "Se requiere 'email_data' (n8n) o 'email_id' (directo)")

    attachment_paths: list[str] = []
    total_received = 0
    total_successful = 0

    if raw_files:
        result = process_attachments(
            raw_files,
            body,
            get_passwords_hook=lambda text: extract_passwords_from_text(text),
        )
        files_to_upload = result.get("files_to_upload", [])
        total_received = result.get("total_received", 0)

        for filename, file_bytes in files_to_upload:
            path = upload_file(email_id, filename, file_bytes)
            if path:
                attachment_paths.append(path)

        total_successful = len(attachment_paths)
        log_attachment_processing(email_id, total_received, total_successful, attachment_paths)

    # Extraer imágenes inline del cuerpo HTML
    inline_images = extract_inline_images_from_html(body_html, email_id)
    if inline_images:
        log_inline_images(email_id, inline_images)
        logger.info(f"Extracted {len(inline_images)} inline image(s) for {email_id}")

    return {
        "status": "success",
        "email_id": email_id,
        "total_attachments_received": total_received,
        "successful_attachments": total_successful,
        "uploaded_paths": attachment_paths,
        "inline_extraidas": len(inline_images),
    }


class CheckReplyRequest(BaseModel):
    thread_id: str
    message_id: str


@app.post("/check-reply")
async def check_reply(data: CheckReplyRequest):
    """
    Check if a Gmail thread already has an active tramite in Supabase.
    Returns: { is_reply, tramite_pipeline_id, twenty_tramite_id, status }
    n8n calls this right after Gmail Trigger to decide whether to branch.
    """
    result = check_existing_thread(data.thread_id)
    logger.info(f"check-reply thread={data.thread_id!r} → found={result.get('found')}")
    return {
        "is_reply": result.get("found", False),
        "tramite_pipeline_id": result.get("tramite_pipeline_id"),
        "twenty_tramite_id": result.get("twenty_tramite_id"),
        "status": result.get("status"),
    }


class ProcessReplyRequest(BaseModel):
    thread_id: str
    message_id: str
    tramite_pipeline_id: Optional[str] = None
    twenty_tramite_id: Optional[str] = None
    email_from: str = ""
    email_subject: str = ""
    email_date: str = ""
    email_body: str = ""


@app.post("/process-reply")
async def process_reply(data: ProcessReplyRequest):
    """
    Handle a reply email:
    1. Insert a 'reply_adjuntado' row in tramites_pipeline
    2. If twenty_tramite_id is set, add a note to the tramite in Twenty CRM
    Called from n8n when check-reply returns is_reply=true.
    """
    logger.info(f"process-reply thread={data.thread_id!r} from={data.email_from!r}")

    record_id = save_reply_record(
        thread_id=data.thread_id,
        message_id=data.message_id,
        twenty_tramite_id=data.twenty_tramite_id,
        email_from=data.email_from,
        email_subject=data.email_subject,
    )

    note_added = False
    if data.twenty_tramite_id:
        fecha = (data.email_date or datetime.utcnow().isoformat())[:10]
        note_text = (
            f"📧 Reply recibido ({fecha})\n"
            f"De: {data.email_from}\n"
            f"Asunto: {data.email_subject}\n"
            f"—\n{data.email_body[:500]}"
        )
        note_added = await _add_note_to_twenty(data.twenty_tramite_id, note_text)

    return {
        "action": "reply_processed",
        "record_id": record_id,
        "note_added": note_added,
        "twenty_tramite_id": data.twenty_tramite_id,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}


# ─── GraphQL helper ───────────────────────────────────────────────────────────

async def _gql(query: str, variables: dict | None = None) -> dict:
    """
    Execute a GraphQL query/mutation against Twenty API.
    Raises ValueError if GraphQL returns errors[].
    """
    headers = {
        "Authorization": f"Bearer {TWENTY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{TWENTY_API_URL}/api",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        body = resp.json()

    if "errors" in body and body["errors"]:
        raise ValueError(f"GraphQL errors: {body['errors']}")

    return body.get("data", {})


def _add_business_days(start: date, days: int) -> date:
    """Add N business days (Mon–Fri) to start date."""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # 0=Mon … 4=Fri
            added += 1
    return current


# Default SLA days per ramo (días hábiles)
_DEFAULT_SLA: dict[str, int] = {
    "Vida": 5,
    "GMM": 3,
    "Autos": 4,
    "PYME": 7,
    "Daños": 5,
    "Siniestros": 2,
}


def _sla_config() -> dict[str, int]:
    """Return SLA config, merging env overrides over defaults."""
    raw = os.getenv("SLA_CONFIG", "")
    if raw:
        try:
            overrides = json.loads(raw)
            return {**_DEFAULT_SLA, **overrides}
        except Exception:
            logger.warning("Invalid SLA_CONFIG JSON, using defaults")
    return dict(_DEFAULT_SLA)


# ─── New endpoints ────────────────────────────────────────────────────────────

class AutoFolioRequest(BaseModel):
    tramite_id: str


@app.post("/auto-folio")
async def auto_folio(data: AutoFolioRequest):
    """
    Generate and assign the next sequential folio to a tramite.
    Format: TRM-{YYYY}-{00001..99999}
    """
    logger.info(f"auto-folio tramite_id={data.tramite_id!r}")
    year = datetime.utcnow().year
    prefix = f"TRM-{year}-"

    # Fetch all tramites whose folio starts with this year's prefix
    query_folios = """
    query GetFoliosAnio($filter: TramiteFilterInput) {
      tramites(filter: $filter) {
        edges {
          node {
            id
            folio
          }
        }
      }
    }
    """
    gql_data = await _gql(
        query_folios,
        {"filter": {"folio": {"like": f"{prefix}%"}}},
    )

    edges = (
        gql_data.get("tramites", {}).get("edges", [])
        or gql_data.get("tramites", {}).get("nodes", [])
    )
    # Handle both edges[].node and nodes[] shapes
    folios: list[int] = []
    for edge in edges:
        node = edge.get("node", edge)  # support flat nodes list
        f = node.get("folio", "")
        if f.startswith(prefix):
            try:
                folios.append(int(f[len(prefix):]))
            except ValueError:
                pass

    next_num = (max(folios) + 1) if folios else 1
    new_folio = f"{prefix}{next_num:05d}"

    # Mutation: update folio on the tramite
    mutation_folio = """
    mutation SetFolio($id: ID!, $data: TramiteUpdateInput!) {
      updateTramite(id: $id, data: $data) {
        id
        folio
      }
    }
    """
    await _gql(mutation_folio, {"id": data.tramite_id, "data": {"folio": new_folio}})
    logger.info(f"auto-folio assigned {new_folio!r} to tramite {data.tramite_id}")
    return {"folio": new_folio}


class AutoAsignacionRequest(BaseModel):
    tramite_id: str
    agente_id: str
    ramo: str


@app.post("/auto-asignacion")
async def auto_asignacion(data: AutoAsignacionRequest):
    """
    Look up the configured Asignacion for (agente, ramo) and assign
    the specialist, or flag the tramite for manual review.
    """
    logger.info(
        f"auto-asignacion tramite={data.tramite_id!r} agente={data.agente_id!r} ramo={data.ramo!r}"
    )

    query_asignacion = """
    query GetAsignacion($filter: AsignacionFilterInput) {
      asignaciones(filter: $filter) {
        edges {
          node {
            id
            especialistaAsignado {
              id
            }
          }
        }
      }
    }
    """
    gql_data = await _gql(
        query_asignacion,
        {
            "filter": {
                "and": [
                    {"agente": {"id": {"eq": data.agente_id}}},
                    {"ramo": {"eq": data.ramo}},
                    {"activo": {"eq": True}},
                ]
            }
        },
    )

    edges = (
        gql_data.get("asignaciones", {}).get("edges", [])
        or gql_data.get("asignaciones", {}).get("nodes", [])
    )

    if edges:
        node = edges[0].get("node", edges[0])
        especialista_rel = node.get("especialistaAsignado") or {}
        especialista_id: str | None = especialista_rel.get("id")

        mutation_assign = """
        mutation AssignEspecialista($id: ID!, $data: TramiteUpdateInput!) {
          updateTramite(id: $id, data: $data) {
            id
          }
        }
        """
        await _gql(
            mutation_assign,
            {
                "id": data.tramite_id,
                "data": {"especialistaAsignadoId": especialista_id},
            },
        )
        logger.info(
            f"auto-asignacion especialista {especialista_id!r} asignado a tramite {data.tramite_id}"
        )
        return {"asignado": True, "especialista_id": especialista_id}
    else:
        # No assignment configured → flag for manual review
        mutation_manual = """
        mutation FlagManualReview($id: ID!, $data: TramiteUpdateInput!) {
          updateTramite(id: $id, data: $data) {
            id
          }
        }
        """
        await _gql(
            mutation_manual,
            {
                "id": data.tramite_id,
                "data": {
                    "estadoTramite": "REVISION_MANUAL",
                    "notasAnalista": "Sin asignación configurada para este agente+ramo",
                },
            },
        )
        logger.info(
            f"auto-asignacion no encontrada → REVISION_MANUAL para tramite {data.tramite_id}"
        )
        return {"asignado": False, "especialista_id": None}


class AutoSlaRequest(BaseModel):
    tramite_id: str
    ramo: str


@app.post("/auto-sla")
async def auto_sla(data: AutoSlaRequest):
    """
    Calculate and set fechaLimiteSla on a tramite based on ramo SLA rules.
    Business days only (Mon–Fri). Defaults configurable via SLA_CONFIG env var.
    """
    logger.info(f"auto-sla tramite={data.tramite_id!r} ramo={data.ramo!r}")

    sla_map = _sla_config()
    dias = sla_map.get(data.ramo, 5)
    fecha_limite = _add_business_days(date.today(), dias)
    fecha_str = fecha_limite.isoformat()  # "2026-04-03"

    mutation_sla = """
    mutation SetSla($id: ID!, $data: TramiteUpdateInput!) {
      updateTramite(id: $id, data: $data) {
        id
      }
    }
    """
    await _gql(
        mutation_sla,
        {"id": data.tramite_id, "data": {"fechaLimiteSla": fecha_str}},
    )
    logger.info(
        f"auto-sla fechaLimiteSla={fecha_str} ({dias}d hábiles) en tramite {data.tramite_id}"
    )
    return {"fecha_limite": fecha_str}


@app.post("/mark-overdue-sla")
async def mark_overdue_sla():
    """
    Cron endpoint: find all tramites past their SLA deadline and mark fueraDeSla=true.
    Skips tramites already closed/cancelled/approved.
    """
    today_str = date.today().isoformat()
    logger.info(f"mark-overdue-sla run date={today_str}")

    query_overdue = """
    query GetOverdueTramites($filter: TramiteFilterInput) {
      tramites(filter: $filter) {
        edges {
          node {
            id
          }
        }
      }
    }
    """
    gql_data = await _gql(
        query_overdue,
        {
            "filter": {
                "and": [
                    {"fechaLimiteSla": {"lt": today_str}},
                    {"fueraDeSla": {"eq": False}},
                    {
                        "estadoTramite": {
                            "notIn": ["CERRADO", "CANCELADO", "APROBADO"]
                        }
                    },
                ]
            }
        },
    )

    edges = (
        gql_data.get("tramites", {}).get("edges", [])
        or gql_data.get("tramites", {}).get("nodes", [])
    )
    ids = [
        edge.get("node", edge).get("id")
        for edge in edges
        if edge.get("node", edge).get("id")
    ]

    mutation_overdue = """
    mutation MarkFueraDeSla($id: ID!, $data: TramiteUpdateInput!) {
      updateTramite(id: $id, data: $data) {
        id
      }
    }
    """
    marcados = 0
    for tramite_id in ids:
        try:
            await _gql(
                mutation_overdue,
                {"id": tramite_id, "data": {"fueraDeSla": True}},
            )
            marcados += 1
            logger.info(f"mark-overdue-sla marcado fueraDeSla tramite={tramite_id}")
        except Exception as e:
            logger.warning(f"mark-overdue-sla error en tramite {tramite_id}: {e}")

    logger.info(f"mark-overdue-sla completado marcados={marcados}")
    return {"marcados": marcados}


# ─── Agente 1: Comprensión de Email ──────────────────────────────────────────

_COMPRENSION_SYSTEM_PROMPT = """\
Eres un experto en seguros mexicanos para una promotoría GNP.
Analiza el correo y extrae datos con máxima precisión.

RAMOS VÁLIDOS: Vida, GMM, Autos, PYME, Daños, Siniestros
TIPOS DE TRÁMITE: nueva_poliza, renovacion, endoso, siniestro,
reembolso, cotizacion, cancelacion, reclamacion

Para cada campo extraído añade su respectivo `confidence` (0-100) basado en qué tan explícito es el dato en el correo.
Si un dato no aparece en el correo, retorna null con confidence 0.
"""

_CONFIDENCE_WEIGHTS = {
    "tipo_tramite":     0.30,
    "ramo":             0.25,
    "numero_poliza":    0.25,
    "nombre_asegurado": 0.10,
    "agente_cua":       0.10,
}


def _global_confidence(fields: dict) -> int:
    total = 0.0
    for key, weight in _CONFIDENCE_WEIGHTS.items():
        conf = (fields.get(key) or {}).get("confidence") or 0
        total += conf * weight
    return round(total)


def _dedup_check(
    record_id: str,
    remitente_email: str,
    asunto: str,
    numero_poliza: str | None,
    tipo_tramite: str | None,
) -> tuple[bool, str | None]:
    """3-query dedup. Returns (is_dup, ref_id_of_original)."""
    if not _sb:
        return False, None

    cutoff_72h = (datetime.utcnow() - timedelta(hours=72)).isoformat()
    cutoff_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    cutoff_48h = (datetime.utcnow() - timedelta(hours=48)).isoformat()

    try:
        # a) Mismo número de póliza activo en últimas 72h
        if numero_poliza:
            r = (
                _sb.table("tramites_pipeline")
                .select("id")
                .eq("numero_poliza", numero_poliza)
                .not_.in_("status", ["cancelado", "cerrado"])
                .gt("created_at", cutoff_72h)
                .limit(1)
                .execute()
            )
            hits = [x for x in (r.data or []) if x["id"] != record_id]
            if hits:
                return True, hits[0]["id"]

        # b) Mismo remitente + mismo tipo de trámite en últimas 24h
        if remitente_email and tipo_tramite:
            r = (
                _sb.table("tramites_pipeline")
                .select("id")
                .eq("correo_remitente", remitente_email)
                .eq("tipo_tramite", tipo_tramite)
                .gt("created_at", cutoff_24h)
                .limit(1)
                .execute()
            )
            hits = [x for x in (r.data or []) if x["id"] != record_id]
            if hits:
                return True, hits[0]["id"]

        # c) Asunto similar en últimas 48h
        if asunto:
            r = (
                _sb.table("tramites_pipeline")
                .select("id")
                .ilike("correo_asunto", f"%{asunto}%")
                .neq("id", record_id)
                .gt("created_at", cutoff_48h)
                .limit(1)
                .execute()
            )
            if r.data:
                return True, r.data[0]["id"]

    except Exception as exc:
        logger.warning(f"dedup_check error (non-fatal): {exc}")

    return False, None


class CampoString(BaseModel):
    valor: Optional[str] = Field(None)
    confidence: int = Field(0)

class CampoFloat(BaseModel):
    valor: Optional[float] = Field(None)
    confidence: int = Field(0)

class ExtraccionInicial(BaseModel):
    resumen: str = Field(description="2-3 oraciones del caso")
    tipo_tramite: CampoString
    ramo: CampoString
    numero_poliza: CampoString
    nombre_asegurado: CampoString
    agente_cua: CampoString
    monto: CampoFloat

class ComprensionRequest(BaseModel):
    email_id: str
    remitente_email: str = ""
    asunto: str = ""
    cuerpo_texto: str = ""


@app.post("/api/v1/agentes/comprension")
async def agente_comprension(data: ComprensionRequest):
    """
    Agente 1 — Comprensión de email con LiteLLM.
    Extrae campos estructurados, calcula confianza y detecta duplicados.
    Actualiza tramites_pipeline con status='comprendido'.
    """
    llm_model = os.environ.get("LLM_MODEL", "openai/gpt-4o")
    logger.info(f"comprension email_id={data.email_id!r} model={llm_model!r}")

    async def _mark_error(detail: str) -> None:
        if _sb:
            try:
                _sb.table("tramites_pipeline").update({
                    "status": "error_comprension",
                    "error_detalle": detail[:500],
                }).eq("id", data.email_id).execute()
            except Exception as e:
                logger.warning(f"Could not mark error in supabase: {e}")

    # ── 1. Llamar al LLM ─────────────────────────────────────────────────────
    raw_content = ""
    response_model = llm_model
    messages = [
        {"role": "system", "content": _COMPRENSION_SYSTEM_PROMPT},
        {"role": "user",   "content": data.cuerpo_texto or "(sin cuerpo)"},
    ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _call_llm():
        return await litellm.acompletion(
            model=llm_model,
            response_format=ExtraccionInicial,
            messages=messages,
            timeout=30,
        )

    try:
        llm_resp = await _call_llm()
        raw_content = llm_resp.choices[0].message.content or "{}"
        response_model = getattr(llm_resp, "model", None) or llm_model
        parsed_pydantic = ExtraccionInicial.model_validate_json(raw_content)
    except Exception as exc:
        logger.error(f"comprension error: {exc}")
        await _mark_error(str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

    # ── 2. Parsear Pydantic ───────────────────────────────────────────────────────
    resumen                    = parsed_pydantic.resumen
    tipo_val,  tipo_conf       = parsed_pydantic.tipo_tramite.valor, parsed_pydantic.tipo_tramite.confidence
    ramo_val,  ramo_conf       = parsed_pydantic.ramo.valor, parsed_pydantic.ramo.confidence
    poliza_val, poliza_conf    = parsed_pydantic.numero_poliza.valor, parsed_pydantic.numero_poliza.confidence
    aseg_val,  aseg_conf       = parsed_pydantic.nombre_asegurado.valor, parsed_pydantic.nombre_asegurado.confidence
    cua_val,   cua_conf        = parsed_pydantic.agente_cua.valor, parsed_pydantic.agente_cua.confidence
    monto_val, monto_conf      = parsed_pydantic.monto.valor, parsed_pydantic.monto.confidence

    campos_confianza = {
        "tipo_tramite":     tipo_conf,
        "ramo":             ramo_conf,
        "numero_poliza":    poliza_conf,
        "nombre_asegurado": aseg_conf,
        "agente_cua":       cua_conf,
        "monto":            monto_conf,
    }
    confianza_global = _global_confidence({
        k: {"confidence": v} for k, v in campos_confianza.items()
    })

    # ── 3. Detección de duplicados ────────────────────────────────────────────
    poliza_str = str(poliza_val) if poliza_val is not None else None
    es_dup, dup_ref = _dedup_check(
        record_id=data.email_id,
        remitente_email=data.remitente_email,
        asunto=data.asunto,
        numero_poliza=poliza_str,
        tipo_tramite=tipo_val,
    )
    if es_dup:
        logger.info(f"comprension posible duplicado de {dup_ref!r}")

    # ── 4. Actualizar tramites_pipeline ───────────────────────────────────────
    monto_float = float(monto_val) if monto_val is not None else None
    update_payload = {
        "tipo_tramite":          tipo_val,
        "ramo":                  ramo_val,
        "numero_poliza":         poliza_str,
        "nombre_asegurado":      aseg_val,
        "agente_cua":            cua_val,
        "monto":                 monto_float,
        "resumen":               resumen,
        "confianza_global":      confianza_global,
        "es_duplicado_posible":  es_dup,
        "tramite_duplicado_ref": dup_ref,
        "status":                "comprendido",
        "campos_confianza":      campos_confianza,
    }
    if _sb:
        try:
            _sb.table("tramites_pipeline").update(update_payload).eq("id", data.email_id).execute()
            logger.info(f"comprension supabase updated id={data.email_id!r}")
        except Exception as exc:
            logger.error(f"comprension supabase update error: {exc}")

    # ── 5. Respuesta ──────────────────────────────────────────────────────────
    return {
        "email_id":              data.email_id,
        "confianza_global":      confianza_global,
        "tipo_tramite":          tipo_val,
        "ramo":                  ramo_val,
        "numero_poliza":         poliza_str,
        "nombre_asegurado":      aseg_val,
        "agente_cua":            cua_val,
        "monto":                 monto_float,
        "resumen":               resumen,
        "es_duplicado_posible":  es_dup,
        "tramite_duplicado_ref": dup_ref,
        "modelo_usado":          response_model,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=4000, reload=True)
