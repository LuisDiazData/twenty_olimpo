import base64
import os
import json
import time
from io import BytesIO
from pathlib import Path
from litellm import completion
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

MODEL_NAME = os.getenv("LITELLM_MODEL")  # e.g. "runpod/c2jx606dtqs7g8" o "openai/gpt-4o"


# ── RunPod OCR ─────────────────────────────────────────────────────────────────

def _llamar_runpod_ocr(imagen_b64: str) -> str:
    """Send a base64-encoded image to the RunPod serverless endpoint for OCR."""
    import requests

    endpoint_id = os.environ["RUNPOD_ENDPOINT_ID"]
    api_key     = os.environ["RUNPOD_API_KEY"]
    base_url    = f"https://api.runpod.ai/v2/{endpoint_id}"

    # Submit job
    resp = requests.post(
        f"{base_url}/run",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "input": {
                "image_base64": imagen_b64,
                "task": "ocr",
                "language": "spa",
            }
        },
        timeout=30,
    )
    resp.raise_for_status()
    job_id = resp.json()["id"]

    # Poll until COMPLETED (max 60 s)
    for _ in range(12):
        time.sleep(5)
        status_resp = requests.get(
            f"{base_url}/status/{job_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resultado = status_resp.json()
        if resultado["status"] == "COMPLETED":
            return resultado.get("output", {}).get("text", "")
        if resultado["status"] == "FAILED":
            raise RuntimeError(f"RunPod OCR falló: {resultado}")

    raise TimeoutError("RunPod OCR no completó en 60 segundos")


def ocr_con_runpod(contenido_bytes: bytes, mime_type: str) -> str:
    """
    Send an image or scanned PDF to RunPod for OCR.
    PDF pages are converted to PNG (max 3 pages) before sending.
    Returns the extracted text.
    """
    if mime_type == "application/pdf":
        from pdf2image import convert_from_bytes  # lazy import

        imagenes = convert_from_bytes(contenido_bytes, first_page=1, last_page=3)
        textos: list[str] = []
        for img in imagenes:
            buf = BytesIO()
            img.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode()
            textos.append(_llamar_runpod_ocr(img_b64))
        return "\n---\n".join(textos)
    else:
        img_b64 = base64.b64encode(contenido_bytes).decode()
        return _llamar_runpod_ocr(img_b64)


# ── Password extraction ────────────────────────────────────────────────────────

def extract_passwords_from_text(email_body: str) -> list[str]:
    """
    Uses litellm to read the email body and extract any potential passwords 
    (like RFCs, explicit passwords mentioned, or policy numbers).
    """
    if not email_body or len(email_body.strip()) < 5:
        return []

    prompt = f"""
Eres un asistente experto en seguridad y extracción de datos.
El siguiente texto es el cuerpo de un correo electrónico que contiene archivos adjuntos (ZIP, RAR, PDF) protegidos con contraseña.

Por favor, lee el correo e identifica TODAS las posibles contraseñas que el remitente haya mencionado para abrir los adjuntos. 
A menudo las contraseñas pueden ser:
- El RFC del cliente cerrado (con o sin homoclave).
- El número de póliza.
- Contraseñas explícitamente mencionadas (ej: "la clave es 1234").
- Nombres propios o fechas si se sugieren.

Texto del correo:
{email_body[:3000]}

Tu única salida debe ser un JSON válido que contenga un array de strings con las posibles contraseñas. NO devuelvas ningún otro texto, explicaciones ni validaciones. 
Si no encuentras ninguna, devuelve un array vacío [].
Ejemplo de salida de éxito: ["MIPassword123", "XAXX010101000", "POLIZA987"]
"""
    try:
        response = completion(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            api_key=os.getenv("LLM_API_KEY", "dummy"), # depends on provider
            # If using RunPod, api_base is required if runpod expects a specific path, but Litellm handles 'runpod/' natively
        )
        
        content = response.choices[0].message.content
        
        # Parse output looking for JSON array
        # Sometime LLMs wrap in ```json [...] ```
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        passwords = json.loads(content.strip())
        if isinstance(passwords, list):
            return [str(p) for p in passwords]
        return []
        
    except Exception as e:
        print(f"Error extracting passwords using LLM: {e}")
        return []
