---
name: Infraestructura confirmada en código
description: URLs, IDs y configuración real observada en los archivos del proyecto
type: project
---

# Infraestructura real del proyecto (observada en código)

**Supabase:**
- Project ref: `aczkvxveenycpnwyqqbs`
- URL: `https://aczkvxveenycpnwyqqbs.supabase.co`
- Storage S3 endpoint: `https://aczkvxveenycpnwyqqbs.storage.supabase.co/storage/v1/s3`
- Región: us-east-1 (North Virginia)
- Buckets configurados: `incoming-raw`, `tramite-docs` (alias `tramites-docs` en código), `ocr-output`

**FastAPI (agentes):**
- Código en: `scripts/attachment_processor/`
- Puerto interno: 4000
- Dockerfile existente: `scripts/attachment_processor/Dockerfile` (python:3.11-slim, sin multi-stage)
- Dependencias clave: fastapi, uvicorn, litellm, supabase, pdfplumber, pikepdf, tenacity
- No tiene endpoint /health — pendiente de agregar

**n8n:**
- Pipeline principal: `scripts/n8n/pipeline_gmail_ingest_v4.json`
- Workflow name: `promotoria-gmail-ingestion-v4`
- Poll Gmail cada minuto, descarga adjuntos
- Variable de entorno clave: `AGENTES_BASE_URL=http://agentes:4000` (local) → producción apunta a Railway

**Twenty CRM:**
- Docker image: `twentycrm/twenty:${TAG:-latest}` — pendiente pinnear versión
- Puerto: 3000
- Health check: `/healthz`
- Worker: `yarn worker:prod`
- GraphQL endpoint real: `/graphql` (no `/api`)

**Migraciones Supabase:**
- 20 archivos: 000 a 018 en `scripts/supabase/migrations/`
- Orden de aplicación es crítico (FK dependencies)
- pg_cron jobs incluyen URLs de FastAPI que deben actualizarse post-deploy

**Why:** Documentado para no tener que re-leer los archivos en cada conversación.
**How to apply:** Usar estos valores al generar configuraciones, no pedir al usuario que los busque.
