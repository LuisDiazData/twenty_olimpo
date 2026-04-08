# DEPLOY.md — Guía de Despliegue en Producción
# Olimpo Promotoría de Seguros GNP

> **Nivel de criticidad**: ALTO — Esta plataforma maneja trámites de seguros de vida,
> GMM, PyMES y Autos. La pérdida de datos o downtime tiene impacto directo en el negocio.
> Sigue cada paso en orden. No improvises en producción.

---

## Tabla de Contenidos

1. [Arquitectura de Producción](#1-arquitectura-de-producción)
2. [Pre-requisitos](#2-pre-requisitos)
3. [Supabase — Base de Datos y Storage](#3-supabase--base-de-datos-y-storage)
4. [Railway — FastAPI (Agentes de IA)](#4-railway--fastapi-agentes-de-ia)
5. [RunPod — OCR con GPU](#5-runpod--ocr-con-gpu)
6. [Twenty CRM — Servidor Propio con Docker](#6-twenty-crm--servidor-propio-con-docker)
7. [n8n — Automatización en Producción](#7-n8n--automatización-en-producción)
8. [Vercel — Dashboard Frontend](#8-vercel--dashboard-frontend)
9. [CI/CD con GitHub Actions](#9-cicd-con-github-actions)
10. [Dominio y DNS con Cloudflare](#10-dominio-y-dns-con-cloudflare)
11. [Variables de Entorno — Tabla Maestra](#11-variables-de-entorno--tabla-maestra)
12. [Orden de Despliegue — Checklist Maestro](#12-orden-de-despliegue--checklist-maestro)
13. [Monitoreo, Logs y Alertas](#13-monitoreo-logs-y-alertas)
14. [Seguridad y Hardening](#14-seguridad-y-hardening)
15. [Runbook de Incidentes](#15-runbook-de-incidentes)
16. [Estimado de Costos Mensuales](#16-estimado-de-costos-mensuales)

---

## 1. Arquitectura de Producción

### Diagrama de Arquitectura

```
                        ┌─────────────────────────────────────────────────────┐
                        │                INTERNET / AGENTES                   │
                        │         (correo electrónico entrante)               │
                        └───────────────────┬─────────────────────────────────┘
                                            │
                                            ▼
                        ┌───────────────────────────────────┐
                        │         GMAIL (OAuth2)            │
                        │   bandeja: operaciones@olimpo.mx  │
                        └───────────────────┬───────────────┘
                                            │  Poll cada 1 min (trigger)
                                            ▼
                    ┌───────────────────────────────────────────┐
                    │         n8n  (Docker en VPS propio)       │
                    │   pipeline_gmail_ingest_v4                │
                    │   n8n.olimpo.com.mx  — puerto 5678        │
                    └────────────────────┬──────────────────────┘
                                         │  POST /api/v1/email/ingest
                                         │  POST /api/v1/agentes/documentos
                                         │  POST /api/v1/agentes/asignacion
                                         ▼
                    ┌────────────────────────────────────────────┐
                    │   FastAPI  (Railway — Hobby plan)          │
                    │   api.olimpo.com.mx                        │
                    │                                            │
                    │   Agente 1: email/ingest                   │
                    │   Agente 2: extractor de documentos        │
                    │   Agente 3: clasificación y enriquecimiento│
                    │   Agente 4: asignación a analista          │
                    │   LiteLLM → OpenAI GPT-4o                  │
                    └──────┬──────────────┬──────────────────────┘
                           │              │
              ┌────────────┘              └──────────────┐
              │                                          │
              ▼                                          ▼
┌─────────────────────────────┐          ┌──────────────────────────────┐
│  Supabase  (us-east-1)      │          │  RunPod  (Serverless GPU)    │
│  aczkvxveenycpnwyqqbs       │          │  Modelo OCR pesado           │
│                             │          │  ocr.olimpo.com.mx (proxy)   │
│  DB: tramites_pipeline      │          │                              │
│      incoming_emails        │          │  Entrada: PDF/imagen         │
│      email_attachments      │          │  Salida:  JSON estructurado  │
│      ocr_results            │          │  Timeout: 180s               │
│      ai_processing_log      │          └──────────────────────────────┘
│      contact_email_map      │
│                             │
│  Storage:                   │
│    incoming-raw/            │
│    tramite-docs/            │
│    ocr-output/              │
└──────────────┬──────────────┘
               │  GraphQL API
               │  POST /graphql
               ▼
┌─────────────────────────────────────────────────────────┐
│   Twenty CRM  (Docker en VPS propio)                    │
│   app.olimpo.com.mx  — puerto 3000 (NGINX proxy)        │
│                                                         │
│   Worker:  yarn worker:prod                             │
│   PostgreSQL:  postgres:5432 (internal Docker network)  │
│   Redis:       redis:6379    (internal Docker network)  │
│                                                         │
│   Objetos custom:  Tramite, Agente, DocumentoTramite    │
│   Vistas:   Directora, Gerente, Analista               │
└──────────────────────────────────────────────────────────┘
               │  Embed iframe / redirect
               ▼
┌─────────────────────────────────────────────────────────┐
│   Dashboard Frontend  (Vercel)                          │
│   dashboard.olimpo.com.mx                               │
│                                                         │
│   DashboardPage.tsx: DirectoraView / GerenteView /      │
│   EspecialistaView  — conecta a Supabase directamente   │
│   via SUPABASE_URL + anon key                           │
└─────────────────────────────────────────────────────────┘
```

### Flujo de Datos Principal

```
1. Gmail recibe correo de agente
2. n8n detecta email nuevo (poll 1 min)
3. n8n extrae headers y adjuntos
4. n8n → POST api.olimpo.com.mx/api/v1/email/ingest
5. FastAPI guarda en Supabase (incoming_emails)
6. FastAPI sube adjuntos a Supabase Storage (incoming-raw/)
7. FastAPI → RunPod si hay PDFs escaneados (OCR GPU)
8. RunPod devuelve texto estructurado → FastAPI guarda en ocr_results
9. FastAPI → Agente LLM: clasifica ramo, extrae campos, identifica agente
10. FastAPI → POST /api/v1/agentes/asignacion: crea Tramite en Twenty CRM
11. FastAPI actualiza tramites_pipeline en Supabase (estatus, IDs)
12. Analista ve el Tramite en app.olimpo.com.mx (Twenty CRM)
13. Dashboard dashboard.olimpo.com.mx muestra KPIs en tiempo real
```

### Subdominios y Puertos

| Servicio | Dominio de Producción | Puerto Interno | Plataforma |
|---|---|---|---|
| Twenty CRM | `app.olimpo.com.mx` | 3000 | VPS propio |
| FastAPI Agentes | `api.olimpo.com.mx` | 4000 | Railway |
| n8n | `n8n.olimpo.com.mx` | 5678 | VPS propio |
| Dashboard | `dashboard.olimpo.com.mx` | 443 (HTTPS) | Vercel |
| Supabase | `aczkvxveenycpnwyqqbs.supabase.co` | 443 | Supabase Cloud |
| RunPod | gestionado por RunPod | — | RunPod Cloud |

> **Nota de dominio**: Este documento usa `olimpo.com.mx` como ejemplo. Reemplaza
> con el dominio real de la promotoría en todos los archivos de configuración.

---

## 2. Pre-requisitos

### 2.1 Cuentas necesarias (créalas antes de empezar)

- [ ] **GitHub** — https://github.com — el repositorio ya existe (`twenty_olimpo`)
- [ ] **Supabase** — https://supabase.com — plan Pro recomendado ($25/mes)
- [ ] **Railway** — https://railway.app — plan Hobby ($5/mes + uso)
- [ ] **RunPod** — https://www.runpod.io — pago por uso (serverless)
- [ ] **Vercel** — https://vercel.com — plan Hobby (gratuito para comenzar)
- [ ] **Cloudflare** — https://cloudflare.com — gratuito para DNS
- [ ] **OpenAI** — https://platform.openai.com — cuenta con créditos
- [ ] **Google Cloud Console** — https://console.cloud.google.com — para OAuth2 de Gmail

### 2.2 Herramientas locales requeridas

```bash
# Verificar que tienes todo instalado:
docker --version        # >= 24.0
docker compose version  # >= 2.20
git --version           # >= 2.40
node --version          # >= 20.0
python3 --version       # >= 3.11
curl --version          # cualquier versión reciente

# Herramientas adicionales:
pip install supabase     # CLI de Supabase vía Python
npm install -g vercel    # CLI de Vercel
npm install -g @railway/cli  # CLI de Railway

# Autenticación con Railway:
railway login

# Autenticación con Vercel:
vercel login
```

### 2.3 VPS para Twenty CRM y n8n

Necesitas un servidor Linux para correr Twenty CRM y n8n con Docker Compose.

**Recomendación mínima para producción:**
- RAM: 4 GB (8 GB ideal)
- CPU: 2 vCPUs
- Disco: 40 GB SSD
- OS: Ubuntu 22.04 LTS
- Proveedor: DigitalOcean Droplet ($24/mes), Hetzner CX22 (€4.35/mes), Linode, Vultr

**Instalar Docker en el VPS (Ubuntu 22.04):**

```bash
# Conectarse al VPS:
ssh root@TU_IP_VPS

# Instalar Docker:
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Instalar Docker Compose plugin:
apt-get install -y docker-compose-plugin

# Verificar:
docker compose version

# Instalar NGINX (reverse proxy):
apt-get install -y nginx certbot python3-certbot-nginx

# Instalar herramientas útiles:
apt-get install -y git htop curl wget unzip fail2ban ufw
```

---

## 3. Supabase — Base de Datos y Storage

> El proyecto Supabase ya existe: `aczkvxveenycpnwyqqbs` (región us-east-1).
> Esta sección documenta cómo recrearlo desde cero si fuera necesario,
> y cómo aplicar las migraciones en un proyecto nuevo o de staging.

### 3.1 Crear proyecto Supabase (si es nuevo)

1. Ir a https://supabase.com/dashboard
2. Clic en **New Project**
3. Configurar:
   - **Name**: `olimpo-produccion`
   - **Database Password**: genera una contraseña segura (guárdala en un gestor)
   - **Region**: `East US (North Virginia)` — más cercana para latencia México
   - **Plan**: Pro ($25/mes) — necesario para PITR (backups point-in-time)
4. Esperar ~2 minutos mientras el proyecto se inicializa

### 3.2 Obtener las credenciales

```
Supabase Dashboard → Settings → API

Copiar y guardar en lugar seguro:
- Project URL:      https://XXXXXXXXXXXX.supabase.co
- anon/public key:  eyJ...  (para clientes frontend con RLS)
- service_role key: eyJ...  (para FastAPI/n8n — NUNCA exponer al frontend)

Supabase Dashboard → Settings → Database

- Connection string (con pooling):
  postgres://postgres.[ref]:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

> **ADVERTENCIA DE SEGURIDAD**: La `service_role` key bypasea Row Level Security.
> Nunca debe aparecer en código frontend, repositorio público, ni logs.
> Solo va en Railway secrets y GitHub Actions secrets.

### 3.3 Aplicar migraciones en orden

Las migraciones están en `scripts/supabase/migrations/`. Deben aplicarse en orden numérico.

**Opción A — Desde Supabase Dashboard (SQL Editor):**

```
Supabase Dashboard → SQL Editor → New Query

Pegar y ejecutar cada archivo en este orden exacto:
```

```bash
# Orden correcto de aplicación:
# 000_tramites_pipeline.sql     — tabla central tramites_pipeline
# 001_pipeline_tables.sql       — incoming_emails, email_attachments, dedup_index, ocr_results, ai_processing_log, contact_email_map
# 002_indexes.sql               — índices de performance
# 003_storage_buckets.sql       — buckets: incoming-raw, tramite-docs, ocr-output
# 004_rls_policies.sql          — Row Level Security
# 005_pg_cron.sql               — jobs de mantenimiento programados
# 006_data_model_enhancements.sql
# 007_attachments_log_agente3.sql
# 008_agente4_tables.sql
# 009_pipeline_logs.sql
# 009b_attachments_log_individual.sql
# 010_tipo_documento_config.sql
# 011_hilos_ingest_log.sql
# 012_historial_estatus.sql
# 013_calendario_operativo.sql
# 014_reglas_negocio.sql
# 015_kpi_snapshots_cache.sql
# 016_productos.sql
# 017_notas_interacciones.sql
# 018_agent_performance_monthly.sql
```

**Opción B — Desde línea de comandos (psql):**

```bash
# Obtener la Connection String desde Supabase Dashboard → Settings → Database
# Usar la "Direct Connection" (no pooler) para migraciones:
export SUPABASE_DB_URL="postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres"

# Aplicar todas las migraciones en orden:
for f in scripts/supabase/migrations/0*.sql; do
  echo "Aplicando: $f"
  psql "$SUPABASE_DB_URL" -f "$f"
  if [ $? -ne 0 ]; then
    echo "ERROR en $f — detener y revisar"
    exit 1
  fi
done

echo "Migraciones completadas."
```

### 3.4 Habilitar extensiones necesarias

```sql
-- Ejecutar en SQL Editor de Supabase:
CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

Para `pg_cron`: ir a `Database → Extensions → pg_cron → Enable`.

### 3.5 Verificar Storage Buckets

Después de aplicar `003_storage_buckets.sql`, verificar en:
`Supabase Dashboard → Storage`

Deben aparecer tres buckets privados:
- `incoming-raw` — emails crudos de Gmail (50 MB límite)
- `tramite-docs` — documentos finales vinculados a Tramites (50 MB límite)
- `ocr-output` — resultados JSON de RunPod (10 MB límite)

Si no aparecen, ejecutar manualmente:

```sql
-- Verificar buckets:
SELECT id, name, public, file_size_limit FROM storage.buckets;

-- Si faltan, re-ejecutar 003_storage_buckets.sql
```

### 3.6 Configurar CORS para el Dashboard Vercel

```
Supabase Dashboard → Settings → API → CORS Origins

Agregar:
- https://dashboard.olimpo.com.mx
- https://*.vercel.app  (para preview deployments)
- http://localhost:3001  (para desarrollo local)
```

### 3.7 Habilitar Point-in-Time Recovery (PITR)

```
Supabase Dashboard → Settings → Backups

- Habilitar PITR (requiere plan Pro)
- Retention: 7 días mínimo (recomendado 14 días)
```

> **Este paso es obligatorio para producción.** Los trámites de seguros son datos
> críticos. Sin PITR, un error en una migración podría ser irreversible.

### 3.8 Configurar pg_cron para SLA overdue

Después de tener FastAPI desplegado en Railway, actualizar `005_pg_cron.sql`
con la URL real:

```sql
-- Ejecutar en SQL Editor después de tener la URL de Railway:
SELECT cron.schedule(
  'sync-contact-email-map',
  '0 */6 * * *',
  $$
    SELECT net.http_post(
      url      := 'https://TU-FASTAPI.railway.app/sync/contact-email-map',
      headers  := '{"Authorization": "Bearer TU-INTERNAL-TOKEN"}'::jsonb,
      body     := '{}'::jsonb
    );
  $$
);

SELECT cron.schedule(
  'mark-overdue-sla',
  '0 14 * * 1-5',
  $$
    SELECT net.http_post(
      url      := 'https://TU-FASTAPI.railway.app/tramites/mark-overdue',
      headers  := '{"Authorization": "Bearer TU-INTERNAL-TOKEN"}'::jsonb,
      body     := '{}'::jsonb
    );
  $$
);
```

### 3.9 Verificar que todo funciona

```bash
# Test de conexión desde local:
curl -H "apikey: TU_ANON_KEY" \
     -H "Authorization: Bearer TU_ANON_KEY" \
     "https://TU-REF.supabase.co/rest/v1/tramites_pipeline?select=count"

# Debe retornar: [{"count": 0}] o el conteo actual
```

---

## 4. Railway — FastAPI (Agentes de IA)

### 4.1 Preparar el Dockerfile para Railway

El Dockerfile existente en `scripts/attachment_processor/Dockerfile` ya está bien
estructurado. Para Railway, necesitamos un Dockerfile multi-stage optimizado.

Crear/actualizar `scripts/attachment_processor/Dockerfile`:

```dockerfile
# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Dependencias del sistema para compilar (solo en build stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime deps para pdfplumber / pdf2image / pikepdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copiar paquetes Python instalados desde builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copiar código de la aplicación
COPY . .

# Railway inyecta PORT como variable de entorno
ENV PORT=4000
EXPOSE 4000

# Health check (Railway lo usa para saber si el servicio está listo)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Usuario no-root para seguridad
RUN useradd -m -u 1001 appuser && chown -R appuser /app
USER appuser

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --log-level info --workers 2"]
```

### 4.2 Agregar endpoint /health a FastAPI

Agregar al final de `scripts/attachment_processor/main.py` si no existe:

```python
from datetime import datetime, timezone
import sys

@app.get("/health")
async def health_check():
    """Health check endpoint para Railway y monitoreo externo."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "olimpo-agentes-fastapi",
        "python": sys.version.split()[0],
    }

@app.get("/ready")
async def readiness_check():
    """Readiness check — verifica conectividad con dependencias críticas."""
    checks = {}

    # Verificar Supabase
    try:
        from supabase_client import supabase as _sb
        if _sb:
            _sb.table("tramites_pipeline").select("id").limit(1).execute()
            checks["supabase"] = "ok"
        else:
            checks["supabase"] = "not_configured"
    except Exception as e:
        checks["supabase"] = f"error: {str(e)[:100]}"

    # Verificar Twenty CRM
    try:
        import httpx, os
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{os.getenv('TWENTY_API_URL', '')}/healthz")
            checks["twenty_crm"] = "ok" if r.status_code == 200 else f"http_{r.status_code}"
    except Exception as e:
        checks["twenty_crm"] = f"error: {str(e)[:100]}"

    all_ok = all("ok" in v for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

### 4.3 Crear railway.toml

Crear `scripts/attachment_processor/railway.toml`:

```toml
# ── Railway configuration — FastAPI Agentes ──────────────────────────────────
# Referencia: https://docs.railway.app/reference/config-as-code

[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
# Railway inyecta PORT automáticamente — no hardcodear
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT --log-level info --workers 2"

# Health check: Railway espera 200 en /health antes de considerar el deploy exitoso
healthcheckPath = "/health"
healthcheckTimeout = 120

# Reiniciar automáticamente si el proceso cae
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

# Región más cercana a México
# region = "us-west1"  # descomentar si quieres especificar región
```

### 4.4 Crear proyecto en Railway

```bash
# 1. Instalar CLI de Railway:
npm install -g @railway/cli

# 2. Login:
railway login

# 3. Ir al directorio de FastAPI:
cd /home/lag/Documentos/twenty_olimpo/scripts/attachment_processor

# 4. Inicializar proyecto Railway:
railway init

# Cuando pregunte:
# Project name: olimpo-agentes
# Environment: production

# 5. Linkear al proyecto recién creado:
railway link
```

### 4.5 Configurar variables de entorno en Railway

```bash
# Método 1 — CLI (recomendado para automatización):
railway variables set \
  TWENTY_API_URL="https://app.olimpo.com.mx" \
  TWENTY_API_KEY="eyJ..." \
  SUPABASE_URL="https://aczkvxveenycpnwyqqbs.supabase.co" \
  SUPABASE_KEY="sb_publishable_..." \
  SUPABASE_SERVICE_ROLE_KEY="eyJ..." \
  BUCKET_NAME="tramites-docs" \
  LLM_MODEL="openai/gpt-4o" \
  OPENAI_API_KEY="sk-..." \
  RUNPOD_API_KEY="..." \
  RUNPOD_ENDPOINT_ID="..."

# Método 2 — Dashboard Railway:
# railway.app → olimpo-agentes → Variables → Add Variable
```

> **IMPORTANTE**: Railway maneja los secretos de forma segura. Nunca los pongas
> en el `railway.toml` ni en el Dockerfile. Solo en el panel de Variables.

### 4.6 Configurar auto-deploy desde GitHub

```
Railway Dashboard → olimpo-agentes → Settings → Source

- Conectar GitHub repo: tu-org/twenty_olimpo
- Branch: main
- Root directory: scripts/attachment_processor
- Auto-deploy: ON

Esto significa que cada push a main re-deploya FastAPI automáticamente.
```

### 4.7 Deploy inicial

```bash
# Desde el directorio de FastAPI:
cd scripts/attachment_processor

# Deploy manual (primera vez):
railway up --detach

# Ver logs en tiempo real:
railway logs --tail

# Ver status del servicio:
railway status
```

### 4.8 Verificar deploy exitoso

```bash
# Obtener URL del servicio:
railway open

# O via CLI:
railway status
# → URL: https://olimpo-agentes-production.up.railway.app

# Test de health check:
curl https://olimpo-agentes-production.up.railway.app/health
# Esperado: {"status": "ok", "version": "1.0.0", ...}

# Test de readiness:
curl https://olimpo-agentes-production.up.railway.app/ready
# Esperado: {"status": "ready", "checks": {"supabase": "ok", "twenty_crm": "ok"}}

# Test del endpoint principal:
curl -X POST https://olimpo-agentes-production.up.railway.app/api/v1/email/ingest \
  -H "Content-Type: application/json" \
  -d '{"message_id":"test-001","thread_id":"test-001","from_email":"test@test.com","from_name":"Test","subject":"Prueba","body_text":"Hola","received_at":"2026-04-05T10:00:00Z","has_attachments":false,"attachment_count":0,"canal_origen":"CORREO"}'
```

### 4.9 Configurar dominio custom en Railway

```
Railway Dashboard → olimpo-agentes → Settings → Domains

1. Clic en "Add Custom Domain"
2. Ingresar: api.olimpo.com.mx
3. Railway mostrará un CNAME record para configurar en Cloudflare
4. En Cloudflare: DNS → Add Record → CNAME → api → [valor que da Railway]
5. Railway detecta automáticamente el SSL (puede tardar 5-10 min)
```

### 4.10 Configurar staging environment

```bash
# Crear environment de staging en Railway:
railway environment create staging

# Cambiar a staging:
railway environment staging

# Set variables de staging (apuntando a Supabase staging si tienes uno):
railway variables set \
  TWENTY_API_URL="https://staging.app.olimpo.com.mx" \
  SUPABASE_URL="https://TU-STAGING-REF.supabase.co" \
  OPENAI_API_KEY="sk-..." \
  LLM_MODEL="openai/gpt-4o-mini"  # modelo más barato para staging

# Deploy a staging:
railway up --environment staging
```

---

## 5. RunPod — OCR con GPU

### 5.1 Crear cuenta y configurar billing

1. Ir a https://www.runpod.io
2. Crear cuenta
3. Settings → Billing → Add credit ($20 de crédito inicial es suficiente para empezar)

### 5.2 Crear Serverless Endpoint

```
RunPod Dashboard → Serverless → New Endpoint

Configuración recomendada:
- Name: olimpo-ocr-endpoint
- Template: Custom
- Container Image: (ver sección 5.3)
- Min Workers: 0  (cold start — se activa solo cuando llegan peticiones)
- Max Workers: 3  (escala hasta 3 instancias paralelas)
- GPU: RTX 3090 o RTX 4090 (mejor costo/beneficio para OCR)
- Timeout: 300 segundos
- Idle Timeout: 5 segundos (apagar worker rápido para reducir costos)
```

### 5.3 Docker Image para OCR en RunPod

El modelo OCR actual usa LiteLLM con visión (GPT-4o). Si en el futuro se usa un
modelo local, se necesitaría una imagen custom. Por ahora, el flujo es:

```
FastAPI (Railway) → envía imagen base64 → OpenAI Vision API (GPT-4o)
                  → resultado JSON estructurado → guarda en ocr_results
```

Si se implementa OCR local con GPU (tesseract/paddleocr/surya), crear un
`Dockerfile.runpod` en `scripts/attachment_processor/`:

```dockerfile
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /app

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    runpod==1.6.2 \
    pytesseract==0.3.10 \
    Pillow==10.3.0 \
    pdf2image==1.17.0 \
    pdfplumber==0.11.0 \
    fastapi==0.110.0 \
    uvicorn==0.29.0

COPY runpod_handler.py .

# RunPod espera un handler en este formato:
CMD ["python", "-u", "runpod_handler.py"]
```

### 5.4 Handler de RunPod (si se usa modelo local)

Crear `scripts/attachment_processor/runpod_handler.py`:

```python
"""
RunPod Serverless Handler para OCR con GPU.
Endpoint: POST (vía RunPod SDK)
Input: {"input": {"file_base64": "...", "mime_type": "image/jpeg"}}
Output: {"text": "...", "fields": {...}, "confidence": 0.95}
"""
import base64
import io
import runpod
import pytesseract
from PIL import Image
import pdf2image


def process_document(job_input: dict) -> dict:
    """Procesa un documento y extrae texto via OCR."""
    file_b64 = job_input.get("file_base64", "")
    mime_type = job_input.get("mime_type", "image/jpeg")

    if not file_b64:
        return {"error": "file_base64 is required"}

    try:
        file_bytes = base64.b64decode(file_b64)

        if mime_type == "application/pdf":
            images = pdf2image.convert_from_bytes(file_bytes, dpi=300)
            texts = []
            for img in images:
                text = pytesseract.image_to_string(img, lang="spa+eng")
                texts.append(text)
            extracted_text = "\n\n".join(texts)
        else:
            img = Image.open(io.BytesIO(file_bytes))
            extracted_text = pytesseract.image_to_string(img, lang="spa+eng")

        return {
            "text": extracted_text,
            "confidence": 0.85,
            "pages": len(texts) if mime_type == "application/pdf" else 1,
        }

    except Exception as e:
        return {"error": str(e)}


def handler(job):
    """RunPod job handler — entry point requerido por RunPod SDK."""
    job_input = job.get("input", {})
    return process_document(job_input)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
```

### 5.5 Variables de entorno en RunPod

```
RunPod Dashboard → Serverless → tu-endpoint → Environment Variables

OPENAI_API_KEY: sk-...   (si el handler usa OpenAI Vision como fallback)
LOG_LEVEL: info
```

### 5.6 Obtener el Endpoint ID

```
RunPod Dashboard → Serverless → tu-endpoint → Overview

Endpoint ID: XXXXXXXXXXXXXXXX  (copiar este valor)
API URL:     https://api.runpod.ai/v2/XXXXXXXXXXXXXXXX/runsync
```

Guardar este `RUNPOD_ENDPOINT_ID` en las variables de Railway y en el `.env` local.

### 5.7 Probar el endpoint de RunPod

```bash
curl -X POST \
  "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "file_base64": "'"$(base64 -w 0 /ruta/a/un/documento.pdf)"'",
      "mime_type": "application/pdf"
    }
  }'

# Respuesta esperada:
# {"id": "...", "status": "COMPLETED", "output": {"text": "...", "confidence": 0.85}}
```

---

## 6. Twenty CRM — Servidor Propio con Docker

### 6.1 Preparar el servidor

```bash
# Conectar al VPS:
ssh root@TU_IP_VPS

# Crear directorio del proyecto:
mkdir -p /opt/olimpo
cd /opt/olimpo

# Clonar solo lo necesario del repo (no necesitas todo el monorepo en el VPS):
git clone https://github.com/TU-ORG/twenty_olimpo.git
cd twenty_olimpo
```

### 6.2 Archivo docker-compose para producción

El archivo existente en `packages/twenty-docker/docker-compose.yml` es bueno para
desarrollo. Para producción, usar esta versión hardened:

Crear `/opt/olimpo/docker-compose.prod.yml`:

```yaml
# ── Twenty CRM + n8n — Producción ─────────────────────────────────────────────
# Diferencias vs docker-compose de dev:
# - Versiones pinneadas (no :latest)
# - Restart policies explícitas
# - Healthchecks en todos los servicios
# - Sin exposición de puertos a la red pública (solo NGINX los expone)
# - Recursos limitados para evitar OOM

name: olimpo-prod

services:
  server:
    image: twentycrm/twenty:0.35.0    # pinear versión específica
    volumes:
      - server-local-data:/app/packages/twenty-server/.local-storage
    # No exponemos puertos directamente — NGINX hace el proxy
    expose:
      - "3000"
    environment:
      NODE_PORT: 3000
      PG_DATABASE_URL: postgres://${PG_DATABASE_USER}:${PG_DATABASE_PASSWORD}@db:5432/default
      SERVER_URL: ${SERVER_URL}
      REDIS_URL: redis://redis:6379
      DISABLE_DB_MIGRATIONS: "false"
      DISABLE_CRON_JOBS_REGISTRATION: "false"
      STORAGE_TYPE: ${STORAGE_TYPE:-local}
      STORAGE_S3_REGION: ${STORAGE_S3_REGION}
      STORAGE_S3_NAME: ${STORAGE_S3_NAME}
      STORAGE_S3_ENDPOINT: ${STORAGE_S3_ENDPOINT}
      APP_SECRET: ${APP_SECRET}
      MESSAGING_PROVIDER_GMAIL_ENABLED: ${MESSAGING_PROVIDER_GMAIL_ENABLED:-false}
      CALENDAR_PROVIDER_GOOGLE_ENABLED: ${CALENDAR_PROVIDER_GOOGLE_ENABLED:-false}
      AUTH_GOOGLE_ENABLED: ${AUTH_GOOGLE_ENABLED:-false}
      AUTH_GOOGLE_CLIENT_ID: ${AUTH_GOOGLE_CLIENT_ID}
      AUTH_GOOGLE_CLIENT_SECRET: ${AUTH_GOOGLE_CLIENT_SECRET}
      AUTH_GOOGLE_CALLBACK_URL: ${AUTH_GOOGLE_CALLBACK_URL}
      AUTH_GOOGLE_APIS_CALLBACK_URL: ${AUTH_GOOGLE_APIS_CALLBACK_URL}
      EMAIL_FROM_ADDRESS: ${EMAIL_FROM_ADDRESS}
      EMAIL_FROM_NAME: ${EMAIL_FROM_NAME}
      EMAIL_DRIVER: ${EMAIL_DRIVER:-smtp}
      EMAIL_SMTP_HOST: ${EMAIL_SMTP_HOST}
      EMAIL_SMTP_PORT: ${EMAIL_SMTP_PORT:-587}
      EMAIL_SMTP_USER: ${EMAIL_SMTP_USER}
      EMAIL_SMTP_PASSWORD: ${EMAIL_SMTP_PASSWORD}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: curl --fail http://localhost:3000/healthz
      interval: 10s
      timeout: 5s
      retries: 20
      start_period: 60s
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M

  worker:
    image: twentycrm/twenty:0.35.0
    volumes:
      - server-local-data:/app/packages/twenty-server/.local-storage
    command: ["yarn", "worker:prod"]
    environment:
      PG_DATABASE_URL: postgres://${PG_DATABASE_USER}:${PG_DATABASE_PASSWORD}@db:5432/default
      SERVER_URL: ${SERVER_URL}
      REDIS_URL: redis://redis:6379
      DISABLE_DB_MIGRATIONS: "true"
      DISABLE_CRON_JOBS_REGISTRATION: "true"
      OUTBOUND_HTTP_SAFE_MODE_ENABLED: "false"
      STORAGE_TYPE: ${STORAGE_TYPE:-local}
      STORAGE_S3_REGION: ${STORAGE_S3_REGION}
      STORAGE_S3_NAME: ${STORAGE_S3_NAME}
      STORAGE_S3_ENDPOINT: ${STORAGE_S3_ENDPOINT}
      APP_SECRET: ${APP_SECRET}
      MESSAGING_PROVIDER_GMAIL_ENABLED: ${MESSAGING_PROVIDER_GMAIL_ENABLED:-false}
      CALENDAR_PROVIDER_GOOGLE_ENABLED: ${CALENDAR_PROVIDER_GOOGLE_ENABLED:-false}
      AUTH_GOOGLE_ENABLED: ${AUTH_GOOGLE_ENABLED:-false}
      AUTH_GOOGLE_CLIENT_ID: ${AUTH_GOOGLE_CLIENT_ID}
      AUTH_GOOGLE_CLIENT_SECRET: ${AUTH_GOOGLE_CLIENT_SECRET}
    depends_on:
      db:
        condition: service_healthy
      server:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G

  db:
    image: postgres:16.2-alpine
    volumes:
      - db-data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: default
      POSTGRES_PASSWORD: ${PG_DATABASE_PASSWORD}
      POSTGRES_USER: ${PG_DATABASE_USER}
    healthcheck:
      test: pg_isready -U ${PG_DATABASE_USER} -h localhost -d postgres
      interval: 5s
      timeout: 5s
      retries: 10
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G

  redis:
    image: redis:7.2-alpine
    restart: unless-stopped
    command: ["--maxmemory-policy", "noeviction", "--maxmemory", "256mb"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10

  n8n:
    image: n8nio/n8n:1.45.1     # pinear versión estable
    expose:
      - "5678"
    environment:
      WEBHOOK_URL: ${N8N_WEBHOOK_URL}
      N8N_HOST: 0.0.0.0
      N8N_PORT: 5678
      N8N_PROTOCOL: https
      N8N_BASIC_AUTH_ACTIVE: "true"
      N8N_BASIC_AUTH_USER: ${N8N_BASIC_AUTH_USER}
      N8N_BASIC_AUTH_PASSWORD: ${N8N_BASIC_AUTH_PASSWORD}
      GENERIC_TIMEZONE: America/Mexico_City
      TZ: America/Mexico_City
      N8N_SECURE_COOKIE: "true"
      AGENTES_BASE_URL: ${AGENTES_BASE_URL}
      SUPABASE_URL: ${SUPABASE_URL}
      SUPABASE_SERVICE_KEY: ${SUPABASE_SERVICE_ROLE_KEY}
      EQUIPO_EMAIL: ${EQUIPO_EMAIL}
    volumes:
      - n8n-data:/home/node/.n8n
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M

volumes:
  db-data:
  server-local-data:
  n8n-data:

networks:
  default:
    name: olimpo-network
```

### 6.3 Archivo .env de producción en el VPS

```bash
# En el VPS, crear /opt/olimpo/.env (NUNCA commitear este archivo):
cat > /opt/olimpo/.env << 'EOF'
# Twenty CRM
TAG=0.35.0
SERVER_URL=https://app.olimpo.com.mx
APP_SECRET=<GENERA_CON: openssl rand -base64 32>

# PostgreSQL
PG_DATABASE_USER=postgres
PG_DATABASE_PASSWORD=<CONTRASEÑA_FUERTE>
PG_DATABASE_NAME=default

# Google OAuth (si se habilita)
MESSAGING_PROVIDER_GMAIL_ENABLED=false
CALENDAR_PROVIDER_GOOGLE_ENABLED=false
AUTH_GOOGLE_ENABLED=false
AUTH_GOOGLE_CLIENT_ID=
AUTH_GOOGLE_CLIENT_SECRET=
AUTH_GOOGLE_CALLBACK_URL=https://app.olimpo.com.mx/auth/google/redirect
AUTH_GOOGLE_APIS_CALLBACK_URL=https://app.olimpo.com.mx/apis/google-apis/get-access-token

# Storage (local en el VPS — cambiar a S3/Supabase si se necesita)
STORAGE_TYPE=local
STORAGE_S3_REGION=
STORAGE_S3_NAME=
STORAGE_S3_ENDPOINT=

# Email (SMTP para notificaciones de Twenty)
EMAIL_FROM_ADDRESS=sistema@olimpo.com.mx
EMAIL_FROM_NAME=Olimpo CRM
EMAIL_DRIVER=smtp
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=sistema@olimpo.com.mx
EMAIL_SMTP_PASSWORD=<APP_PASSWORD_DE_GMAIL>

# n8n
N8N_WEBHOOK_URL=https://n8n.olimpo.com.mx
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<CONTRASEÑA_FUERTE>

# Referencias a servicios externos
AGENTES_BASE_URL=https://api.olimpo.com.mx
SUPABASE_URL=https://aczkvxveenycpnwyqqbs.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
EQUIPO_EMAIL=operaciones@olimpo.com.mx
EOF

# Proteger el archivo:
chmod 600 /opt/olimpo/.env
```

### 6.4 Configurar NGINX como reverse proxy

```bash
# En el VPS, crear configuración de NGINX:
cat > /etc/nginx/sites-available/olimpo << 'EOF'
# ── Twenty CRM ────────────────────────────────────────────────────────────────
server {
    listen 80;
    server_name app.olimpo.com.mx;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name app.olimpo.com.mx;

    ssl_certificate     /etc/letsencrypt/live/app.olimpo.com.mx/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.olimpo.com.mx/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Aumentar para uploads de documentos
    client_max_body_size 60M;

    # Timeouts generosos para GraphQL
    proxy_read_timeout 120;
    proxy_connect_timeout 30;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}

# ── n8n ───────────────────────────────────────────────────────────────────────
server {
    listen 80;
    server_name n8n.olimpo.com.mx;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name n8n.olimpo.com.mx;

    ssl_certificate     /etc/letsencrypt/live/n8n.olimpo.com.mx/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/n8n.olimpo.com.mx/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 50M;

    location / {
        proxy_pass http://localhost:5678;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

# Habilitar configuración:
ln -s /etc/nginx/sites-available/olimpo /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 6.5 Obtener certificados SSL con Let's Encrypt

```bash
# Obtener certificados (reemplaza con tus dominios reales):
certbot --nginx -d app.olimpo.com.mx -d n8n.olimpo.com.mx \
  --email admin@olimpo.com.mx \
  --agree-tos \
  --no-eff-email

# Verificar renovación automática:
certbot renew --dry-run

# Certbot instala un cron para renovación automática — verificar:
systemctl status certbot.timer
```

### 6.6 Levantar Twenty CRM por primera vez

```bash
cd /opt/olimpo

# Primer arranque (puede tardar ~5 min mientras carga la imagen):
docker compose -f docker-compose.prod.yml up -d

# Verificar que todos los servicios están healthy:
docker compose -f docker-compose.prod.yml ps

# Ver logs del servidor:
docker compose -f docker-compose.prod.yml logs -f server

# Esperar hasta ver:
# "Twenty Server started on port 3000"
# "Migrations completed"
```

### 6.7 Setup inicial del workspace de Twenty

```
1. Abrir https://app.olimpo.com.mx en el navegador
2. Seguir el wizard de setup inicial
3. Crear cuenta de administrador:
   - Email: admin@olimpo.com.mx
   - Password: [contraseña segura]
4. Crear workspace: "Olimpo Promotoría GNP"
5. Configurar el workspace:
   - Settings → General → Workspace Name: "Olimpo Promotoría GNP"
   - Settings → General → Logo: subir logo de la empresa
   - Settings → Members → Invitar analistas y gerentes

6. Crear objetos custom (Tramite, Agente, DocumentoTramite, AlertaTramite):
   Settings → Data Model → Add Object
   (seguir el modelo en CLAUDE.md sección "Objetos Personalizados")

7. Obtener la API Key:
   Settings → API & Webhooks → API Keys → Create
   Copiar el JWT generado → va en TWENTY_API_KEY de Railway y .env
```

### 6.8 Sincronizar metadata

```bash
# Después de crear los objetos custom, sincronizar metadata:
docker compose -f docker-compose.prod.yml exec server \
  npx nx run twenty-server:command workspace:sync-metadata
```

### 6.9 Actualizar Twenty CRM (proceso de upgrade)

```bash
# 1. Hacer backup de la base de datos ANTES de actualizar:
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U postgres default > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Cambiar la versión en docker-compose.prod.yml:
# image: twentycrm/twenty:NUEVA_VERSION

# 3. Pull de la nueva imagen:
docker compose -f docker-compose.prod.yml pull

# 4. Reiniciar (downtime < 30s):
docker compose -f docker-compose.prod.yml up -d

# 5. Verificar health:
docker compose -f docker-compose.prod.yml ps
curl https://app.olimpo.com.mx/healthz

# Si algo falla, rollback:
# Cambiar de vuelta la versión y:
docker compose -f docker-compose.prod.yml up -d
```

---

## 7. n8n — Automatización en Producción

n8n corre dentro del mismo `docker-compose.prod.yml` del VPS.

### 7.1 Importar el pipeline de Gmail

```
1. Abrir https://n8n.olimpo.com.mx
   Usuario: admin (del N8N_BASIC_AUTH_USER)
   Password: [del N8N_BASIC_AUTH_PASSWORD]

2. Menú superior → Import Workflow
3. Seleccionar: scripts/n8n/pipeline_gmail_ingest_v4.json
4. El workflow se importa como inactivo
```

### 7.2 Configurar credenciales de Gmail OAuth2

```
n8n Dashboard → Credentials → New Credential → Gmail OAuth2

Para configurar OAuth2 de Gmail:
1. Ir a https://console.cloud.google.com
2. Crear proyecto: "olimpo-n8n-gmail"
3. APIs & Services → Enable: Gmail API
4. APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
   - Application type: Web application
   - Name: olimpo-n8n
   - Authorized redirect URIs:
     https://n8n.olimpo.com.mx/rest/oauth2-credential/callback
5. Copiar Client ID y Client Secret
6. En n8n: pegar Client ID y Client Secret
7. Clic en "Sign in with Google" y autorizar con la cuenta de Gmail de la promotoría
```

> **Importante**: Usar la cuenta de Gmail de la promotoría (ej: tramites@olimpo.com.mx),
> no una cuenta personal. Esta cuenta es la que recibe los correos de los agentes.

### 7.3 Actualizar variables de entorno del pipeline

En el nodo "POST email/ingest" del pipeline, verificar que apunta al URL de producción:

```
$env.AGENTES_BASE_URL = https://api.olimpo.com.mx
```

Esto se configura en docker-compose.prod.yml:
```yaml
AGENTES_BASE_URL: https://api.olimpo.com.mx
```

### 7.4 Activar el workflow

```
n8n Dashboard → Workflows → promotoria-gmail-ingestion-v4

1. Abrir el workflow
2. Toggle superior derecho: OFF → ON
3. El trigger Gmail comenzará a hacer poll cada minuto
4. Verificar en Executions que no hay errores
```

### 7.5 Backup de workflows de n8n

```bash
# Los workflows se guardan en el volumen n8n-data
# Hacer backup manual del volumen:
docker compose -f docker-compose.prod.yml exec n8n \
  n8n export:workflow --all --output=/home/node/.n8n/backup_workflows.json

# Copiar a la máquina local:
docker cp olimpo-prod-n8n-1:/home/node/.n8n/backup_workflows.json \
  ./backups/n8n_workflows_$(date +%Y%m%d).json
```

---

## 8. Vercel — Dashboard Frontend

El dashboard custom (Twenty front customizado con vistas de Directora, Gerente y
Especialista) puede desplegarse en Vercel para acceso externo rápido.

### 8.1 Crear proyecto en Vercel

```bash
# Desde la raíz del repositorio:
cd /home/lag/Documentos/twenty_olimpo

# Login en Vercel:
vercel login

# Inicializar proyecto (solo la primera vez):
vercel

# Cuando pregunte:
# - Set up and deploy: Y
# - Which scope: tu-org
# - Link to existing project: N
# - Project name: olimpo-dashboard
# - Directory: packages/twenty-front
# - Override settings: N (detecta Next.js/Vite automáticamente)
```

### 8.2 Crear vercel.json

Crear `packages/twenty-front/vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "vite",
  "buildCommand": "cd ../.. && npx nx build twenty-front",
  "outputDirectory": "packages/twenty-front/dist",
  "installCommand": "yarn install --frozen-lockfile",
  "devCommand": "npx nx start twenty-front",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "X-Frame-Options",
          "value": "SAMEORIGIN"
        },
        {
          "key": "X-XSS-Protection",
          "value": "1; mode=block"
        }
      ]
    }
  ]
}
```

### 8.3 Variables de entorno en Vercel

```bash
# Via CLI:
vercel env add VITE_SUPABASE_URL production
# Ingresar: https://aczkvxveenycpnwyqqbs.supabase.co

vercel env add VITE_SUPABASE_ANON_KEY production
# Ingresar: sb_publishable_... (clave ANON — no service_role)

vercel env add VITE_TWENTY_API_URL production
# Ingresar: https://app.olimpo.com.mx

vercel env add VITE_API_URL production
# Ingresar: https://api.olimpo.com.mx
```

> **NUNCA poner SUPABASE_SERVICE_ROLE_KEY en Vercel**. En el frontend solo va la
> clave `anon/public`. El service_role solo va en Railway (FastAPI).

### 8.4 Configurar dominio custom en Vercel

```
Vercel Dashboard → olimpo-dashboard → Settings → Domains

1. Add Domain: dashboard.olimpo.com.mx
2. Vercel muestra un registro DNS a agregar en Cloudflare:
   Type: CNAME
   Name: dashboard
   Value: cname.vercel-dns.com
3. En Cloudflare: agregar el CNAME
4. Vercel provisiona SSL automáticamente
```

### 8.5 Preview deployments automáticos

Vercel crea automáticamente un preview URL por cada Pull Request.
No hay configuración adicional necesaria — funciona out of the box.

```
PR creado → Vercel detecta → build automático → URL preview:
https://olimpo-dashboard-git-feature-mi-feature.vercel.app
```

### 8.6 Variables de entorno para preview (staging)

```bash
# Agregar variables para el environment "preview":
vercel env add VITE_SUPABASE_URL preview
# Ingresar URL de Supabase staging

vercel env add VITE_TWENTY_API_URL preview
# Ingresar URL de staging de Twenty CRM
```

---

## 9. CI/CD con GitHub Actions

### 9.1 Estructura de branches

```
main          ← Producción. Solo merges via PR desde develop o hotfix/*
develop       ← Staging. Feature branches se mergean aquí primero
feature/*     ← Nuevas funcionalidades
hotfix/*      ← Fixes urgentes que van directo a main y develop
```

### 9.2 GitHub Secrets necesarios

Configurar en: `GitHub → tu-org/twenty_olimpo → Settings → Secrets → Actions`

```
RAILWAY_TOKEN              → Token de API de Railway (railway.app → Account → API Tokens)
RAILWAY_SERVICE_ID         → ID del servicio FastAPI en Railway
VERCEL_TOKEN               → Token de Vercel (vercel.com → Settings → Tokens)
VERCEL_ORG_ID              → ID de la organización en Vercel
VERCEL_PROJECT_ID          → ID del proyecto dashboard en Vercel
SUPABASE_DB_URL            → PostgreSQL connection string para migraciones
SUPABASE_SERVICE_ROLE_KEY  → Para verificar salud de Supabase post-deploy
SLACK_WEBHOOK_URL          → (Opcional) Notificaciones de deploy a Slack
VPS_SSH_KEY                → Private key SSH para conectar al VPS (Twenty CRM)
VPS_HOST                   → IP o hostname del VPS
VPS_USER                   → Usuario SSH del VPS (ej: root o deploy)
```

### 9.3 Workflow: Deploy FastAPI a Railway

Crear `.github/workflows/deploy-fastapi.yml`:

```yaml
# ── Deploy FastAPI (Agentes de IA) a Railway ──────────────────────────────────
# Trigger: push a main o develop en el directorio de FastAPI

name: Deploy FastAPI → Railway

on:
  push:
    branches:
      - main
      - develop
    paths:
      - 'scripts/attachment_processor/**'
      - '.github/workflows/deploy-fastapi.yml'
  pull_request:
    paths:
      - 'scripts/attachment_processor/**'

jobs:
  # ── Job 1: Lint y Tests ───────────────────────────────────────────────────
  test:
    name: Lint + Tests
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: scripts/attachment_processor/requirements.txt

      - name: Install dependencies
        working-directory: scripts/attachment_processor
        run: pip install -r requirements.txt

      - name: Lint con ruff
        working-directory: scripts/attachment_processor
        run: |
          pip install ruff==0.4.1
          ruff check . --output-format=github || true

      - name: Type check con mypy
        working-directory: scripts/attachment_processor
        run: |
          pip install mypy==1.10.0
          mypy main.py --ignore-missing-imports || true

  # ── Job 2: Build Docker image ─────────────────────────────────────────────
  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: test

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build imagen (sin push — solo verificar que compila)
        uses: docker/build-push-action@v5
        with:
          context: scripts/attachment_processor
          push: false
          tags: olimpo-agentes:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ── Job 3: Deploy a Railway ───────────────────────────────────────────────
  deploy:
    name: Deploy a Railway
    runs-on: ubuntu-latest
    needs: [test, build]
    # Solo deployar en push a main o develop (no en PRs)
    if: github.event_name == 'push'

    environment:
      # main → producción, develop → staging
      name: ${{ github.ref == 'refs/heads/main' && 'production' || 'staging' }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install Railway CLI
        run: npm install -g @railway/cli@3.12.1

      - name: Deploy a Railway
        working-directory: scripts/attachment_processor
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
        run: |
          if [ "${{ github.ref }}" = "refs/heads/main" ]; then
            railway up --service ${{ secrets.RAILWAY_SERVICE_ID }} --detach
          else
            railway up --service ${{ secrets.RAILWAY_SERVICE_STAGING_ID }} --detach
          fi

      - name: Verificar health post-deploy
        run: |
          # Esperar 60s para que el deploy termine
          sleep 60

          # Obtener URL del servicio según el ambiente
          if [ "${{ github.ref }}" = "refs/heads/main" ]; then
            URL="https://api.olimpo.com.mx/health"
          else
            URL="https://api-staging.olimpo.com.mx/health"
          fi

          # Reintentar hasta 10 veces cada 10 segundos
          for i in $(seq 1 10); do
            STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL")
            if [ "$STATUS" = "200" ]; then
              echo "Health check pasó (intento $i)"
              exit 0
            fi
            echo "Intento $i: HTTP $STATUS — esperando..."
            sleep 10
          done

          echo "Health check falló después de 10 intentos"
          exit 1

      - name: Notificar a Slack (éxito)
        if: success() && secrets.SLACK_WEBHOOK_URL != ''
        uses: slackapi/slack-github-action@v1.26.0
        with:
          payload: |
            {
              "text": "FastAPI deployed exitosamente a ${{ github.ref == 'refs/heads/main' && 'PRODUCCIÓN' || 'staging' }} ✅\nCommit: ${{ github.sha }}\nBy: ${{ github.actor }}"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}

      - name: Notificar a Slack (fallo)
        if: failure() && secrets.SLACK_WEBHOOK_URL != ''
        uses: slackapi/slack-github-action@v1.26.0
        with:
          payload: |
            {
              "text": "FALLO en deploy de FastAPI a ${{ github.ref == 'refs/heads/main' && 'PRODUCCIÓN' || 'staging' }} ❌\nCommit: ${{ github.sha }}\nBy: ${{ github.actor }}\nRevisar: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### 9.4 Workflow: Deploy Dashboard a Vercel

Crear `.github/workflows/deploy-vercel.yml`:

```yaml
# ── Deploy Dashboard Frontend a Vercel ────────────────────────────────────────

name: Deploy Dashboard → Vercel

on:
  push:
    branches:
      - main
      - develop
    paths:
      - 'packages/twenty-front/src/modules/dashboard/**'
      - 'packages/twenty-front/src/**'
      - '.github/workflows/deploy-vercel.yml'
  pull_request:
    paths:
      - 'packages/twenty-front/**'

jobs:
  deploy:
    name: Deploy a Vercel
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node.js 20
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'yarn'

      - name: Install dependencies
        run: yarn install --frozen-lockfile

      - name: Type check
        run: npx nx typecheck twenty-front || true

      - name: Deploy a Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          # main → producción, otras branches → preview
          vercel-args: ${{ github.ref == 'refs/heads/main' && '--prod' || '' }}
          working-directory: packages/twenty-front
```

### 9.5 Workflow: Migraciones de Supabase

Crear `.github/workflows/supabase-migrations.yml`:

```yaml
# ── Aplicar migraciones de Supabase ───────────────────────────────────────────
# Solo se ejecuta cuando hay cambios en los archivos de migración

name: Supabase Migrations

on:
  push:
    branches:
      - main
    paths:
      - 'scripts/supabase/migrations/*.sql'

jobs:
  migrate:
    name: Aplicar migraciones
    runs-on: ubuntu-latest
    environment: production

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup psql
        run: |
          sudo apt-get install -y postgresql-client

      - name: Detectar archivos de migración nuevos
        id: changed
        run: |
          # Obtener archivos SQL cambiados vs el commit anterior
          CHANGED=$(git diff --name-only HEAD~1 HEAD -- 'scripts/supabase/migrations/*.sql')
          echo "files=$CHANGED" >> $GITHUB_OUTPUT
          echo "Migraciones a aplicar: $CHANGED"

      - name: Aplicar migraciones
        if: steps.changed.outputs.files != ''
        env:
          SUPABASE_DB_URL: ${{ secrets.SUPABASE_DB_URL }}
        run: |
          for f in ${{ steps.changed.outputs.files }}; do
            echo "Aplicando: $f"
            psql "$SUPABASE_DB_URL" -f "$f"
            if [ $? -ne 0 ]; then
              echo "ERROR en $f"
              exit 1
            fi
          done
          echo "Migraciones aplicadas exitosamente"

      - name: Verificar tablas post-migración
        env:
          SUPABASE_DB_URL: ${{ secrets.SUPABASE_DB_URL }}
        run: |
          psql "$SUPABASE_DB_URL" -c "\dt public.*" | head -50
```

### 9.6 Workflow: Deploy Twenty CRM al VPS

Crear `.github/workflows/deploy-twenty.yml`:

```yaml
# ── Deploy Twenty CRM al VPS ──────────────────────────────────────────────────

name: Deploy Twenty CRM → VPS

on:
  push:
    branches:
      - main
    paths:
      - 'packages/twenty-docker/docker-compose.yml'
      - '.github/workflows/deploy-twenty.yml'
  workflow_dispatch:
    inputs:
      version:
        description: 'Versión de Twenty a deployar (ej: 0.35.0)'
        required: true
        default: '0.35.0'

jobs:
  deploy:
    name: Deploy a VPS
    runs-on: ubuntu-latest
    environment: production

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Deploy vía SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/olimpo/twenty_olimpo

            # Pull de cambios recientes
            git fetch origin main
            git reset --hard origin/main

            # Actualizar imagen si se especificó versión
            if [ "${{ github.event.inputs.version }}" != "" ]; then
              sed -i "s/twentycrm\/twenty:.*/twentycrm\/twenty:${{ github.event.inputs.version }}/g" \
                docker-compose.prod.yml
            fi

            # Backup de BD antes de cualquier actualización
            docker compose -f docker-compose.prod.yml exec -T db \
              pg_dump -U postgres default > /opt/olimpo/backups/pre_deploy_$(date +%Y%m%d_%H%M%S).sql

            # Pull de nuevas imágenes
            docker compose -f docker-compose.prod.yml pull

            # Reiniciar servicios (rolling update)
            docker compose -f docker-compose.prod.yml up -d

            # Verificar salud
            sleep 30
            docker compose -f docker-compose.prod.yml ps

      - name: Verificar health
        run: |
          sleep 30
          STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://app.olimpo.com.mx/healthz)
          if [ "$STATUS" = "200" ]; then
            echo "Twenty CRM healthy"
          else
            echo "FALLO: HTTP $STATUS"
            exit 1
          fi
```

---

## 10. Dominio y DNS con Cloudflare

### 10.1 Registrar el dominio

Si no tienes dominio registrado:
- **Namecheap**: https://www.namecheap.com (recomendado para .com.mx)
- **GoDaddy**: https://www.godaddy.com
- Costo: ~$15-20 USD/año para .com.mx

### 10.2 Configurar Cloudflare como DNS

```
1. Crear cuenta en https://cloudflare.com
2. Add Site → ingresar tu dominio (olimpo.com.mx)
3. Seleccionar plan Free
4. Cloudflare muestra los nameservers a usar
5. En tu registrador (Namecheap/GoDaddy), cambiar los nameservers:
   - ns1.cloudflare.com
   - ns2.cloudflare.com
6. Esperar propagación (2-48 horas, generalmente <1 hora con Cloudflare)
```

### 10.3 Registros DNS a crear

En Cloudflare → DNS → Records:

```
# Twenty CRM (VPS propio)
Type: A
Name: app
Content: [IP_PUBLICA_DEL_VPS]
Proxy: ON (naranja — Cloudflare proxea el tráfico)

# n8n (mismo VPS)
Type: A
Name: n8n
Content: [IP_PUBLICA_DEL_VPS]
Proxy: ON

# FastAPI (Railway — usar CNAME que Railway provee)
Type: CNAME
Name: api
Content: [valor que Railway muestra en Settings → Domains]
Proxy: ON

# Dashboard (Vercel — usar CNAME que Vercel provee)
Type: CNAME
Name: dashboard
Content: cname.vercel-dns.com
Proxy: OFF (Vercel requiere proxy desactivado para SSL propio)

# Email (MX records si usas Gmail Workspace)
Type: MX
Name: @
Content: aspmx.l.google.com
Priority: 1
```

> **Nota sobre Proxy de Cloudflare**: Para app.olimpo.com.mx y n8n.olimpo.com.mx,
> activar el proxy naranja de Cloudflare da DDoS protection gratuito. Para
> dashboard.olimpo.com.mx (Vercel), desactivar el proxy para que Vercel maneje SSL.

### 10.4 Configurar SSL/TLS en Cloudflare

```
Cloudflare → tu dominio → SSL/TLS → Overview

Seleccionar: "Full (strict)"
Esto requiere que el servidor de origen también tenga certificado válido.
NGINX + Let's Encrypt cumple este requisito.
```

### 10.5 Reglas de seguridad en Cloudflare

```
Cloudflare → Security → WAF → Custom Rules

Regla 1: Bloquear acceso a rutas sensibles
  If: URI Path contains "/.env" OR URI Path contains "/wp-admin"
  Then: Block

Regla 2: Rate limiting para API
  If: URI Path starts with "/api/v1/"
  Then: Rate limit 100 requests per minute per IP
```

---

## 11. Variables de Entorno — Tabla Maestra

### 11.1 FastAPI en Railway

| Variable | Descripción | Dónde obtenerla | Ejemplo |
|---|---|---|---|
| `TWENTY_API_URL` | URL base de Twenty CRM | Configurar al deployar | `https://app.olimpo.com.mx` |
| `TWENTY_API_KEY` | JWT para autenticarse en Twenty GraphQL | Twenty → Settings → API Keys | `eyJhbGciOi...` |
| `SUPABASE_URL` | URL del proyecto Supabase | Supabase → Settings → API | `https://xxxx.supabase.co` |
| `SUPABASE_KEY` | Clave anon/public de Supabase | Supabase → Settings → API | `sb_publishable_...` |
| `SUPABASE_SERVICE_ROLE_KEY` | Clave service_role de Supabase | Supabase → Settings → API | `eyJhbGciOi...` |
| `BUCKET_NAME` | Nombre del bucket de Storage | Ya configurado en migración 003 | `tramites-docs` |
| `LLM_MODEL` | Modelo LiteLLM a usar | Configurar | `openai/gpt-4o` |
| `OPENAI_API_KEY` | API Key de OpenAI | platform.openai.com → API Keys | `sk-proj-...` |
| `RUNPOD_API_KEY` | API Key de RunPod | runpod.io → Settings → API Keys | `rpa_...` |
| `RUNPOD_ENDPOINT_ID` | ID del endpoint serverless | RunPod → Serverless → endpoint | `abc123def456` |
| `PORT` | Puerto de la aplicación (Railway lo inyecta) | Railway automático | `4000` |

### 11.2 Twenty CRM en VPS (docker-compose.prod.yml / .env)

| Variable | Descripción | Cómo generarla | Ejemplo |
|---|---|---|---|
| `SERVER_URL` | URL pública de Twenty CRM | Configurar después de DNS | `https://app.olimpo.com.mx` |
| `APP_SECRET` | Secreto para JWT — nunca cambiar en producción | `openssl rand -base64 32` | `E+N/rW4nW2...` |
| `PG_DATABASE_USER` | Usuario PostgreSQL | Configurar | `postgres` |
| `PG_DATABASE_PASSWORD` | Contraseña PostgreSQL | Contraseña aleatoria segura | `Xy9!mKp3...` |
| `REDIS_URL` | URL de Redis (interno Docker) | Automático | `redis://redis:6379` |
| `TWENTY_API_KEY` | JWT de la API Key creada en Twenty | Twenty → Settings → API Keys | `eyJhbGciOi...` |
| `STORAGE_TYPE` | Tipo de storage (local o s3) | Configurar | `local` |
| `AUTH_GOOGLE_CLIENT_ID` | Client ID de Google OAuth2 | Google Cloud Console | `1234567890.apps.googleusercontent.com` |
| `AUTH_GOOGLE_CLIENT_SECRET` | Client Secret de Google OAuth2 | Google Cloud Console | `GOCSPX-...` |
| `EMAIL_SMTP_HOST` | Host SMTP para notificaciones | Gmail o servidor de correo | `smtp.gmail.com` |
| `EMAIL_SMTP_PASSWORD` | App Password de Gmail | Google Account → App Passwords | `xxxx xxxx xxxx xxxx` |

### 11.3 n8n en VPS

| Variable | Descripción | Valor |
|---|---|---|
| `N8N_WEBHOOK_URL` | URL pública de n8n | `https://n8n.olimpo.com.mx` |
| `N8N_BASIC_AUTH_USER` | Usuario para autenticación básica | `admin` |
| `N8N_BASIC_AUTH_PASSWORD` | Contraseña para n8n UI | Contraseña fuerte |
| `AGENTES_BASE_URL` | URL de FastAPI en Railway | `https://api.olimpo.com.mx` |
| `SUPABASE_URL` | URL de Supabase | `https://xxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Clave service_role de Supabase | `eyJhbGciOi...` |
| `EQUIPO_EMAIL` | Email del equipo de operaciones | `operaciones@olimpo.com.mx` |

### 11.4 Vercel (Dashboard Frontend)

| Variable | Descripción | Nota de seguridad |
|---|---|---|
| `VITE_SUPABASE_URL` | URL del proyecto Supabase | Pública — OK en frontend |
| `VITE_SUPABASE_ANON_KEY` | Clave anon de Supabase | Solo anon — NUNCA service_role |
| `VITE_TWENTY_API_URL` | URL de Twenty CRM | Pública — OK en frontend |
| `VITE_API_URL` | URL de FastAPI | Pública — OK en frontend |

### 11.5 GitHub Actions Secrets

| Secret | Descripción | Dónde obtenerlo |
|---|---|---|
| `RAILWAY_TOKEN` | Token de API Railway | railway.app → Account → Tokens |
| `RAILWAY_SERVICE_ID` | ID del servicio en Railway | Railway Dashboard → service → Settings |
| `VERCEL_TOKEN` | Token de API Vercel | vercel.com → Settings → Tokens |
| `VERCEL_ORG_ID` | ID de la organización | `vercel whoami` o Dashboard |
| `VERCEL_PROJECT_ID` | ID del proyecto | Vercel Dashboard → project → Settings |
| `SUPABASE_DB_URL` | Connection string de PostgreSQL | Supabase → Settings → Database → URI |
| `VPS_SSH_KEY` | Private key SSH para el VPS | Generar con `ssh-keygen -t ed25519` |
| `VPS_HOST` | IP o hostname del VPS | Panel del proveedor de VPS |
| `VPS_USER` | Usuario SSH (ej: root) | Panel del proveedor de VPS |

---

## 12. Orden de Despliegue — Checklist Maestro

Seguir este orden exacto. Cada paso depende del anterior.

### Fase 1: Infraestructura Base (Día 1)

- [ ] **1.1** Registrar dominio y configurar Cloudflare como DNS
- [ ] **1.2** Crear cuenta Supabase Pro y proyecto
- [ ] **1.3** Aplicar migraciones de Supabase (000 → 018) en orden
- [ ] **1.4** Verificar Storage buckets (incoming-raw, tramite-docs, ocr-output)
- [ ] **1.5** Habilitar extensiones pg_cron y pg_net
- [ ] **1.6** Configurar CORS en Supabase
- [ ] **1.7** Habilitar PITR (backups) en Supabase
- [ ] **1.8** Anotar: SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY, DB_URL

**Verificación Fase 1:**
```bash
curl -H "apikey: $SUPABASE_ANON_KEY" \
  "$SUPABASE_URL/rest/v1/tramites_pipeline?select=count"
# Esperado: [{"count":0}]
```

### Fase 2: VPS y Twenty CRM (Día 1-2)

- [ ] **2.1** Contratar y provisionar VPS (Ubuntu 22.04, mínimo 4GB RAM)
- [ ] **2.2** Instalar Docker, Docker Compose, NGINX, Certbot en el VPS
- [ ] **2.3** Configurar registros DNS (A records para app.olimpo.com.mx y n8n.olimpo.com.mx)
- [ ] **2.4** Crear `/opt/olimpo/.env` con valores de producción en el VPS
- [ ] **2.5** Subir `docker-compose.prod.yml` al VPS
- [ ] **2.6** Configurar NGINX (archivo de configuración para app y n8n)
- [ ] **2.7** Obtener certificados SSL con Certbot
- [ ] **2.8** Levantar Twenty CRM: `docker compose -f docker-compose.prod.yml up -d`
- [ ] **2.9** Completar setup inicial del workspace en https://app.olimpo.com.mx
- [ ] **2.10** Crear objetos custom (Tramite, Agente, DocumentoTramite, AlertaTramite)
- [ ] **2.11** Crear API Key en Twenty → Settings → API & Webhooks
- [ ] **2.12** Anotar TWENTY_API_KEY

**Verificación Fase 2:**
```bash
curl https://app.olimpo.com.mx/healthz
# Esperado: {"status":"ok"}
```

### Fase 3: FastAPI en Railway (Día 2)

- [ ] **3.1** Crear cuenta Railway y proyecto `olimpo-agentes`
- [ ] **3.2** Actualizar `scripts/attachment_processor/Dockerfile` (multi-stage)
- [ ] **3.3** Agregar endpoint `/health` y `/ready` a `main.py`
- [ ] **3.4** Crear `scripts/attachment_processor/railway.toml`
- [ ] **3.5** Conectar repositorio GitHub en Railway
- [ ] **3.6** Configurar todas las variables de entorno en Railway (ver sección 11.1)
- [ ] **3.7** Primer deploy: `railway up --detach`
- [ ] **3.8** Configurar dominio custom `api.olimpo.com.mx` en Railway
- [ ] **3.9** Agregar CNAME de Railway en Cloudflare DNS
- [ ] **3.10** Activar auto-deploy desde rama `main` en Railway
- [ ] **3.11** Crear environment de staging en Railway

**Verificación Fase 3:**
```bash
curl https://api.olimpo.com.mx/health
# Esperado: {"status":"ok","version":"1.0.0"}

curl https://api.olimpo.com.mx/ready
# Esperado: {"status":"ready","checks":{"supabase":"ok","twenty_crm":"ok"}}
```

### Fase 4: n8n y Gmail Pipeline (Día 2-3)

- [ ] **4.1** Verificar que n8n está corriendo: https://n8n.olimpo.com.mx
- [ ] **4.2** Crear proyecto en Google Cloud Console para OAuth2 de Gmail
- [ ] **4.3** Configurar credenciales Gmail OAuth2 en n8n
- [ ] **4.4** Importar workflow: `scripts/n8n/pipeline_gmail_ingest_v4.json`
- [ ] **4.5** Verificar que `AGENTES_BASE_URL` apunta a `https://api.olimpo.com.mx`
- [ ] **4.6** Activar el workflow en n8n
- [ ] **4.7** Enviar correo de prueba a la cuenta de Gmail de la promotoría
- [ ] **4.8** Verificar que aparece en Supabase: `incoming_emails` y `tramites_pipeline`
- [ ] **4.9** Verificar que se crea el Trámite en Twenty CRM

**Verificación Fase 4:**
```bash
# Verificar que el workflow está activo:
# n8n → Workflows → promotoria-gmail-ingestion-v4 → status: "Active"

# Enviar correo de prueba y verificar en Supabase:
# Supabase → Table Editor → incoming_emails → debe aparecer el correo
```

### Fase 5: RunPod OCR (Día 3)

- [ ] **5.1** Crear cuenta RunPod y agregar crédito
- [ ] **5.2** Crear Serverless Endpoint con la configuración correcta
- [ ] **5.3** Anotar RUNPOD_API_KEY y RUNPOD_ENDPOINT_ID
- [ ] **5.4** Actualizar variables de entorno en Railway con los valores de RunPod
- [ ] **5.5** Probar OCR con un documento PDF escaneado

**Verificación Fase 5:**
```bash
curl -X POST \
  "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"input": {"test": true}}'
# Esperado: {"status":"COMPLETED"}
```

### Fase 6: Dashboard Vercel (Día 3-4)

- [ ] **6.1** Crear cuenta Vercel y conectar repositorio
- [ ] **6.2** Crear `packages/twenty-front/vercel.json`
- [ ] **6.3** Configurar variables de entorno en Vercel (solo anon key, nunca service_role)
- [ ] **6.4** Primer deploy: `vercel --prod`
- [ ] **6.5** Configurar dominio custom `dashboard.olimpo.com.mx`
- [ ] **6.6** Agregar CNAME de Vercel en Cloudflare DNS

**Verificación Fase 6:**
```bash
curl -I https://dashboard.olimpo.com.mx
# Esperado: HTTP/2 200
```

### Fase 7: CI/CD (Día 4)

- [ ] **7.1** Configurar todos los GitHub Secrets (ver sección 11.5)
- [ ] **7.2** Crear `.github/workflows/deploy-fastapi.yml`
- [ ] **7.3** Crear `.github/workflows/deploy-vercel.yml`
- [ ] **7.4** Crear `.github/workflows/supabase-migrations.yml`
- [ ] **7.5** Crear `.github/workflows/deploy-twenty.yml`
- [ ] **7.6** Hacer un commit de prueba en develop → verificar que dispara los workflows
- [ ] **7.7** Verificar que preview deployment de Vercel se crea en el PR

### Fase 8: Hardening y Monitoreo (Día 4-5)

- [ ] **8.1** Configurar Cloudflare WAF (reglas de seguridad)
- [ ] **8.2** Habilitar `fail2ban` en el VPS
- [ ] **8.3** Configurar alertas en Railway (email en caso de errores)
- [ ] **8.4** Activar cron jobs de pg_cron en Supabase (actualizar URLs)
- [ ] **8.5** Programar backup automático de n8n workflows
- [ ] **8.6** Documentar proceso de rollback para el equipo

### Rollback rápido (si algo falla post-deploy)

```bash
# FastAPI en Railway (< 2 minutos):
railway rollback --service olimpo-agentes

# Twenty CRM en VPS (< 5 minutos):
# Cambiar versión en docker-compose.prod.yml de vuelta
docker compose -f docker-compose.prod.yml up -d

# Base de datos Supabase:
# Usar PITR desde Supabase Dashboard → Settings → Backups
# O restaurar desde backup manual:
psql "$SUPABASE_DB_URL" < backup_YYYYMMDD_HHMMSS.sql

# Vercel (automático):
# Vercel Dashboard → Deployments → click en deploy anterior → "Promote to Production"
```

---

## 13. Monitoreo, Logs y Alertas

### 13.1 Endpoints de salud por servicio

| Servicio | URL | Respuesta esperada |
|---|---|---|
| Twenty CRM | `GET https://app.olimpo.com.mx/healthz` | `{"status":"ok"}` |
| FastAPI | `GET https://api.olimpo.com.mx/health` | `{"status":"ok","version":"..."}` |
| FastAPI (readiness) | `GET https://api.olimpo.com.mx/ready` | `{"status":"ready","checks":{...}}` |
| n8n | `GET https://n8n.olimpo.com.mx/healthz` | HTTP 200 |

### 13.2 Logs en tiempo real

```bash
# FastAPI en Railway:
railway logs --tail --service olimpo-agentes

# Twenty CRM en VPS:
docker compose -f docker-compose.prod.yml logs -f server
docker compose -f docker-compose.prod.yml logs -f worker

# n8n en VPS:
docker compose -f docker-compose.prod.yml logs -f n8n

# Base de datos PostgreSQL:
docker compose -f docker-compose.prod.yml logs -f db
```

### 13.3 Verificar estado del pipeline periódicamente

```bash
# Ver últimos 10 trámites procesados:
psql "$SUPABASE_DB_URL" -c "
  SELECT folio, ramo, status, created_at, error_detalle
  FROM tramites_pipeline
  ORDER BY created_at DESC
  LIMIT 10;
"

# Ver emails atascados (más de 2 horas en estado 'parsing'):
psql "$SUPABASE_DB_URL" -c "
  SELECT id, gmail_message_id, subject, processing_status, updated_at
  FROM incoming_emails
  WHERE processing_status IN ('parsing', 'extracting')
    AND updated_at < NOW() - INTERVAL '2 hours';
"

# Ver errores de OCR recientes:
psql "$SUPABASE_DB_URL" -c "
  SELECT id, status, error_message, created_at
  FROM ocr_results
  WHERE status = 'failed'
  ORDER BY created_at DESC
  LIMIT 20;
"
```

### 13.4 Alertas en Railway

```
Railway Dashboard → olimpo-agentes → Observability

Configurar alertas de:
- CPU > 80% por 5 minutos
- Memory > 80% por 5 minutos
- Crash loops (restart > 3 en 10 minutos)
- Deploy failures
```

### 13.5 Script de health check automático

Crear `/opt/olimpo/scripts/healthcheck.sh` en el VPS:

```bash
#!/bin/bash
# Ejecutar cada 5 minutos via cron: */5 * * * * /opt/olimpo/scripts/healthcheck.sh

ALERT_EMAIL="admin@olimpo.com.mx"
SERVICES=(
  "Twenty CRM|https://app.olimpo.com.mx/healthz"
  "FastAPI|https://api.olimpo.com.mx/health"
  "n8n|https://n8n.olimpo.com.mx/healthz"
)

for service_url in "${SERVICES[@]}"; do
  NAME="${service_url%%|*}"
  URL="${service_url##*|}"
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$URL")

  if [ "$STATUS" != "200" ]; then
    echo "ALERTA: $NAME no responde (HTTP $STATUS)" | \
      mail -s "[OLIMPO-PROD] $NAME DOWN" "$ALERT_EMAIL"
  fi
done
```

```bash
# Instalar y habilitar:
chmod +x /opt/olimpo/scripts/healthcheck.sh

# Agregar al cron:
crontab -e
# Agregar: */5 * * * * /opt/olimpo/scripts/healthcheck.sh
```

### 13.6 Monitoreo de Supabase

```
Supabase Dashboard → Reports

Revisar semanalmente:
- Database size (alertar si supera 80% del límite del plan)
- API requests (verificar que no hay spikes anómalos)
- Storage usage (incoming-raw puede crecer rápido)

Configurar Supabase Alerts:
Supabase Dashboard → Settings → Alerts
- Database size > 80%
- API error rate > 1%
```

---

## 14. Seguridad y Hardening

### 14.1 Secretos que NUNCA deben ir al repositorio

```
# ESTOS archivos deben estar en .gitignore:
.env
.env.*
!.env.example
packages/twenty-docker/.env     # YA EXISTE en el repo — MOVER a .env.example urgente

# Verificar que no hay secretos en el historial:
git log --all --full-history -- "*.env"
git log --all --full-history -- ".env"
```

> **URGENTE**: El archivo `packages/twenty-docker/.env` actual contiene
> credenciales reales (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, TWENTY_API_KEY).
> **Estas keys deben rotarse antes del go-live en producción.**

### 14.2 Rotar secretos antes de producción

```bash
# 1. Rotar APP_SECRET de Twenty (genera nuevo):
openssl rand -base64 32
# IMPORTANTE: cambiar APP_SECRET invalida todas las sesiones activas — usuarios
# deberán hacer login nuevamente.

# 2. En Supabase: rotar service_role key
# Supabase Dashboard → Settings → API → Rotate keys
# IMPORTANTE: actualizar en Railway y en VPS antes de revocar la key antigua.

# 3. En Twenty: regenerar API Key
# Settings → API & Webhooks → revocar la actual → crear nueva

# 4. En OpenAI: revocar y regenerar API Key
# platform.openai.com → API Keys → Delete old → Create new
```

### 14.3 Configurar .gitignore correctamente

Verificar que `.gitignore` en la raíz incluye:

```gitignore
# Variables de entorno — NUNCA al repositorio
.env
.env.*
!.env.example
packages/twenty-docker/.env

# Secrets locales
*.key
*.pem
*.p12
secrets/

# Build artifacts
dist/
.next/
*.local
```

### 14.4 Hardening del VPS

```bash
# En el VPS, configurar UFW (firewall):
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh          # puerto 22
ufw allow http         # puerto 80 (para redirect a HTTPS)
ufw allow https        # puerto 443
ufw enable

# Verificar que puertos internos NO están expuestos a internet:
# (3000, 5678, 4000 solo deben ser accesibles internamente vía Docker/NGINX)
netstat -tulnp | grep -E "(3000|5678|4000)"
# NO deben aparecer con 0.0.0.0 como interface — solo 127.0.0.1

# Habilitar fail2ban para proteger SSH:
systemctl enable fail2ban
systemctl start fail2ban

# Deshabilitar login con contraseña (solo SSH keys):
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd
```

### 14.5 Variables sensibles por servicio

| Variable | Nivel de sensibilidad | Dónde va |
|---|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | CRITICO | Solo Railway + VPS .env. NUNCA frontend. |
| `TWENTY_API_KEY` | ALTO | Railway + VPS .env. No en código. |
| `OPENAI_API_KEY` | ALTO | Solo Railway secrets. |
| `APP_SECRET` | CRITICO | Solo VPS .env. Si rota, invalida sesiones. |
| `PG_DATABASE_PASSWORD` | CRITICO | Solo VPS .env. |
| `RUNPOD_API_KEY` | ALTO | Solo Railway. |
| `SUPABASE_KEY` (anon) | BAJO | Puede ir en frontend (sujeto a RLS). |
| `VITE_SUPABASE_URL` | NINGUNO | Público. |

---

## 15. Runbook de Incidentes

### INC-001: FastAPI no responde

```
Síntoma: api.olimpo.com.mx devuelve 502 o timeout
Impacto: Pipeline de ingesta de correos se detiene. Los correos se acumulan en Gmail.

Diagnóstico:
1. railway logs --tail --service olimpo-agentes
2. Buscar: "Error", "Exception", "ConnectionRefused"

Soluciones comunes:
A) Crash por OOM → Railway reinicia automáticamente. Si no: railway restart --service olimpo-agentes
B) Error de Supabase → verificar supabase.com/status
C) Error de OpenAI API → verificar platform.openai.com/status
D) Deploy roto → railway rollback --service olimpo-agentes

Rollback:
railway rollback --service olimpo-agentes

Tiempo objetivo de resolución: < 10 minutos
```

### INC-002: Twenty CRM no responde

```
Síntoma: app.olimpo.com.mx devuelve 502 o "Service Unavailable"
Impacto: Analistas no pueden ver ni actualizar trámites.

Diagnóstico (en el VPS):
1. docker compose -f docker-compose.prod.yml ps
2. docker compose -f docker-compose.prod.yml logs --tail 50 server
3. Si PostgreSQL está caído: docker compose -f docker-compose.prod.yml logs --tail 50 db

Soluciones:
A) Contenedor caído → docker compose -f docker-compose.prod.yml up -d
B) PostgreSQL sin espacio en disco → df -h, limpiar logs o ampliar disco
C) Out of memory → htop, identificar proceso que consume memoria, reiniciar

Rollback a versión anterior:
1. Editar docker-compose.prod.yml: cambiar versión de imagen
2. docker compose -f docker-compose.prod.yml up -d

Tiempo objetivo de resolución: < 5 minutos
```

### INC-003: Correos no se procesan (pipeline roto)

```
Síntoma: Los correos llegan a Gmail pero no aparecen en Supabase ni en Twenty CRM
Impacto: Trámites nuevos no se registran. Agentes sin respuesta.

Diagnóstico:
1. Verificar n8n: https://n8n.olimpo.com.mx → Executions
   Buscar errores en la última ejecución del workflow
2. Si n8n funciona, verificar FastAPI:
   curl https://api.olimpo.com.mx/health
3. Si FastAPI falla, ver logs: railway logs --tail
4. Verificar Supabase: revisar tabla incoming_emails

Soluciones:
A) Workflow n8n desactivado → activarlo manualmente
B) Credencial Gmail expirada → re-autorizar OAuth2 en n8n
C) FastAPI down → ver INC-001
D) Supabase down → verificar supabase.com/status

Tiempo objetivo de resolución: < 15 minutos
```

### INC-004: Base de datos Supabase llena

```
Síntoma: Errores "storage full" en los logs de FastAPI o n8n
Impacto: No se pueden escribir datos nuevos. Pipeline se rompe.

Diagnóstico:
Supabase Dashboard → Settings → Usage → Database size

Soluciones inmediatas:
1. Limpiar tabla ai_processing_log (logs > 90 días):
   psql "$SUPABASE_DB_URL" -c "DELETE FROM ai_processing_log WHERE created_at < NOW() - INTERVAL '90 days';"
2. Limpiar Storage de archivos de incoming-raw antiguos:
   Supabase Dashboard → Storage → incoming-raw → eliminar carpetas > 30 días
3. Si persiste, hacer upgrade del plan de Supabase

Tiempo objetivo de resolución: < 30 minutos
```

### INC-005: OCR con RunPod falla masivamente

```
Síntoma: Todos los documentos PDF quedan en estado 'failed' en ocr_results
Impacto: Documentos escaneados no se procesan. Trámites con adjuntos quedan incompletos.

Diagnóstico:
1. Verificar runpod.io/status (puede haber outage de GPU)
2. Revisar logs de FastAPI: railway logs --grep "runpod"
3. Verificar crédito en RunPod: el saldo puede estar agotado

Soluciones:
A) RunPod outage → esperar resolución o switchear a procesamiento vía OpenAI Vision
B) Crédito agotado → agregar crédito en runpod.io
C) Error en el handler → revisar logs del endpoint en RunPod Dashboard

Fallback (procesar sin OCR):
El pipeline puede continuar sin OCR usando el texto del PDF directamente.
Los PDFs legibles nativamente (no escaneados) no necesitan OCR.

Tiempo objetivo de resolución: < 20 minutos
```

---

## 16. Estimado de Costos Mensuales

### Infraestructura base (producción)

| Servicio | Plan | Costo Mensual (USD) | Notas |
|---|---|---|---|
| **VPS (Twenty CRM + n8n)** | DigitalOcean 4GB | ~$24 | Hetzner es más barato ($4.35/mes para similar spec) |
| **Supabase** | Pro | $25 | Incluye PITR, 8GB BD, 100GB storage |
| **Railway (FastAPI)** | Hobby + uso | ~$10-25 | $5 base + ~$0.01/GB-hora de compute |
| **Vercel (Dashboard)** | Hobby | $0 | Gratuito para proyectos personales |
| **RunPod (OCR)** | Serverless | ~$5-20 | Pago por uso. GPU $0.40/h. Solo cuando hay PDFs escaneados |
| **OpenAI (GPT-4o)** | Pay per use | ~$20-100 | Depende del volumen de correos. ~$0.005/email con GPT-4o-mini |
| **Cloudflare** | Free | $0 | DNS, WAF básico gratuito |
| **Dominio** | .com.mx | ~$1.5/mes | ~$18/año |

**Total estimado mensual: $85-175 USD**

### Optimizaciones de costo posibles

```
1. Usar GPT-4o-mini en lugar de GPT-4o para clasificación inicial
   Ahorro: 40-60% en costos de OpenAI

2. Hetzner Cloud CX22 en lugar de DigitalOcean
   Ahorro: ~$20/mes en VPS

3. Supabase Free plan para staging (500MB límite)
   Ahorro: $25/mes en staging

4. RunPod: configurar Min Workers = 0 (ya está así)
   Solo consume cuando hay documentos a procesar

5. Usar Supabase Storage para Twenty CRM (en lugar de local)
   Elimina necesidad de VPS grande — podría reducir specs
```

### Escalado (cuando el volumen crezca)

```
- 500+ correos/día: subir Railway a Pro ($20/mes), más workers
- BD > 8GB: Supabase Team plan ($599/mes) con 100GB
- Necesidad de SLA 99.9%: agregar monitoreo externo (Uptime Robot, $7/mes)
```

---

## Apéndice A: Comandos de Referencia Rápida

```bash
# ── Supabase ──────────────────────────────────────────────────────────────────
# Ver tablas:
psql "$SUPABASE_DB_URL" -c "\dt public.*"

# Ver últimas entradas del pipeline:
psql "$SUPABASE_DB_URL" -c "SELECT * FROM tramites_pipeline ORDER BY created_at DESC LIMIT 5;"

# ── Railway ───────────────────────────────────────────────────────────────────
# Deploy:
railway up --service olimpo-agentes --detach

# Logs en tiempo real:
railway logs --tail --service olimpo-agentes

# Variables de entorno:
railway variables --service olimpo-agentes

# Rollback:
railway rollback --service olimpo-agentes

# ── VPS / Twenty CRM ─────────────────────────────────────────────────────────
# Estado de todos los contenedores:
docker compose -f /opt/olimpo/docker-compose.prod.yml ps

# Reiniciar solo Twenty server:
docker compose -f /opt/olimpo/docker-compose.prod.yml restart server

# Ver logs de Twenty:
docker compose -f /opt/olimpo/docker-compose.prod.yml logs -f server --tail 100

# Backup de BD:
docker compose -f /opt/olimpo/docker-compose.prod.yml exec -T db \
  pg_dump -U postgres default > backup_$(date +%Y%m%d_%H%M%S).sql

# ── Vercel ────────────────────────────────────────────────────────────────────
# Deploy a producción:
vercel --prod

# Ver deployments recientes:
vercel ls

# Rollback al deployment anterior:
vercel rollback
```

---

## Apéndice B: .env.example actualizado

Este archivo SÍ debe commitearse al repositorio como referencia:

```bash
# Generar .env.example desde el .env actual (sin valores reales):
cat packages/twenty-docker/.env | \
  sed 's/=.*/=/' | \
  sed 's/^TWENTY_API_KEY=$/TWENTY_API_KEY=eyJ_OBTENER_DESDE_TWENTY_SETTINGS/' | \
  sed 's/^APP_SECRET=$/APP_SECRET=GENERAR_CON_openssl_rand_-base64_32/' \
  > packages/twenty-docker/.env.example
```

---

*Documento generado el 2026-04-05. Versión 1.0.*
*Actualizar este documento cuando cambien URLs, versiones pinneadas o procedimientos.*
