import os
import json
from litellm import completion
from dotenv import load_dotenv

load_dotenv()

# We will use LiteLLM to extract possible passwords from the email text.
# The user can configure the LITELLM_MODEL in .env (e.g. "openai/gpt-4o", "gemini/gemini-pro")
# or use their existing RunPod container.
MODEL_NAME = os.getenv("LITELLM_MODEL", "runpod/c2jx606dtqs7g8") # fallback to the runpod endpoint ID

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
