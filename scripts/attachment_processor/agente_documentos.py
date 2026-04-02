"""
Agente 3 — Extracción y clasificación de documentos adjuntos.

Endpoint: POST /api/v1/agentes/documentos

Por cada documento (de attachments_log):
  1. Descarga el archivo desde Supabase Storage
  2. Extrae texto: pdfplumber (PDF con texto) → OCR RunPod (PDF escaneado / imagen)
                   o lectura directa (XML, texto plano)
  3. Clasifica con LiteLLM (GPT-4o por defecto) → JSON estructurado
  4. Persiste en attachments_log (Supabase)
  5. Actualiza objeto Documento en Twenty CRM si twenty_documento_id ya existe
"""
import asyncio
import base64
import json
import logging
import os
import time
from datetime import datetime
from io import BytesIO
from typing import Optional

import httpx
import litellm
import requests as _requests
from fastapi import APIRouter
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from agent_llm import ocr_con_runpod
from supabase_client import supabase as _sb

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Constants ─────────────────────────────────────────────────────────────────

BUCKET_NAME = os.getenv("BUCKET_NAME", "tramites-docs")
TWENTY_API_URL = os.getenv("TWENTY_API_URL", "http://localhost:3000")
TWENTY_API_KEY = os.getenv("TWENTY_API_KEY", "")

TIPOS_DOCUMENTO = [
    "INE/IFE",
    "Póliza GNP",
    "Formato GNP",
    "Comprobante de domicilio",
    "Comprobante de pago",
    "CFDI/Factura",
    "Acta de nacimiento",
    "Solicitud de seguro",
    "Carta instrucción",
    "Pasaporte",
    "Carnet de salud",
    "Estado de cuenta",
    "Otro",
]

_CLASIFICACION_SYSTEM_PROMPT = """\
Eres un experto en documentación para seguros mexicanos en una promotoría GNP.
Analiza el texto extraído de un documento y determina qué tipo de documento es.

TIPOS VÁLIDOS:
INE/IFE, Póliza GNP, Formato GNP, Comprobante de domicilio,
Comprobante de pago, CFDI/Factura, Acta de nacimiento,
Solicitud de seguro, Carta instrucción, Pasaporte,
Carnet de salud, Estado de cuenta, Otro

Extrae SOLO datos que estén explícitamente en el texto asegurando la estructura JSON requerida.
Si un dato no aparece, usa null. No inventes información."""

# Cache de campos del objeto Documento en Twenty (cargado una vez por proceso)
_twenty_documento_fields: set[str] | None = None


# ── Pydantic models ────────────────────────────────────────────────────────────

class DocumentosRequest(BaseModel):
    tramite_id: str
    documento_ids: list[str] = []

class DatosExtraidos(BaseModel):
    nombre_titular: Optional[str] = Field(None)
    numero_poliza: Optional[str] = Field(None)
    agente_cua: Optional[str] = Field(None)
    rfc: Optional[str] = Field(None)
    curp: Optional[str] = Field(None)
    fecha_emision: Optional[str] = Field(None)
    fecha_vencimiento: Optional[str] = Field(None)
    monto: Optional[float] = Field(None)
    numero_folio: Optional[str] = Field(None)
    nombre_asegurado: Optional[str] = Field(None)
    ramo: Optional[str] = Field(None)

class ClasificacionDocumento(BaseModel):
    tipo_documento: str = Field(description="Uno de los tipos válidos (ej. INE/IFE, Póliza GNP, etc)")
    confidence: int = Field(description="Nivel de confianza en la clasificación (0-100)")
    datos_extraidos: DatosExtraidos
    resumen_documento: str = Field(description="Breve descripción de una oración sobre el documento")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _truncate_texto(texto: str, max_chars: int = 15000) -> str:
    """Keep first half + last half chars for long documents."""
    if len(texto) <= max_chars:
        return texto
    half = max_chars // 2
    return texto[:half] + "\n...[texto truncado]...\n" + texto[-half:]


def _extract_pdf_text(contenido_bytes: bytes) -> str:
    """Extract embedded text from a PDF using pdfplumber (sync)."""
    import pdfplumber  # lazy import — not always needed

    with pdfplumber.open(BytesIO(contenido_bytes)) as pdf:
        partes = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                partes.append(t)
    return "\n".join(partes).strip()


