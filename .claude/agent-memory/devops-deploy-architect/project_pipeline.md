---
name: Arquitectura del pipeline de correo
description: Flujo técnico completo desde Gmail hasta Twenty CRM, con endpoints reales
type: project
---

# Pipeline de procesamiento de correos

## Flujo completo (confirmado en código)

```
Gmail → n8n (poll 1min) → POST /api/v1/email/ingest (FastAPI)
     → guarda incoming_emails en Supabase
     → sube adjuntos a bucket `tramites-docs` en Supabase Storage
     → RunPod si hay PDFs escaneados (RUNPOD_ENDPOINT_ID)
     → LiteLLM → OpenAI GPT-4o para clasificación y extracción
     → POST /api/v1/agentes/asignacion
     → Crea Tramite en Twenty CRM via GraphQL /graphql
     → Actualiza tramites_pipeline en Supabase
```

## Endpoints FastAPI confirmados en código

- `POST /api/v1/email/ingest` — ingesta de email desde n8n (router: email_ingest)
- `POST /api/v1/agentes/documentos` — procesamiento de documentos (router: documentos)
- `POST /api/v1/agentes/asignacion` — asignación a analista y creación en Twenty (router: asignacion)
- `GET /health` — pendiente de implementar (no existe aún en main.py)
- `GET /ready` — pendiente de implementar

## Agentes en el pipeline

- **Agente 1** (email_ingest.py): recibe y guarda el email
- **Agente 2** (extractor.py): extrae adjuntos y los procesa con pikepdf
- **Agente 3** (agente_documentos.py): clasificación de documentos
- **Agente 4** (agente_asignacion.py): identifica agente (email→CUA→fuzzy), consulta analista disponible, crea Tramite en Twenty

## Confianza del agente de asignación

- Umbral: confianza >= 75 para proceder
- Fuzzy matching de nombres: umbral 85% via LLM
- Búsqueda en cascada: email exacto → CUA → nombre fuzzy

## Deduplicación

- Tabla `dedup_index` con hash SHA256 de (sender_email + subject_normalizado + fecha_ventana)
- Campo `es_duplicado_posible` en tramites_pipeline
- Thread tracking via `thread_id` (Gmail thread ID o In-Reply-To header)

**Why:** Documentar el flujo evita tener que re-leer 5 archivos Python en cada sesión.
**How to apply:** Usar cuando el usuario pregunte sobre el pipeline, debugging, o configuración de endpoints.
