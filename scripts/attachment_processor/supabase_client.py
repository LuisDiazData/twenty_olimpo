import os
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # service role para bypass de RLS
BUCKET_NAME  = os.getenv("BUCKET_NAME", "tramites-docs")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Warning: Supabase client not initialized: {e}")
    supabase = None


# ─── Storage ──────────────────────────────────────────────────────────────────

def upload_file(email_id: str, filename: str, file_bytes: bytes,
                content_type: str = "application/octet-stream") -> str:
    """
    Uploads a file to Supabase Storage.
    Storage path: {email_id}/{clean_filename}
    """
    if not supabase:
        print("Supabase not configured. Skipping upload.")
        return ""

    clean_filename = filename.replace(" ", "_").replace("/", "_")
    storage_path = f"{email_id}/{clean_filename}"

    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )
        return storage_path
    except Exception as e:
        print(f"Error uploading {filename} to Supabase: {e}")
        return ""


def upload_file_to_path(storage_path: str, file_bytes: bytes,
                        content_type: str = "application/octet-stream") -> str:
    """
    Uploads bytes to an exact storage path in the bucket (no sanitization).
    Used for inline images: {email_id}/inline/inline_001.jpg
    """
    if not supabase:
        return ""

    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )
        return storage_path
    except Exception as e:
        print(f"Error uploading to path {storage_path}: {e}")
        return ""


# ─── Logging ──────────────────────────────────────────────────────────────────

def log_attachment_processing(email_id: str, total_received: int,
                               successful_processed: int, file_paths: list[str]):
    """Insert one record into attachments_log for a batch of regular attachments."""
    if not supabase:
        return

    data = {
        "email_id": email_id,
        "bucket_id": BUCKET_NAME,
        "total_attachments": total_received,
        "successful_attachments": successful_processed,
        "file_paths": file_paths,
        "es_inline": False,
    }
    try:
        response = supabase.table("attachments_log").insert(data).execute()
        print(f"Logged attachments for email {email_id}. Count: {successful_processed}")
    except Exception as e:
        print(f"Error logging to attachments_log: {e}")


def log_inline_images(email_id: str, images: list[dict]):
    """
    Insert one record per inline image into attachments_log.
    Each dict in `images` must have: storage_path, mime_type, tamano_bytes.
    """
    if not supabase or not images:
        return

    rows = [
        {
            "email_id": email_id,
            "bucket_id": BUCKET_NAME,
            "total_attachments": 1,
            "successful_attachments": 1,
            "file_paths": [img["storage_path"]],
            "es_inline": True,
            "mime_type": img.get("mime_type", "image/jpeg"),
        }
        for img in images
    ]
    try:
        supabase.table("attachments_log").insert(rows).execute()
        print(f"Logged {len(rows)} inline image(s) for email {email_id}")
    except Exception as e:
        print(f"Error logging inline images: {e}")


# ─── Reply detection ──────────────────────────────────────────────────────────

_CLOSED_STATUSES = {"cerrado", "cancelado"}


def check_existing_thread(thread_id: str) -> dict:
    """
    Check if thread_id has an active tramite in tramites_pipeline.
    Returns {found, tramite_pipeline_id, twenty_tramite_id, status}.
    """
    if not supabase or not thread_id:
        return {"found": False}

    try:
        resp = (
            supabase.table("tramites_pipeline")
            .select("id, status, twenty_tramite_id")
            .eq("thread_id", thread_id)
            .not_.in_("status", list(_CLOSED_STATUSES))
            .limit(1)
            .execute()
        )
        records = resp.data or []
        if not records:
            return {"found": False}

        rec = records[0]
        return {
            "found": True,
            "tramite_pipeline_id": rec.get("id"),
            "twenty_tramite_id": rec.get("twenty_tramite_id"),
            "status": rec.get("status"),
        }
    except Exception as e:
        print(f"Error checking thread {thread_id}: {e}")
        return {"found": False}


# ── Per-document logging (1:1 con documentoAdjunto en Twenty) ─────────────────