def _get_pending_documentos(tramite_id: str) -> list[dict]:
    """Fetch all unclassified attachment records for a tramite."""
    if not _sb:
        return []
    resp = (
        _sb.table("attachments_log")
        .select("id, nombre, storage_path, mime_type")
        .eq("tramite_id", tramite_id)
        .eq("clasificacion_completada", False)
        .execute()
    )
    return resp.data or []


def _get_documento_by_id(doc_id: str) -> dict | None:
    """Fetch a single attachment record by id."""
    if not _sb:
        return None
    resp = (
        _sb.table("attachments_log")
        .select("id, nombre, storage_path, mime_type, twenty_documento_id")
        .eq("id", doc_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def _mark_error(doc_id: str, error_msg: str) -> None:
    """Mark a document as failed in Supabase."""
    if not _sb:
        return
    try:
        _sb.table("attachments_log").update({
            "clasificacion_completada": False,
            "error_detalle": error_msg[:500],
        }).eq("id", doc_id).execute()
    except Exception as exc:
        logger.warning(f"Could not mark error for doc {doc_id}: {exc}")


def _save_resultado(
    doc_id: str,
    tipo_documento: str,
    texto_extraido: str,
    datos_extraidos: dict,
    metodo_extraccion: str,
) -> None:
    """Persist classification result to attachments_log."""
    if not _sb:
        return
    _sb.table("attachments_log").update({
        "tipo_documento":            tipo_documento,
        "texto_extraido":            texto_extraido[:10_000] if texto_extraido else "",
        "datos_extraidos":           datos_extraidos,
        "metodo_extraccion":         metodo_extraccion,
        "ocr_completado":            metodo_extraccion == "ocr_runpod",
        "clasificacion_completada":  True,
        "error_detalle":             None,
        "procesado_at":              datetime.utcnow().isoformat(),
    }).eq("id", doc_id).execute()


# ── Twenty CRM helpers ─────────────────────────────────────────────────────────

async def _get_twenty_documento_fields() -> set[str]:
    """
    Introspect Twenty Metadata API to get valid field names for the
    'documento' object. Cached after first call.
    """
    global _twenty_documento_fields
    if _twenty_documento_fields is not None:
        return _twenty_documento_fields

    if not TWENTY_API_KEY:
        _twenty_documento_fields = set()
        return _twenty_documento_fields

    introspect_query = """
    query GetDocumentoFields {
      objects(filter: { nameSingular: { eq: "documento" } }) {
        edges {
          node {
            nameSingular
            fields {
              edges {
                node {
                  name
                  type
                }
              }
            }
          }
        }
      }
    }
    """
    headers = {
        "Authorization": f"Bearer {TWENTY_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{TWENTY_API_URL}/metadata",
                json={"query": introspect_query},
                headers=headers,
            )
            resp.raise_for_status()
            body = resp.json()

        edges = (
            body.get("data", {})
            .get("objects", {})
            .get("edges", [])
        )
        if not edges:
            logger.warning("Twenty: objeto 'documento' no encontrado en metadata")
            _twenty_documento_fields = set()
            return _twenty_documento_fields

        field_edges = (
            edges[0].get("node", {})
            .get("fields", {})
            .get("edges", [])
        )
        _twenty_documento_fields = {
            e["node"]["name"]
            for e in field_edges
            if e.get("node", {}).get("name")
        }
        logger.info(f"Twenty documento fields: {_twenty_documento_fields}")
    except Exception as exc:
        logger.warning(f"Twenty metadata introspection failed: {exc}")
        _twenty_documento_fields = set()

    return _twenty_documento_fields


async def _update_twenty_documento(
    twenty_documento_id: str,
    tipo_documento: str,
    datos_extraidos: dict,
    resumen_documento: str,
) -> bool:
    """
    Update a Documento object in Twenty CRM if the fields exist.
    Only updates fields confirmed via metadata introspection.
    """
    if not TWENTY_API_KEY or not twenty_documento_id:
        return False

    valid_fields = await _get_twenty_documento_fields()
    if not valid_fields:
        logger.warning("Skipping Twenty update — no valid documento fields found")
        return False

    # Build update data only with fields that exist in Twenty
    update_data: dict = {}
    field_map = {
        "tipoDocumento":     tipo_documento,
        "nombreTitular":     (datos_extraidos or {}).get("nombre_titular"),
        "numeroPoliza":      (datos_extraidos or {}).get("numero_poliza"),
        "resumenDocumento":  resumen_documento,
    }
    for field_name, value in field_map.items():
        if field_name in valid_fields and value is not None:
            update_data[field_name] = value

    if not update_data:
        logger.info(
            f"Twenty documento {twenty_documento_id}: no matching fields to update"
        )
        return False

    # Build dynamic mutation with only the fields we know exist
    fields_str = " ".join(update_data.keys())
    mutation = f"""
    mutation UpdateDocumento($id: ID!, $data: DocumentoUpdateInput!) {{
      updateDocumento(id: $id, data: $data) {{
        id
        {fields_str}
      }}
    }}
    """
    headers = {
        "Authorization": f"Bearer {TWENTY_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{TWENTY_API_URL}/api",
                json={"query": mutation, "variables": {
                    "id": twenty_documento_id,
                    "data": update_data,
                }},
                headers=headers,
            )
            resp.raise_for_status()
            body = resp.json()
            if body.get("errors"):
                logger.warning(
                    f"Twenty updateDocumento errors: {body['errors']}"
                )
                return False
        logger.info(
            f"Twenty documento {twenty_documento_id} actualizado: {list(update_data.keys())}"
        )
        return True
    except Exception as exc:
        logger.warning(f"Twenty updateDocumento failed: {exc}")
        return False


# ── LLM classification ─────────────────────────────────────────────────────────

async def _clasificar_documento(texto: str) -> dict:
    """
    Send extracted text to LiteLLM for classification.
    Returns parsed JSON dict with tipo_documento, datos_extraidos, etc.
    """
    llm_model = os.environ.get("LLM_MODEL", "openai/gpt-4o")
    texto_truncado = _truncate_texto(texto)
    messages = [
        {"role": "system", "content": _CLASIFICACION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Texto del documento:\n\n{texto_truncado}"},
    ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _call() -> str:
        resp = await litellm.acompletion(
            model=llm_model,
            response_format=ClasificacionDocumento,
            messages=messages,
            timeout=30,
        )
        return resp.choices[0].message.content or ""

    try:
        raw = await _call()
        parsed = ClasificacionDocumento.model_validate_json(raw)
        return parsed.model_dump()
    except Exception as exc:
        logger.warning(f"clasificar_documento final error after retries: {exc}")
        # Fallback dictionary if all parsing fails
        return {
            "tipo_documento": "Otro",
            "confidence": 0,
            "datos_extraidos": {},
            "resumen_documento": "Error de clasificación."
        }


# ── Core processing pipeline ───────────────────────────────────────────────────

async def _procesar_documento(doc: dict) -> dict:
    """
    Full pipeline for one document. Returns a result dict.
    Raises on unrecoverable errors — caller handles per-doc try/except.
    """
    doc_id       = doc["id"]
    nombre       = doc.get("nombre", "")
    storage_path = doc.get("storage_path", "")
    mime_type    = (doc.get("mime_type") or "application/octet-stream").lower()
    twenty_doc_id = doc.get("twenty_documento_id")

    # 1. Download from Supabase Storage
    contenido_bytes: bytes = _sb.storage.from_(BUCKET_NAME).download(storage_path)
    if not contenido_bytes:
        raise ValueError(f"Archivo vacío o no encontrado: {storage_path}")

    # 2. Extract text based on mime type
    metodo_extraccion: str
    texto_extraido: str

    if mime_type == "application/pdf":
        # Try embedded text first
        try:
            texto_pdf = await asyncio.to_thread(_extract_pdf_text, contenido_bytes)
        except Exception as exc:
            logger.warning(f"pdfplumber error en {nombre}: {exc}")
            texto_pdf = ""

        if len(texto_pdf) >= 100:
            metodo_extraccion = "pdf_texto"
            texto_extraido = texto_pdf
        else:
            # Scanned PDF → OCR
            texto_extraido = await asyncio.to_thread(
                ocr_con_runpod, contenido_bytes, mime_type
            )
            metodo_extraccion = "ocr_runpod"

    elif mime_type in ("image/jpeg", "image/jpg", "image/png", "image/tiff", "image/webp"):
        texto_extraido = await asyncio.to_thread(
            ocr_con_runpod, contenido_bytes, mime_type
        )
        metodo_extraccion = "ocr_runpod"

    elif mime_type in ("application/xml", "text/xml"):
        texto_extraido = contenido_bytes.decode("utf-8", errors="replace")
        metodo_extraccion = "xml_texto"

    elif mime_type.startswith("text/"):
        texto_extraido = contenido_bytes.decode("utf-8", errors="replace")
        metodo_extraccion = "texto_plano"

    else:
        raise ValueError(f"formato no soportado: {mime_type}")

    if not texto_extraido.strip():
        raise ValueError("No se pudo extraer texto del documento")

    # 3. Classify with LLM
    clasificacion = await _clasificar_documento(texto_extraido)

    tipo_documento    = clasificacion.get("tipo_documento", "Otro")
    datos_extraidos   = clasificacion.get("datos_extraidos", {})
    resumen_documento = clasificacion.get("resumen_documento", "")

    # 4. Persist to Supabase
    await asyncio.to_thread(
        _save_resultado,
        doc_id, tipo_documento, texto_extraido, datos_extraidos, metodo_extraccion,
    )

    # 5. Update Twenty CRM if twenty_documento_id is set
    if twenty_doc_id:
        await _update_twenty_documento(
            twenty_doc_id, tipo_documento, datos_extraidos, resumen_documento
        )
    else:
        logger.info(
            f"Doc {doc_id} ({nombre}): sin twenty_documento_id — "
            "Twenty se actualizará cuando el Agente 4 cree el trámite"
        )

    return {
        "documento_id":           doc_id,
        "nombre":                 nombre,
        "tipo_documento":         tipo_documento,
        "metodo_extraccion":      metodo_extraccion,
        "datos_extraidos":        datos_extraidos,
        "clasificacion_completada": True,
    }


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/documentos")
async def agente_documentos(data: DocumentosRequest):
    """
    Agente 3 — Extracción y clasificación de adjuntos.

    Si documento_ids está vacío → procesa todos los pendientes del tramite.
    Cada documento se procesa de forma independiente:
      un error en uno no detiene los demás.
    """
    logger.info(
        f"agente_documentos tramite_id={data.tramite_id!r} "
        f"doc_ids={data.documento_ids or '(todos pendientes)'}"
    )

    if not _sb:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Supabase no configurado")

    # Resolve document list
    if data.documento_ids:
        docs = []
        for doc_id in data.documento_ids:
            doc = await asyncio.to_thread(_get_documento_by_id, doc_id)
            if doc:
                docs.append(doc)
            else:
                logger.warning(f"Doc id {doc_id!r} no encontrado en attachments_log")
    else:
        docs = await asyncio.to_thread(_get_pending_documentos, data.tramite_id)

    if not docs:
        return {
            "tramite_id":              data.tramite_id,
            "documentos_procesados":   0,
            "documentos_con_error":    0,
            "resultados":              [],
            "errores":                 [],
        }

    resultados: list[dict] = []
    errores: list[dict] = []

    for doc in docs:
        doc_id = doc.get("id", "?")
        nombre = doc.get("nombre", "?")
        try:
            result = await _procesar_documento(doc)
            resultados.append(result)
            logger.info(
                f"Doc {doc_id} ({nombre}) → "
                f"{result['tipo_documento']} [{result['metodo_extraccion']}]"
            )
        except ValueError as exc:
            # Known unsupported formats or empty files — mark and continue
            msg = str(exc)
            logger.warning(f"Doc {doc_id} ({nombre}) ValueError: {msg}")
            await asyncio.to_thread(_mark_error, doc_id, msg)
            errores.append({"documento_id": doc_id, "nombre": nombre, "error": msg})

        except Exception as exc:
            msg = str(exc)
            logger.error(f"Doc {doc_id} ({nombre}) error: {msg}", exc_info=True)
            await asyncio.to_thread(_mark_error, doc_id, msg)
            errores.append({"documento_id": doc_id, "nombre": nombre, "error": msg})

    return {
        "tramite_id":              data.tramite_id,
        "documentos_procesados":   len(resultados),
        "documentos_con_error":    len(errores),
        "resultados":              resultados,
        "errores":                 errores,
    }
