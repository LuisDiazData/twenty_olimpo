import os
from fastapi import FastAPI, File, UploadFile, Form
from typing import List, Optional
import uvicorn
from agent_llm import extract_passwords_from_text
from extractor import process_attachments
from supabase_client import upload_file, log_attachment_processing

app = FastAPI(title="Email Attachment Processor API")

@app.post("/process-email")
async def process_email(
    email_id: str = Form(...),
    subject: str = Form(""),
    body: str = Form(""),
    attachments: List[UploadFile] = File(None)
):
    """
    Receives email data and attachments from N8N.
    - Extracts passwords if needed using LLM
    - Decrypts PDFs and extracts ZIPs/RARs
    - Uploads clean files to Supabase
    - Logs results to Supabase DB
    """
    if not attachments:
        return {"status": "success", "message": "No attachments found", "email_id": email_id}
        
    # Read files into memory: list of (filename, bytes)
    raw_files = []
    for f in attachments:
        file_bytes = await f.read()
        raw_files.append((f.filename, file_bytes))

    # A hook to lazily call the LLM only if an encrypted file is found
    def get_passwords(email_text: str):
        return extract_passwords_from_text(email_text)

    # Process attachments (decrypt, unzip, filter sizes)
    # the hook will be called inside process_attachments if password is required
    result = process_attachments(raw_files, body, get_passwords_hook=get_passwords)
    
    files_to_upload = result.get("files_to_upload", [])
    
    # Upload to Supabase 
    uploaded_paths = []
    for filename, file_bytes in files_to_upload:
        path = upload_file(email_id, filename, file_bytes)
        if path:
            uploaded_paths.append(path)
            
    # Log to database
    total_received = result.get("total_received", 0)
    total_successful = len(uploaded_paths)
    log_attachment_processing(email_id, total_received, total_successful, uploaded_paths)

    return {
        "status": "success",
        "email_id": email_id,
        "total_attachments_received": total_received,
        "successful_attachments": total_successful,
        "uploaded_paths": uploaded_paths
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
