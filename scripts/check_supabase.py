import os
import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path="c:/Users/wichi/twenty_olimpo/.env")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "tramites-docs")

print(f"URL: {SUPABASE_URL}")
print(f"Bucket setting: {BUCKET_NAME}")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

tables_to_check = [
    "incoming_emails",
    "email_attachments",
    "dedup_index",
    "ocr_results",
    "ai_processing_log",
    "contact_email_map",
    "procedure_requirements",
    "analyst_metrics_log",
    "tramites_pipeline",
    "cobertura_analistas",
    "historial_asignaciones",
    "pipeline_logs",
    "attachments_log"
]

results = []

for table in tables_to_check:
    resp = httpx.get(f"{SUPABASE_URL}/rest/v1/{table}?select=*&limit=1", headers=headers)
    if resp.status_code == 200:
        results.append(f"Table '{table}' -> EXISTS")
    else:
        results.append(f"Table '{table}' -> FAIL: Status {resp.status_code} - {resp.text}")

print("\n--- TABLE CHECK ---")
print("\n".join(results))

resp_bucket = httpx.get(f"{SUPABASE_URL}/storage/v1/bucket", headers=headers)
if resp_bucket.status_code == 200:
    buckets = resp_bucket.json()
    bucket_names = [b.get("name") for b in buckets]
    if BUCKET_NAME in bucket_names:
        print(f"\n--- BUCKET CHECK ---")
        print(f"Bucket '{BUCKET_NAME}' -> EXISTS")
    else:
        print(f"\n--- BUCKET CHECK ---")
        print(f"Bucket '{BUCKET_NAME}' -> DOES NOT EXIST. Found: {bucket_names}")
else:
    print(f"\n--- BUCKET CHECK ---")
    print(f"FAILED to list buckets: {resp_bucket.status_code} - {resp_bucket.text}")