def log_attachment_individual(
    email_id: str,
    tramite_id: str,
    nombre: str,
    storage_path: str,
    mime_type: str,
    tamano_bytes: int,
    was_encrypted: bool = False,
    decryption_successful: bool = True,
) -> str | None:
    """
    Inserta un registro individual en attachments_log por documento.
    A diferencia de log_attachment_processing (batch), este es 1:1.
    Retorna el UUID del nuevo registro o None si falla.
    """
    if not supabase:
        return None

    data = {
        "email_id":              email_id,
        "tramite_id":            tramite_id,
        "nombre":                nombre,
        "storage_path":          storage_path,
        "mime_type":             mime_type,
        "tamano_bytes":          tamano_bytes,
        "was_encrypted":         was_encrypted,
        "decryption_successful": decryption_successful,
        "bucket_id":             BUCKET_NAME,
        "clasificacion_completada": False,
        "ocr_completado":        False,
        "es_inline":             False,
    }
    try:
        resp = supabase.table("attachments_log").insert(data).execute()
        rows = resp.data or []
        doc_id = rows[0].get("id") if rows else None
        if doc_id:
            print(f"log_attachment_individual: {nombre} → {doc_id}")
        return doc_id
    except Exception as e:
        print(f"Error en log_attachment_individual para {nombre}: {e}")
        return None


def update_twenty_documento_id(doc_id: str, twenty_documento_id: str) -> None:
    """
    Actualiza twenty_documento_id en attachments_log después de crear
    el documentoAdjunto en Twenty CRM.
    """
    if not supabase or not doc_id or not twenty_documento_id:
        return
    try:
        supabase.table("attachments_log").update(
            {"twenty_documento_id": twenty_documento_id}
        ).eq("id", doc_id).execute()
    except Exception as e:
        print(f"Error actualizando twenty_documento_id para {doc_id}: {e}")


# Cache para get_tipo_documento_map (TTL 5 min, evita round-trips repetidos)
_tipo_doc_map_cache: dict[str, str] = {}
_tipo_doc_map_ttl: object = None  # datetime


def get_tipo_documento_map() -> dict[str, str]:
    """
    Carga el mapeo etiqueta_ia → clave_twenty desde tipo_documento_config.
    Cache in-process de 5 minutos.
    Retorna {} si Supabase no está disponible.
    """
    global _tipo_doc_map_cache, _tipo_doc_map_ttl
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    if _tipo_doc_map_ttl and now < _tipo_doc_map_ttl and _tipo_doc_map_cache:
        return _tipo_doc_map_cache

    if not supabase:
        return _tipo_doc_map_cache  # retorna último cache aunque esté vencido

    try:
        resp = (
            supabase.table("tipo_documento_config")
            .select("etiqueta_ia, clave_twenty")
            .eq("activo", True)
            .execute()
        )
        rows = resp.data or []
        _tipo_doc_map_cache = {r["etiqueta_ia"]: r["clave_twenty"] for r in rows}
        _tipo_doc_map_ttl = now + timedelta(minutes=5)
    except Exception as e:
        print(f"Error cargando tipo_documento_config: {e}")

    return _tipo_doc_map_cache


def save_reply_record(thread_id: str, message_id: str,
                      twenty_tramite_id: str | None = None,
                      email_from: str = "",
                      email_subject: str = "") -> str | None:
    """
    Insert a reply record in tramites_pipeline with status='reply_adjuntado'.
    Returns the new record id, or None on failure.
    """
    if not supabase:
        return None

    data = {
        "thread_id": thread_id,
        "message_id": message_id,
        "status": "reply_adjuntado",
        "canal_ingreso": "Correo",
        "correo_remitente": email_from,
        "correo_asunto": email_subject,
    }
    if twenty_tramite_id:
        data["twenty_tramite_id"] = twenty_tramite_id

    try:
        resp = supabase.table("tramites_pipeline").insert(data).execute()
        records = resp.data or []
        return records[0].get("id") if records else None
    except Exception as e:
        print(f"Error saving reply record for thread {thread_id}: {e}")
        return None
