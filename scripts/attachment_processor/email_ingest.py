"""
Email Ingestion Router — Matching hilo de conversación → Trámite

POST /api/v1/email/ingest

Pipeline de matching (ordenado de mayor a menor precisión):

  1. threadExternalId en HiloConversacion de Twenty  → hilo conocido, actualizar
  2. In-Reply-To / References headers → message_id en tramites_pipeline
  3. Regex folio interno  (TRM-YYYY-NNNNN) en asunto/cuerpo → tramite exacto
  4. Regex número de póliza en asunto/cuerpo         → tramite exacto
  5. Email del remitente  → Agente en Twenty → tramites activos del agente
       a. 1 tramite activo  → auto-vincular (confianza 90)
       b. N tramites activos → desambiguación por LLM (umbral 80)
  6. Sin match              → HiloConversacion sin tramite, requiereAccion=True

Supabase es fuente de verdad para logging/auditoría.
Twenty es best-effort (circuit breaker heredado de twenty_sync).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import unicodedata
from datetime import datetime
from typing import Literal, Optional

import litellm
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import twenty_sync
from agente_asignacion import _buscar_agente_por_email
from supabase_client import supabase as _sb

logger = logging.getLogger(__name__)
router = APIRouter()

LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o")


# ── Modelos Pydantic ───────────────────────────────────────────────────────────

class EmailIngestRequest(BaseModel):
    message_id: str = Field(
        ...,
        description="ID único del mensaje (Gmail Message-ID header o equivalente IMAP)",
    )
    thread_id: str = Field(
        ...,
        description="ID del hilo (Gmail threadId). Clave primaria de agrupación.",
    )
    from_email: str = Field(..., description="Email del remitente")
    from_name: str = Field("", description="Nombre del remitente (si está disponible)")
    to: list[str] = Field(default_factory=list, description="Lista de destinatarios")
    subject: str = Field("", description="Asunto del email")
    body_text: str = Field("", description="Cuerpo en texto plano")
    body_html: str = Field("", description="Cuerpo en HTML (opcional, para extracción de contexto)")
    received_at: str = Field(..., description="ISO 8601 timestamp de recepción")
    in_reply_to: str = Field("", description="Valor del header In-Reply-To")
    references: list[str] = Field(
        default_factory=list,
        description="Valores del header References (cadena completa de la conversación)",
    )
    has_attachments: bool = Field(False)
    attachment_count: int = Field(0)
    canal_origen: Literal["CORREO", "WHATSAPP"] = Field("CORREO")


class EmailIngestResponse(BaseModel):
    message_id: str
    thread_id: str
    strategy: str
    tramite_id: Optional[str]
    agente_id: Optional[str]
    hilo_id: Optional[str]
    requiere_accion: bool
    confianza: int
    urgencia_detectada: bool
    motivo_sin_match: Optional[str]
    ingest_log_id: Optional[str]


# Modelo para desambiguación LLM
class _TramiteMatch(BaseModel):
    tramite_id: Optional[str] = Field(
        None,
        description="UUID del tramite que mejor corresponde al email, o null si no hay coincidencia",
    )
    confidence: int = Field(
        0,
        description="Confianza 0-100. Solo retornar tramite_id si confidence >= 80",
    )
    razon: str = Field("", description="Breve justificación de la selección")


# ── Patrones de extracción ─────────────────────────────────────────────────────

# Folio interno: TRM-2026-00123
_RE_FOLIO = re.compile(r'\bTRM-\d{4}-\d{5}\b', re.IGNORECASE)

# Número de póliza GNP: 8-12 dígitos precedidos por palabra clave
_RE_POLIZA = [
    re.compile(r'\bP[ÓO]LIZA\s*[#N°:]?\s*(\d{6,12})\b', re.IGNORECASE),
    re.compile(r'\bNO\.?\s*P[ÓO]LIZA\s*[#:]?\s*(\d{6,12})\b', re.IGNORECASE),
    re.compile(r'\bFOLIO\s*GNP\s*[#:]?\s*(\d{6,12})\b', re.IGNORECASE),
]

# Palabras que implican urgencia operacional
_URGENCY_KEYWORDS = frozenset([
    'urgente', 'urgentísimo', 'urgentisimo',
    'vencimiento hoy', 'vence hoy', 'fecha límite', 'fecha limite',
    'rechazo gnp', 'gnp rechazó', 'gnp rechazo', 'me rechazaron',
    'bloqueado', 'detenido por gnp', 'sin respuesta de gnp',
    'ya pasaron días', 'llevan días', 'semanas sin respuesta',
    'cancelarán', 'cancelaran', 'van a cancelar',
    'último aviso', 'ultimo aviso', 'plazo vencido',
])

# Estados de tramite que se consideran "activos" para matching
_ESTADOS_ACTIVOS = frozenset([
    'RECIBIDO', 'EN_REVISION', 'PENDIENTE',
    'DOCUMENTACION_COMPLETA', 'TURNADO_GNP', 'EN_PROCESO_GNP', 'DETENIDO',
])


# ── Utilidades de texto ────────────────────────────────────────────────────────

def _strip_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _build_search_text(subject: str, body_text: str, body_html: str) -> str:
    """Combina asunto + cuerpo en texto plano para búsqueda."""
    parts = [subject]
    if body_text:
        parts.append(body_text[:3000])
    elif body_html:
        # Strip HTML básico para no depender de BS4 aquí
        html_stripped = re.sub(r'<[^>]+>', ' ', body_html)
        html_stripped = re.sub(r'\s+', ' ', html_stripped).strip()
        parts.append(html_stripped[:3000])
    return " ".join(parts)


def _detectar_urgencia(subject: str, body_text: str) -> bool:
    """Detecta si el email contiene señales de urgencia operacional."""
    combined = _strip_accents((subject + " " + body_text).lower())
    return any(_strip_accents(kw) in combined for kw in _URGENCY_KEYWORDS)


def _extraer_folio(text: str) -> Optional[str]:
    """Extrae un folio interno TRM-YYYY-NNNNN del texto."""
    match = _RE_FOLIO.search(text)
    return match.group(0).upper() if match else None


def _extraer_poliza(text: str) -> Optional[str]:
    """Extrae el primer número de póliza reconocido del texto."""
    for pattern in _RE_POLIZA:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def _determinar_ultimo_remitente(from_email: str) -> Literal["AGENTE", "ANALISTA"]:
    """
    Determina si el remitente es un analista (interno) o un agente (externo).
    Verifica contra contact_email_map en Supabase. Si no se puede determinar,
    asume AGENTE (el caso más común en la bandeja entrante de la promotoría).
    """
    if not _sb or not from_email:
        return "AGENTE"
    try:
        resp = (
            _sb.table("contact_email_map")
            .select("rol_contacto")
            .eq("email", from_email.lower())
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if rows and rows[0].get("rol_contacto") in ("analista", "especialista", "gerente"):
            return "ANALISTA"
    except Exception as exc:
        logger.debug(f"contact_email_map lookup failed: {exc}")
    return "AGENTE"


# ── Logging de auditoría en Supabase ──────────────────────────────────────────

def _log_ingest(
    *,
    message_id: str,
    thread_id: str,
    from_email: str,
    subject: str,
    received_at: str,
    strategy: str,
    tramite_id: Optional[str],
    agente_id: Optional[str],
    hilo_id: Optional[str],
    requiere_accion: bool,
    confianza: int,
    urgencia: bool,
    motivo_sin_match: Optional[str],
    canal_origen: str,
    has_attachments: bool,
) -> Optional[str]:
    """
    Persiste el resultado del matching en hilos_ingest_log.
    Retorna el UUID del registro o None si falla.
    Nunca lanza excepción — Supabase es fuente de verdad pero no bloquea el response.
    """
    if not _sb:
        return None
    try:
        resp = _sb.table("hilos_ingest_log").insert({
            "message_id":       message_id,
            "thread_id":        thread_id,
            "from_email":       from_email,
            "subject":          subject[:500] if subject else "",
            "received_at":      received_at,
            "match_strategy":   strategy,
            "tramite_twenty_id": tramite_id,
            "agente_twenty_id": agente_id,
            "hilo_twenty_id":   hilo_id,
            "requiere_accion":  requiere_accion,
            "match_confianza":  confianza,
            "urgencia_detectada": urgencia,
            "motivo_sin_match": motivo_sin_match,
            "canal_origen":     canal_origen,
            "tiene_adjuntos":   has_attachments,
        }).execute()
        rows = resp.data or []
        return rows[0].get("id") if rows else None
    except Exception as exc:
        logger.warning(f"[email_ingest] hilos_ingest_log insert failed: {exc}")
        return None


def _update_tramites_pipeline_thread(
    thread_id: str,
    twenty_tramite_id: str,
    message_id: str,
    from_email: str,
    subject: str,
) -> None:
    """Actualiza o registra la asociación thread_id → tramite en tramites_pipeline."""
    if not _sb:
        return
    try:
        # Verificar si ya existe
        resp = (
            _sb.table("tramites_pipeline")
            .select("id, twenty_tramite_id")
            .eq("thread_id", thread_id)
            .limit(1)
            .execute()
        )
        existing = (resp.data or [])
        if existing and not existing[0].get("twenty_tramite_id"):
            # Existe pero sin tramite vinculado — actualizar
            _sb.table("tramites_pipeline").update(
                {"twenty_tramite_id": twenty_tramite_id, "status": "hilo_matched"}
            ).eq("thread_id", thread_id).execute()
        elif not existing:
            # No existe — crear registro de seguimiento
            _sb.table("tramites_pipeline").insert({
                "thread_id":         thread_id,
                "message_id":        message_id,
                "status":            "hilo_matched",
                "canal_ingreso":     "Correo",
                "correo_remitente":  from_email,
                "correo_asunto":     subject[:500] if subject else "",
                "twenty_tramite_id": twenty_tramite_id,
            }).execute()
    except Exception as exc:
        logger.warning(f"[email_ingest] tramites_pipeline update failed: {exc}")


# ── Estrategias de matching ────────────────────────────────────────────────────

async def _match_by_thread_id(thread_id: str) -> Optional[dict]:
    """
    Estrategia 1: Busca HiloConversacion existente por threadExternalId en Twenty.
    Es la ruta más rápida y precisa — el hilo ya fue clasificado antes.
    Retorna el nodo de HiloConversacion (con tramiteId si está vinculado) o None.
    """
    return await twenty_sync.buscar_hilo_por_thread_id(thread_id)


async def _match_by_reply_headers(
    in_reply_to: str,
    references: list[str],
) -> Optional[str]:
    """
    Estrategia 2: Busca en tramites_pipeline por el message_id original
    que está referenciado en los headers In-Reply-To / References.
    Retorna twenty_tramite_id o None.
    """
    if not _sb:
        return None

    candidate_ids = []
    if in_reply_to:
        # Limpiar los delimitadores <...> si los hay
        clean = in_reply_to.strip().strip("<>")
        if clean:
            candidate_ids.append(clean)
    for ref in references:
        clean = ref.strip().strip("<>")
        if clean and clean not in candidate_ids:
            candidate_ids.append(clean)

    if not candidate_ids:
        return None

    try:
        resp = (
            _sb.table("tramites_pipeline")
            .select("twenty_tramite_id")
            .in_("message_id", candidate_ids)
            .not_.is_("twenty_tramite_id", "null")
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if rows:
            tramite_id = rows[0].get("twenty_tramite_id")
            if tramite_id:
                logger.info(f"[email_ingest] match_reply_headers → tramite={tramite_id}")
                return tramite_id
    except Exception as exc:
        logger.warning(f"[email_ingest] reply_headers lookup failed: {exc}")

    return None


async def _match_by_folio(search_text: str) -> Optional[str]:
    """
    Estrategia 3: Extrae folio interno (TRM-YYYY-NNNNN) del texto y busca en Twenty.
    Retorna twenty_tramite_id o None.
    """
    folio = _extraer_folio(search_text)
    if not folio:
        return None
    tramite = await twenty_sync.buscar_tramite_por_folio(folio)
    if tramite:
        logger.info(f"[email_ingest] match_folio '{folio}' → tramite={tramite['id']}")
        return tramite["id"]
    return None


async def _match_by_poliza(search_text: str) -> Optional[str]:
    """
    Estrategia 4: Extrae número de póliza del texto y busca en Twenty.
    Retorna twenty_tramite_id o None.
    """
    poliza = _extraer_poliza(search_text)
    if not poliza:
        return None
    tramite = await twenty_sync.buscar_tramite_por_poliza(poliza)
    if tramite:
        logger.info(f"[email_ingest] match_poliza '{poliza}' → tramite={tramite['id']}")
        return tramite["id"]
    return None


async def _match_by_agente_tramites(
    from_email: str,
    subject: str,
    body_text: str,
) -> tuple[Optional[str], Optional[str], int, str]:
    """
    Estrategia 5: Busca al agente por email y sus trámites activos.
    Si hay exactamente 1 trámite activo → auto-vincular (confianza 90).
    Si hay varios → LLM desambigua (umbral de confianza 80).

    Retorna: (tramite_id | None, agente_id | None, confianza 0-100, método).
    """
    agente_id = await _buscar_agente_por_email(from_email)
    if not agente_id:
        return None, None, 0, "agente_not_found"

    tramites = await twenty_sync.buscar_tramites_activos_por_agente(agente_id)
    if not tramites:
        logger.info(f"[email_ingest] Agente {agente_id} encontrado pero sin trámites activos")
        return None, agente_id, 0, "agente_sin_tramites_activos"

    if len(tramites) == 1:
        tramite_id = tramites[0]["id"]
        logger.info(
            f"[email_ingest] match_agente_single tramite={tramite_id} "
            f"(folio={tramites[0].get('folioInterno')})"
        )
        return tramite_id, agente_id, 90, "agente_single_tramite"

    # Múltiples trámites — desambiguación por LLM
    tramite_id, confianza = await _llm_disambiguate(tramites, subject, body_text)
    if tramite_id and confianza >= 80:
        logger.info(
            f"[email_ingest] match_llm_disambig tramite={tramite_id} confianza={confianza}"
        )
        return tramite_id, agente_id, confianza, "llm_disambig"

    # LLM no alcanzó umbral — cola manual, pero sí tenemos al agente
    return None, agente_id, confianza, "llm_disambig_low_confidence"


async def _llm_disambiguate(
    tramites: list[dict],
    subject: str,
    body_text: str,
) -> tuple[Optional[str], int]:
    """
    Usa Claude/GPT para identificar cuál de los trámites activos corresponde al email.
    Retorna (tramite_id | None, confianza 0-100).
    Absorbe errores del LLM — nunca propaga excepción.
    """
    tramites_summary = [
        {
            "id":           t.get("id"),
            "folio":        t.get("folioInterno", ""),
            "tipo":         t.get("tipoTramite", ""),
            "ramo":         t.get("ramo", ""),
            "estado":       t.get("estadoTramite", ""),
            "num_poliza":   t.get("numPolizaGnp", ""),
            "asegurado":    t.get("nombreAsegurado", ""),
            "fecha_entrada": t.get("fechaEntrada", ""),
        }
        for t in tramites[:20]  # Limitar para no exceder contexto
    ]

    prompt = (
        "Eres un asistente de clasificación para una promotoría de seguros mexicana.\n\n"
        f"Se recibió este email:\n"
        f"  Asunto: {subject}\n"
        f"  Cuerpo (primeros 800 caracteres): {body_text[:800]}\n\n"
        f"El agente tiene estos trámites activos:\n"
        f"{json.dumps(tramites_summary, ensure_ascii=False, indent=2)}\n\n"
        "¿A cuál de estos trámites hace referencia el email?\n"
        "Responde con el UUID del tramite_id si la confianza >= 80, "
        "o null si no puedes determinarlo con esa certeza."
    )

    try:
        llm_resp = await litellm.acompletion(
            model=LLM_MODEL,
            response_format=_TramiteMatch,
            messages=[{"role": "user", "content": prompt}],
            timeout=25,
        )
        raw = llm_resp.choices[0].message.content or "{}"
        result = _TramiteMatch.model_validate_json(raw)
        logger.info(
            f"[email_ingest] LLM disambig: tramite_id={result.tramite_id} "
            f"confidence={result.confidence} razon={result.razon!r}"
        )
        return result.tramite_id, result.confidence
    except Exception as exc:
        logger.warning(f"[email_ingest] LLM disambiguate failed: {exc}")
        return None, 0


# ── Orquestador principal ──────────────────────────────────────────────────────

async def _run_matching_pipeline(req: EmailIngestRequest) -> dict:
    """
    Ejecuta el pipeline de matching en orden de precisión.
    Retorna un dict con: strategy, tramite_id, agente_id, confianza, requiere_accion, motivo.
    """
    search_text = _build_search_text(req.subject, req.body_text, req.body_html)

    # ── Estrategia 1: Hilo ya conocido en Twenty ─────────────────────────────
    existing_hilo = await _match_by_thread_id(req.thread_id)
    if existing_hilo:
        tramite_id = existing_hilo.get("tramiteId") or existing_hilo.get("tramite", {}).get("id")
        agente_id  = existing_hilo.get("agenteId") or existing_hilo.get("agente", {}).get("id")
        return {
            "strategy":       "thread_id_known",
            "hilo_id":        existing_hilo.get("id"),
            "tramite_id":     tramite_id,
            "agente_id":      agente_id,
            "confianza":      100,
            "requiere_accion": not bool(tramite_id),
            "motivo_sin_match": None,
        }

    # ── Estrategia 2: Reply headers ──────────────────────────────────────────
    tramite_id = await _match_by_reply_headers(req.in_reply_to, req.references)
    if tramite_id:
        return {
            "strategy":        "reply_headers",
            "hilo_id":         None,
            "tramite_id":      tramite_id,
            "agente_id":       None,
            "confianza":       95,
            "requiere_accion": False,
            "motivo_sin_match": None,
        }

    # ── Estrategia 3: Folio interno en texto ────────────────────────────────
    tramite_id = await _match_by_folio(search_text)
    if tramite_id:
        return {
            "strategy":        "folio_regex",
            "hilo_id":         None,
            "tramite_id":      tramite_id,
            "agente_id":       None,
            "confianza":       98,
            "requiere_accion": False,
            "motivo_sin_match": None,
        }

    # ── Estrategia 4: Número de póliza en texto ──────────────────────────────
    tramite_id = await _match_by_poliza(search_text)
    if tramite_id:
        return {
            "strategy":        "poliza_regex",
            "hilo_id":         None,
            "tramite_id":      tramite_id,
            "agente_id":       None,
            "confianza":       92,
            "requiere_accion": False,
            "motivo_sin_match": None,
        }

    # ── Estrategia 5: Agente por email → tramites activos ───────────────────
    tramite_id, agente_id, confianza, sub_method = await _match_by_agente_tramites(
        req.from_email, req.subject, req.body_text
    )

    if tramite_id:
        return {
            "strategy":        f"agente_tramites:{sub_method}",
            "hilo_id":         None,
            "tramite_id":      tramite_id,
            "agente_id":       agente_id,
            "confianza":       confianza,
            "requiere_accion": False,
            "motivo_sin_match": None,
        }

    # ── Estrategia 6: Cola manual ────────────────────────────────────────────
    motivos = []
    if not agente_id:
        motivos.append(f"Remitente {req.from_email!r} no está registrado como agente en el CRM")
    elif sub_method == "agente_sin_tramites_activos":
        motivos.append(f"El agente (id={agente_id}) no tiene trámites activos")
    elif sub_method == "llm_disambig_low_confidence":
        motivos.append(
            f"El agente tiene múltiples trámites activos pero el LLM no alcanzó confianza "
            f"suficiente (obtuvo {confianza}/80)"
        )

    return {
        "strategy":        "manual_queue",
        "hilo_id":         None,
        "tramite_id":      None,
        "agente_id":       agente_id,
        "confianza":       confianza,
        "requiere_accion": True,
        "motivo_sin_match": "; ".join(motivos) if motivos else "No se pudo determinar el trámite",
    }


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post(
    "/email/ingest",
    response_model=EmailIngestResponse,
    summary="Ingestar email y matchear con HiloConversacion → Trámite",
    description=(
        "Recibe un email procesado por n8n, ejecuta el pipeline de matching "
        "para vincularlo a un HiloConversacion y Trámite en Twenty CRM, "
        "y persiste el resultado en Supabase."
    ),
)
async def ingest_email(req: EmailIngestRequest) -> EmailIngestResponse:
    logger.info(
        f"[email_ingest] Procesando message_id={req.message_id!r} "
        f"thread_id={req.thread_id!r} from={req.from_email!r} subject={req.subject[:80]!r}"
    )

    urgencia = _detectar_urgencia(req.subject, req.body_text)
    ultimo_remitente = _determinar_ultimo_remitente(req.from_email)

    # ── 1. Ejecutar pipeline de matching ────────────────────────────────────
    match = await _run_matching_pipeline(req)

    strategy      = match["strategy"]
    tramite_id    = match["tramite_id"]
    agente_id     = match["agente_id"]
    confianza     = match["confianza"]
    requiere      = match["requiere_accion"]
    motivo        = match["motivo_sin_match"]
    existing_hilo_id = match["hilo_id"]

    # ── 2. Crear o actualizar HiloConversacion en Twenty ────────────────────
    hilo_id: Optional[str] = existing_hilo_id

    if existing_hilo_id:
        # Hilo ya existía — solo actualizar contadores y timestamps
        await twenty_sync.actualizar_hilo_conversacion(
            hilo_id=existing_hilo_id,
            ultimo_mensaje_en=req.received_at,
            ultimo_remitente=ultimo_remitente,
            incrementar_mensajes=True,
            requiere_accion=requiere or None,  # None = no cambiar si ya estaba resuelto
            tramite_id=tramite_id,             # vincular si ahora lo tenemos
        )
    else:
        # Hilo nuevo — crear en Twenty
        hilo_id = await twenty_sync.crear_hilo_conversacion(
            asunto=req.subject[:500] if req.subject else "(sin asunto)",
            thread_external_id=req.thread_id,
            canal_origen=req.canal_origen,
            ultimo_mensaje_en=req.received_at,
            ultimo_remitente=ultimo_remitente,
            mensajes_count=1,
            requiere_accion=requiere,
            tramite_id=tramite_id,
            agente_id=agente_id,
        )

    # ── 3. Si hay urgencia y tramite, escalar prioridad en Twenty ───────────
    if urgencia and tramite_id:
        await twenty_sync.escalar_prioridad_tramite(tramite_id, motivo="Urgencia detectada en email")

    # ── 4. Actualizar tramites_pipeline en Supabase ──────────────────────────
    if tramite_id:
        _update_tramites_pipeline_thread(
            thread_id=req.thread_id,
            twenty_tramite_id=tramite_id,
            message_id=req.message_id,
            from_email=req.from_email,
            subject=req.subject,
        )

    # ── 5. Log de auditoría ──────────────────────────────────────────────────
    ingest_log_id = _log_ingest(
        message_id=req.message_id,
        thread_id=req.thread_id,
        from_email=req.from_email,
        subject=req.subject,
        received_at=req.received_at,
        strategy=strategy,
        tramite_id=tramite_id,
        agente_id=agente_id,
        hilo_id=hilo_id,
        requiere_accion=requiere,
        confianza=confianza,
        urgencia=urgencia,
        motivo_sin_match=motivo,
        canal_origen=req.canal_origen,
        has_attachments=req.has_attachments,
    )

    logger.info(
        f"[email_ingest] Completado message_id={req.message_id!r} "
        f"strategy={strategy} tramite={tramite_id} hilo={hilo_id} "
        f"confianza={confianza} requiere_accion={requiere} urgencia={urgencia}"
    )

    return EmailIngestResponse(
        message_id=req.message_id,
        thread_id=req.thread_id,
        strategy=strategy,
        tramite_id=tramite_id,
        agente_id=agente_id,
        hilo_id=hilo_id,
        requiere_accion=requiere,
        confianza=confianza,
        urgencia_detectada=urgencia,
        motivo_sin_match=motivo,
        ingest_log_id=ingest_log_id,
    )
