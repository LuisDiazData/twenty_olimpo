import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://aczkvxveenycpnwyqqbs.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") # This should be a service role key or anon key depending on your setup
BUCKET_NAME = os.getenv("BUCKET_NAME", "tramites-docs")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Warning: Supabase client not initialized: {e}")
    supabase = None

def upload_file(email_id: str, filename: str, file_bytes: bytes) -> str:
    """
    Uploads a file to Supabase Storage in the specified bucket.
    Returns the public URL or the path inside the bucket.
    """
    if not supabase:
        print("Supabase not configured. Skipping upload.")
        return ""
        
    # Standardize filename and create a path
    clean_filename = filename.replace(" ", "_").replace("/", "_")
    storage_path = f"{email_id}/{clean_filename}"
    
    try:
        # Check if bucket exists, conceptually
        res = supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path, 
            file=file_bytes, 
            file_options={"content-type": "application/octet-stream"}
        )
        # We can construct the public URL if needed, or just return path
        return storage_path
    except Exception as e:
        print(f"Error uploading {filename} to Supabase: {e}")
        return ""

def log_attachment_processing(email_id: str, total_received: int, successful_processed: int, file_paths: list[str]):
    """
    Inserts a record into the attachments_log table in Supabase Database.
    """
    if not supabase:
        print("Supabase not configured. Skipping log insert.")
        return

    data = {
        "email_id": email_id,
        "bucket_id": BUCKET_NAME,
        "total_attachments": total_received,
        "successful_attachments": successful_processed,
        "file_paths": file_paths # if using a json/jsonb array column
    }
    
    try:
        response = supabase.table("attachments_log").insert(data).execute()
        print(f"Logged attachments for email {email_id}. Response: {response.data}")
    except Exception as e:
        print(f"Error logging to attachments_log table: {e}")
