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
