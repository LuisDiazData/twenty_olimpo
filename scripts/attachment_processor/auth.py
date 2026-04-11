"""
auth.py — Autenticación centralizada para el servicio FastAPI.

Dependencias disponibles:
  - require_api_key: API Key via X-API-Key header (para llamadas desde n8n)
  - verify_twenty_webhook: HMAC sha256 via X-Twenty-Signature (para webhooks de Twenty CRM)

Uso en main.py:
  from auth import require_api_key, verify_twenty_webhook, validate_env_vars
"""
import hashlib
import hmac
import logging
import os

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def validate_env_vars() -> None:
    """Llamar en startup. Falla rápido si faltan variables críticas de seguridad."""
    missing = [var for var in ["INTERNAL_API_KEY"] if not os.getenv(var)]
    if missing:
        raise RuntimeError(
            f"Variables de entorno requeridas no configuradas: {', '.join(missing)}\n"
            "Configúralas en .env o en las variables de entorno del servidor."
        )
    logger.info("[AUTH] Variables de seguridad verificadas correctamente")


async def require_api_key(
    api_key: str | None = Security(_API_KEY_HEADER),
) -> None:
    """
    Dependencia FastAPI — valida el header X-API-Key contra INTERNAL_API_KEY.
    Usa hmac.compare_digest para prevenir timing attacks.
    """
    configured_key = os.getenv("INTERNAL_API_KEY", "")
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Servicio no configurado correctamente",
        )
    if not api_key or not hmac.compare_digest(api_key, configured_key):
        logger.warning("[AUTH] API key inválida o ausente")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o ausente",
            headers={"WWW-Authenticate": "ApiKey"},
        )


async def verify_twenty_webhook(request: Request) -> None:
    """
    Dependencia FastAPI — valida la firma HMAC del webhook de Twenty CRM.

    Twenty debe enviar el header:
        X-Twenty-Signature: sha256=<hex_digest>

    El digest se calcula como: HMAC-SHA256(body, TWENTY_WEBHOOK_SECRET)

    Si TWENTY_WEBHOOK_SECRET no está configurado, el webhook se acepta sin
    validación de firma (útil en desarrollo local). En producción debe configurarse.

    Nota: request.body() cachea el body en request._body, por lo que Pydantic
    puede deserializar el payload normalmente después de llamar a esta dependencia.
    """
    webhook_secret = os.getenv("TWENTY_WEBHOOK_SECRET", "")

    if not webhook_secret:
        logger.warning(
            "[AUTH] TWENTY_WEBHOOK_SECRET no configurado — webhook aceptado sin "
            "validación de firma. Configúralo en producción."
        )
        return

    signature_header = request.headers.get("x-twenty-signature", "")
    if not signature_header.startswith("sha256="):
        logger.warning("[AUTH] Webhook recibido sin firma válida")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma de webhook ausente o con formato incorrecto",
        )

    # Leer body — queda cacheado en request._body para uso posterior por Pydantic
    body = await request.body()
    expected_hex = hmac.new(
        webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    received_hex = signature_header[len("sha256="):]

    if not hmac.compare_digest(received_hex, expected_hex):
        logger.warning("[AUTH] Firma de webhook inválida — posible request falsificado")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma de webhook inválida",
        )
