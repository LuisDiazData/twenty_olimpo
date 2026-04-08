---
name: Workflows en disco
description: Inventario de archivos JSON de workflow en scripts/n8n/ y su estado de carga en n8n
type: reference
---

## Directorio: `/home/lag/Documentos/twenty_olimpo/scripts/n8n/`

### pipeline_tramites_v3_fixed.json — RECOMENDADO
- **Nombre:** Pipeline Trámites v3 (Fixed)
- **Estado en JSON:** `active: true`
- **Cargado en n8n:** NO (instancia vacía)
- **Arquitectura:** Gmail Trigger → Extraer Headers → Check Reply → [branch reply | branch nuevo]
  - Branch nuevo: UUID → Supabase → FastAPI(/process-email) → Agente1(comprensión) → Agente2(clasificación) → Agente3(documentos) → Agente4(asignación) → Acuse
- **URLs:** Usa `$env.AGENTES_BASE_URL` y `$env.SUPABASE_URL` (variables de entorno, no hardcoded)
- **Gmail credential ID referenciada:** `dOjcZbTWAE6HCxaM`

### pipeline_tramites_v3.json — VERSION ANTERIOR
- **Nombre:** Pipeline Trámites v3
- **URLs hardcodeadas:** `http://host.docker.internal:4000/...`
- **Sin Agente 2 (Clasificación)**
- **Diferencia clave vs fixed:** URLs hardcodeadas y falta Agente 2

### workflow-gmail-tramite-v3.json — IGUAL A pipeline_tramites_v3.json
- Mismo contenido que `pipeline_tramites_v3.json`

### workflow-gmail-tramite-v2.json
- **Nombre:** Gmail → Trámite (v2 con Python Backend)
- Usa RunPod para IA (arquitectura anterior, reemplazada por agentes FastAPI)
- URLs hardcodeadas a `host.docker.internal:4000`

### workflow-gmail-tramite.json — VERSION MAS ANTIGUA
- **Nombre:** Gmail → Trámite (RunPod + Supabase)
- Arquitectura RunPod-only, sin FastAPI backend
- URL hardcodeada: `https://api.runpod.ai/v2/c2jx606dtqs7g8/run`
- Supabase URL hardcodeada: `https://aczkvxveenycpnwyqqbs.supabase.co`

## Workflow importado y activo en instancia n8n

**`pipeline_gmail_ingest_v4_hardcoded.json`** — IMPORTADO como `promotoria-gmail-ingestion-v4`
- **ID en instancia:** `cijncOdXmag1dv7z`
- **Estado:** INACTIVO (pendiente conectar credencial Gmail OAuth2)
- **Arquitectura v4:** Gmail Trigger → Extraer Headers → POST /api/v1/email/ingest (PRIMER PASO)
  → IF hilo conocido → branch reply (Notificar equipo / noOp)
  → branch nuevo → Supabase record → FastAPI process-email → Agente comprension → Agente asignacion → Acuse al remitente
- **Valores hardcoded:** AGENTES_BASE_URL=host.docker.internal:4000, SUPABASE_URL, SUPABASE_SERVICE_KEY, EQUIPO_EMAIL
- **Gmail credential placeholder:** `PENDIENTE_CONFIGURAR` en todos los nodos Gmail

## Endpoints FastAPI que el workflow v4 llama

- `POST /api/v1/email/ingest` — primer paso, detecta si es reply o email nuevo
- `POST /process-email` — procesamiento multipart de adjuntos
- `POST /api/v1/agentes/comprension` — Agente 1 (comprension)
- `POST /api/v1/agentes/asignacion` — Agente 4 (asignacion a Twenty)
