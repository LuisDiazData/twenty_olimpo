# PRE-PROD-FIXES.md
## Auditoría de Seguridad y Calidad — Promotoría GNP

**Fecha:** 2026-04-05
**Auditor:** Claude Code (claude-sonnet-4-6)

---

## Resumen Ejecutivo

| Prioridad | Cantidad |
|-----------|----------|
| CRÍTICO   | 6        |
| ALTO      | 8        |
| MEDIO     | 7        |
| BAJO      | 5        |
| **Total** | **26**   |

**Estado:** No apto para producción hasta corregir los 6 problemas críticos.

---

## PROBLEMAS CRÍTICOS

---

### [CRÍTICO-1] Supabase service_role key real expuesta en .env commiteado implícitamente

**Archivo:** `packages/twenty-docker/.env` (línea 56)
**Problema:** El archivo `.env` contiene la `SUPABASE_SERVICE_ROLE_KEY` real del proyecto `aczkvxveenycpnwyqqbs`. Aunque el `.gitignore` tiene `**/**/.env` y `.env`, el archivo actualmente en disco tiene credenciales reales. Si se commitea (el status muestra que está modificado), quedaría en el historial de git permanentemente.

La key expuesta es:
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFjemt2eHZlZW55Y3Bud3lxcWJzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDc0NDA4MywiZXhwIjoyMDkwMzIwMDgzfQ...
```
Esta es una key `service_role` que **bypasea completamente RLS** en Supabase — acceso total a todos los datos de producción.

**Riesgo:** Acceso completo de lectura/escritura/borrado a toda la base de datos de Supabase, incluyendo datos de agentes, trámites y documentos de seguros. La key expira en 2090, por lo que tiene vigencia de décadas si no se revoca.

**Fix:**
1. Revocar inmediatamente la key en el Dashboard de Supabase → Settings → API → Service Role Key → Roll Key.
2. Actualizar `.env` con la nueva key.
3. Verificar que `.env` NO está en staging: `git status --short | grep ".env"`.
4. Si fue commiteado accidentalmente, purgar el historial con `git filter-repo` o BFG Repo Cleaner.

---

### [CRÍTICO-2] TWENTY_API_KEY real expuesta en .env

**Archivo:** `packages/twenty-docker/.env` (línea 24)
**Problema:** La `TWENTY_API_KEY` contiene un JWT real de workspace:
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkODdjNGM4NS03MDVhLTQ2ZjgtOWM1OC0xNzQ2ZDEwZWNkMDYi...
```
Esta clave da acceso a la API de Twenty CRM para el workspace `d87c4c85-705a-46f8-9c58-1746d10ecd06`, con expiración en 2126.

**Riesgo:** Acceso completo a todos los objetos, trámites y datos del workspace de Twenty CRM. Un atacante puede crear, modificar o borrar trámites, agentes y documentos.

**Fix:**
1. Revocar la API Key en Twenty: Settings → API & Webhooks → API Keys → revocar la key actual.
2. Generar una nueva API key.
3. Actualizar el `.env` y nunca dejar keys reales en el repositorio.

---

### [CRÍTICO-3] Tokens Supabase reales hardcodeados en archivos JSON commiteados a git

**Archivos:**
- `scripts/n8n/workflow-gmail-tramite-v2.json` (líneas 350, 354) — anon key de Supabase
- `scripts/n8n/workflow-gmail-tramite.json` (línea 114) — URL real hardcodeada `aczkvxveenycpnwyqqbs.supabase.co`
- `scripts/n8n/workflow-gmail-tramite.json` (líneas 37, 84) — RunPod endpoint ID real `c2jx606dtqs7g8`

**Problema:** Estos archivos están **commiteados en git** (confirmado con `git ls-files`). Contienen:
- La `anon key` de Supabase completa como valor de header `apikey`
- La URL real del proyecto Supabase
- El ID del endpoint serverless de RunPod

**Riesgo:** Cualquier persona con acceso al repositorio tiene acceso a la base de datos de producción vía la anon key, y puede consumir créditos de RunPod usando el endpoint ID.

**Fix:**
1. Retirar los archivos del historial de git con BFG o `git filter-repo`:
   ```bash
   git filter-repo --path scripts/n8n/workflow-gmail-tramite-v2.json --invert-paths
   git filter-repo --path scripts/n8n/workflow-gmail-tramite.json --invert-paths
   ```
2. Agregar `scripts/n8n/workflow-gmail-tramite*.json` al `.gitignore`.
3. Rotar la anon key de Supabase.
4. Reemplazar URLs y tokens por variables de entorno `$env.SUPABASE_URL` y `$env.SUPABASE_KEY`.

---

### [CRÍTICO-4] APP_SECRET de Twenty CRM expuesto en .env

**Archivo:** `packages/twenty-docker/.env` (línea 16)
**Problema:** `APP_SECRET=E+N/rW4nW2W59JyWlHtTQi6COZP4HP7+92rOWnkSEkA=` está presente. Este secret se usa para firmar y verificar JWTs de sesiones de usuarios en Twenty CRM.

**Riesgo:** Con el APP_SECRET conocido, un atacante puede forjar tokens de autenticación válidos para cualquier usuario del workspace sin conocer sus credenciales.

**Fix:**
1. Generar un nuevo APP_SECRET: `openssl rand -base64 32`
2. Actualizar el `.env` con el nuevo valor.
3. Reiniciar los contenedores: `docker compose down && docker compose up -d`.
4. Todos los usuarios tendrán que volver a iniciar sesión (los JWT anteriores quedarán inválidos).

---

### [CRÍTICO-5] Credenciales Supabase hardcodeadas en pipeline_gmail_ingest_v4_hardcoded.json (no commiteado, pero riesgo latente)

**Archivo:** `scripts/n8n/pipeline_gmail_ingest_v4_hardcoded.json` (líneas 217, 221, 394, 398)
**Problema:** Este archivo (actualmente no commiteado — aparece como `??` en git status) contiene la `SUPABASE_SERVICE_ROLE_KEY` completa hardcodeada en headers de peticiones HTTP. El nombre `_hardcoded` indica que fue creado intencionalmente con credenciales reales para pruebas.

**Riesgo:** Si se commitea accidentalmente (lo cual es probable dado que los otros archivos similares sí fueron commiteados), expone el service_role key.

**Fix:**
1. Agregar `scripts/n8n/*hardcoded*.json` al `.gitignore` inmediatamente.
2. Eliminar el archivo o reemplazar todos los tokens con `$env.SUPABASE_SERVICE_KEY`.
3. Agregar la regla al `.gitignore`:
   ```
   scripts/n8n/*hardcoded*
   ```

---

### [CRÍTICO-6] Todos los endpoints FastAPI son públicos — sin autenticación

**Archivo:** `scripts/attachment_processor/main.py` (endpoints: `/process-email`, `/check-reply`, `/process-reply`, `/webhook/twenty`, `/api/v1/agentes/asignacion`, `/api/v1/agentes/documentos`, `/api/v1/email/ingest`)
**Problema:** Ningún endpoint tiene autenticación. El endpoint `/process-email` acepta archivos arbitrarios, el `/api/v1/agentes/asignacion` crea trámites en Twenty CRM, y el `/webhook/twenty` modifica estados de documentos. Cualquiera que conozca la URL del servicio puede:
- Subir archivos maliciosos a Supabase Storage
- Crear trámites falsos en el CRM
- Inyectar datos en tablas de Supabase

**Riesgo:** El servicio FastAPI en Railway está expuesto a internet. Sin autenticación, es completamente vulnerable a abuso.

**Fix:**
```python
# En main.py — agregar middleware de autenticación
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)
EXPECTED_API_KEY = os.getenv("INTERNAL_API_KEY", "")

def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    if not EXPECTED_API_KEY or api_key != EXPECTED_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return api_key

# En cada router o a nivel de app:
app = FastAPI(dependencies=[Depends(verify_api_key)])
```
Agregar `INTERNAL_API_KEY` al `.env` y configurar n8n para enviar el header `X-API-Key`.

---

## PROBLEMAS ALTOS

---

### [ALTO-1] n8n expuesto sin autenticación en docker-compose

**Archivo:** `packages/twenty-docker/docker-compose.yml` (línea 145)
**Problema:** `N8N_BASIC_AUTH_ACTIVE: ${N8N_BASIC_AUTH_ACTIVE:-false}` — el valor por defecto es `false`. El puerto 5678 de n8n está expuesto públicamente en el docker-compose. El parámetro `N8N_SECURE_COOKIE: "false"` también está hardcodeado.

**Riesgo:** n8n sin autenticación permite que cualquiera vea, modifique y ejecute los workflows de automatización, incluyendo el pipeline de Gmail. Pueden acceder a las credenciales OAuth2 de Gmail y disparar el pipeline manualmente.

**Fix:**
En `.env`:
```
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<password_fuerte_aleatorio>
```
En docker-compose.yml, cambiar:
```yaml
N8N_SECURE_COOKIE: "true"  # cuando se use HTTPS
```
Además, considerar no exponer el puerto 5678 públicamente en producción (remover la entrada `ports` de n8n y acceder solo a través de proxy reverso).

---

### [ALTO-2] Contraseña de PostgreSQL es "postgres" (valor por defecto débil)

**Archivo:** `packages/twenty-docker/.env` (línea 29)
**Problema:** `PG_DATABASE_PASSWORD=postgres` — contraseña trivial para el motor de base de datos.

**Riesgo:** Si el puerto 5432 de PostgreSQL es accesible (aunque no está en el docker-compose de producción, puede serlo por configuración errónea), la base de datos completa es comprometible con fuerza bruta en segundos.

**Fix:**
```bash
PG_DATABASE_PASSWORD=$(openssl rand -base64 24)
```
Actualizar `.env` con la nueva contraseña, luego:
```bash
docker compose down
docker volume rm twenty_db-data  # CUIDADO: borra datos, hacer backup primero
docker compose up -d
```

---

### [ALTO-3] Webhook de Twenty sin verificación de firma

**Archivo:** `scripts/attachment_processor/main.py` (línea 420)
**Problema:** El endpoint `/webhook/twenty` acepta cualquier payload sin verificar que proviene de Twenty CRM. Twenty envía un header `X-Twenty-Webhook-Signature` con HMAC-SHA256 del payload firmado con el APP_SECRET.

**Riesgo:** Un atacante puede enviar webhooks forjados para cambiar el estado de documentos en el sistema, marcando documentos inválidos como procesados.

**Fix:**
```python
import hmac
import hashlib

@app.post("/webhook/twenty")
async def twenty_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Twenty-Webhook-Signature", "")
    expected = hmac.new(
        APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Invalid webhook signature")
    payload = json.loads(body)
    # ... resto del handler
```

---

### [ALTO-4] Falta rate limiting en todos los endpoints públicos

**Archivo:** `scripts/attachment_processor/main.py` (todos los endpoints)
**Problema:** No existe rate limiting en ningún endpoint. El endpoint `/process-email` procesa archivos binarios completos (base64), el `/api/v1/agentes/asignacion` hace múltiples llamadas a LLM (OpenAI GPT-4o) por request.

**Riesgo:** Un atacante puede enviar miles de requests por minuto para:
- Agotar el crédito de OpenAI API (cada llamada a GPT-4o cuesta dinero)
- Saturar Supabase Storage con archivos maliciosos
- Hacer DoS al servicio

**Fix:**
```bash
pip install slowapi
```
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/process-email")
@limiter.limit("30/minute")  # n8n no debería enviar más de 30 emails/min
async def process_email(request: Request, ...):
```

---

### [ALTO-5] Imágenes Docker sin versión fija (latest/sin pinning)

**Archivo:** `packages/twenty-docker/docker-compose.yml` (líneas 5, 61, 111, 126, 136)
**Problema:**
- `image: twentycrm/twenty:${TAG:-latest}` — usa `latest` si TAG no se define
- `image: redis` — sin tag, toma `redis:latest`
- `image: n8nio/n8n:latest` — siempre latest

**Riesgo:** En producción, `latest` puede cambiar silenciosamente. Un pull automático puede desplegar una versión incompatible o con vulnerabilidades, rompiendo el sistema en producción sin cambio deliberado.

**Fix:**
```yaml
image: twentycrm/twenty:0.42.0   # fijar versión exacta
image: postgres:16.3              # fijar patch version
image: redis:7.2-alpine           # fijar versión
image: n8nio/n8n:1.87.0           # fijar versión
```
Verificar la última versión estable de cada imagen antes de fijar.

---

### [ALTO-6] Falta de validación de tamaño de archivos en /process-email

**Archivo:** `scripts/attachment_processor/main.py` (línea 181)
**Problema:** El endpoint `/process-email` acepta archivos en base64 sin límite de tamaño. Un email con adjuntos masivos (varios GB en base64) puede agotar la memoria del contenedor.

**Riesgo:** Un único request malicioso puede causar OOM en el contenedor FastAPI, dejando el servicio inoperante.

**Fix:**
```python
MAX_EMAIL_DATA_SIZE = 50 * 1024 * 1024  # 50 MB en bytes

@app.post("/process-email")
async def process_email(request: Request, email_data: str = Form(None), ...):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_EMAIL_DATA_SIZE:
        raise HTTPException(413, "Payload demasiado grande (máximo 50MB)")
```
También agregar en `uvicorn`:
```python
# En CMD del Dockerfile o al arrancar uvicorn
uvicorn main:app --limit-max-requests 1000 --limit-concurrency 50
```

---

### [ALTO-7] print() en supabase_client.py expone email_id y nombres de archivos en logs

**Archivo:** `scripts/attachment_processor/supabase_client.py` (líneas 15, 28, 42, 85, 112, 151, 194)
**Problema:** Se usan `print()` (no `logging`) para varios mensajes, entre ellos:
- Línea 85: `print(f"Logged attachments for email {email_id}. Count: ...")` — expone IDs de email de personas reales
- Línea 194: `print(f"log_attachment_individual: {nombre} → {doc_id}")` — expone nombres de documentos de seguros (INE, actas de nacimiento, etc.)

**Riesgo:** Los `print()` van al stdout del contenedor sin nivel de log ni formato estructurado. En algunos entornos de cloud (Railway, etc.), stdout es capturado y potencialmente indexado por servicios de logging de terceros, exponiendo metadata de documentos de asegurados.

**Fix:** Reemplazar todos los `print()` por `logger.info()` / `logger.warning()`:
```python
import logging
logger = logging.getLogger(__name__)

# Cambiar:
print(f"Logged attachments for email {email_id}. Count: {successful_processed}")
# Por:
logger.info(f"Logged attachments for email {email_id}. Count: {successful_processed}")
```

---

### [ALTO-8] Folio sequential con race condition en producción

**Archivo:** `scripts/attachment_processor/agente_asignacion.py` (línea 199 — función `_generar_folio`)
**Problema:** La generación de folios (`TRM-YYYY-NNNNN`) se hace consultando todos los folios existentes en Twenty, encontrando el máximo, y sumando 1. Este patrón tiene race condition: si dos requests concurrentes llegan al mismo tiempo, ambos pueden leer el mismo `max`, y generar el mismo folio.

**Riesgo:** Folios duplicados en el CRM, lo que rompe la trazabilidad de trámites y puede confundir a los analistas.

**Fix:** Usar una secuencia en Supabase:
```sql
-- En Supabase
CREATE SEQUENCE IF NOT EXISTS tramite_folio_seq START 1;
```
```python
async def _generar_folio(year: int | None = None) -> str:
    y = year or datetime.utcnow().year
    resp = _sb.rpc("nextval", {"seq_name": "tramite_folio_seq"}).execute()
    n = resp.data
    return f"TRM-{y}-{n:05d}"
```
O usar un campo `SERIAL` en una tabla auxiliar de contadores.

---

## PROBLEMAS MEDIOS

---

### [MEDIO-1] RLS no habilitada en tablas críticas: cobertura_analistas, historial_asignaciones, pipeline_logs, attachments_log (creación original)

**Archivos:**
- `scripts/supabase/migrations/008_agente4_tables.sql` — `cobertura_analistas` y `historial_asignaciones` sin RLS
- `scripts/supabase/migrations/009_pipeline_logs.sql` — `pipeline_logs` sin RLS
- `scripts/supabase/migrations/001_pipeline_tables.sql` — tablas originales del pipeline (`incoming_emails`, `email_attachments`, etc.) — RLS habilitada en 004 pero no en la tabla misma

**Problema:** Estas tablas contienen datos sensibles (coberturas de vacaciones de analistas, historial de todas las asignaciones, logs de emails) sin Row Level Security activa. Cualquier usuario autenticado con la anon key puede leer todos los datos.

**Riesgo:** Fuga de información sobre la organización interna (quién está de vacaciones, qué trámites se asignaron a quién).

**Fix:**
```sql
-- 008_agente4_rls.sql (nueva migración)
ALTER TABLE cobertura_analistas ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON cobertura_analistas
  FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE historial_asignaciones ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON historial_asignaciones
  FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE pipeline_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON pipeline_logs
  FOR ALL TO service_role USING (true) WITH CHECK (true);
```

---

### [MEDIO-2] Dashboard GraphQL query sin paginación cursor — carga hasta 500 trámites en memoria del browser

**Archivo:** `packages/twenty-front/src/modules/dashboard/hooks/useDashboardData.ts` (línea 20)
**Problema:** `tramites(first: 500)` carga los 500 trámites más recientes sin cursor de paginación. Con polleo cada 60 segundos, esto es potencialmente 500 × 60/min × N usuarios = miles de objetos transferidos continuamente.

**Riesgo:** A medida que el volumen de trámites crezca (objetivo de producción), esta query puede:
- Exceder el límite de respuesta de GraphQL (por defecto 50MB)
- Degradar el rendimiento del browser con miles de re-renders
- Incrementar latencia del servidor de Twenty

**Fix:** Agregar filtros de fecha obligatorios en el backend y reducir `first`:
```graphql
tramites(
  first: 100
  filter: {
    fechaIngreso: { gte: $periodoInicio }
    estadoTramite: { notIn: ["CANCELADO", "RESUELTO"] }
  }
  orderBy: { fechaIngreso: DescNullsLast }
)
```

---

### [MEDIO-3] Falta logging estructurado — inconsistencia entre print() y logging

**Archivos:** `scripts/attachment_processor/supabase_client.py`, `scripts/attachment_processor/extractor.py`
**Problema:** Hay mezcla de `print()` y `logging.getLogger()`. `supabase_client.py` usa `print()` exclusivamente mientras que `main.py`, `agente_asignacion.py`, `email_ingest.py` y `twenty_sync.py` usan el módulo `logging`. Esto significa que parte de los mensajes no tienen timestamp ni nivel en los logs de Railway.

**Riesgo:** En producción, imposible correlacionar eventos de `supabase_client.py` con el resto del pipeline. No hay niveles de log (DEBUG/INFO/WARNING/ERROR), lo que dificulta el troubleshooting.

**Fix:** Agregar al inicio de `supabase_client.py`:
```python
import logging
logger = logging.getLogger(__name__)
```
Y reemplazar todos los `print()` por llamadas al `logger`.

---

### [MEDIO-4] Variables de entorno sin validación al arrancar FastAPI

**Archivo:** `scripts/attachment_processor/main.py`
**Problema:** El servicio arranca aunque `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `TWENTY_API_URL` o `OPENAI_API_KEY` no estén configuradas. Solo falla en tiempo de ejecución cuando se llama un endpoint.

**Riesgo:** En producción, el servicio puede iniciar sin errores visibles pero fallar silenciosamente en el primer email procesado. Dificulta diagnóstico de configuraciones incorrectas en deployment.

**Fix:**
```python
# Al inicio de main.py, después de load_dotenv()
REQUIRED_ENV_VARS = [
    "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY",
    "TWENTY_API_URL", "TWENTY_API_KEY", "OPENAI_API_KEY",
]
missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
if missing:
    raise RuntimeError(f"Variables de entorno requeridas no configuradas: {missing}")
```

---

### [MEDIO-5] Ninguna migración SQL tiene lógica de rollback (DOWN)

**Archivos:** Todos los archivos en `scripts/supabase/migrations/` (000 al 018)
**Problema:** Ninguna de las 19 migraciones tiene una sección de rollback/DOWN. Si una migración se aplica incorrectamente en producción, no hay forma automatizada de revertirla.

**Riesgo:** En caso de despliegue fallido, la base de datos queda en estado inconsistente sin mecanismo de recuperación. La única opción es restaurar desde backup.

**Fix:** Para las migraciones críticas, agregar scripts de rollback:
```sql
-- Al final de cada migración, en sección comentada:
-- === ROLLBACK ===
-- DROP TABLE IF EXISTS cobertura_analistas CASCADE;
-- DROP TABLE IF EXISTS historial_asignaciones CASCADE;
-- ALTER TABLE tramites_pipeline
--   DROP COLUMN IF EXISTS agente_twenty_id,
--   DROP COLUMN IF EXISTS analista_twenty_id,
--   DROP COLUMN IF EXISTS motivo_revision,
--   DROP COLUMN IF EXISTS asignado_at;
```

---

### [MEDIO-6] PROJECT_REF de Supabase hardcodeado en script de administración

**Archivo:** `scripts/apply_supabase_migrations.py` (línea 24)
**Problema:** `PROJECT_REF = "aczkvxveenycpnwyqqbs"` y `DB_HOST = "aws-0-us-east-1.pooler.supabase.com"` están hardcodeados directamente en el código, no en variables de entorno.

**Riesgo:** Este archivo está en el repositorio. Aunque no contiene contraseñas (se pasan como argumento), expone el PROJECT_REF que permite identificar el proyecto Supabase en combinación con otras credenciales. También hace el script no reutilizable para otros ambientes.

**Fix:**
```python
PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF") or os.getenv("SUPABASE_URL", "").split(".")[0].replace("https://", "")
DB_HOST = os.environ.get("SUPABASE_DB_HOST", "aws-0-us-east-1.pooler.supabase.com")
```

---

### [MEDIO-7] Falta índice en tramites_pipeline.message_id (columna usada en búsqueda de replies)

**Archivo:** `scripts/supabase/migrations/000_tramites_pipeline.sql`
**Problema:** La función `_match_by_reply_headers` en `email_ingest.py` hace:
```python
_sb.table("tramites_pipeline").select(...).in_("message_id", candidate_ids)
```
La columna `message_id` no tiene índice en la tabla `tramites_pipeline`.

**Riesgo:** Con miles de filas en `tramites_pipeline`, cada lookup de reply headers hará un full table scan. En producción con alto volumen de emails, esto degradará el rendimiento del pipeline.

**Fix:**
```sql
-- Nueva migración: 019_missing_indexes.sql
CREATE INDEX IF NOT EXISTS idx_tramites_message_id
  ON tramites_pipeline(message_id)
  WHERE message_id IS NOT NULL;
```

---

## PROBLEMAS BAJOS

---

### [BAJO-1] Código comentado con URLs de desarrollo en semaforo.ts

**Archivo:** `packages/twenty-front/src/modules/dashboard/` (varios archivos de componentes)
**Problema:** Los archivos del dashboard tienen comentarios con TODO/referencias que deben limpiarse antes de producción.

**Fix:** Revisar y limpiar comentarios irrelevantes antes del release.

---

### [BAJO-2] requirements.txt sin pinning exacto de versiones

**Archivo:** `scripts/attachment_processor/requirements.txt`
**Problema:** Todas las dependencias usan `>=` (versión mínima) sin fijar la versión exacta:
```
fastapi>=0.100.0
litellm>=1.40.0
supabase>=2.0.0
```

**Riesgo:** `pip install` en producción puede instalar versiones incompatibles o con vulnerabilidades no vistas en desarrollo. `litellm` en particular tiene actualizaciones frecuentes que cambian la API.

**Fix:**
```bash
# En el entorno de desarrollo donde todo funciona:
pip freeze > requirements.txt
```
Esto genera versiones exactas como `fastapi==0.115.6`, `litellm==1.56.2`, etc.

---

### [BAJO-3] Falta de type hints completos en Python

**Archivos:** `scripts/attachment_processor/extractor.py`, `scripts/attachment_processor/agent_llm.py`
**Problema:** Las funciones en `extractor.py` usan type hints de `typing` (Python <3.9 style: `List`, `Dict`) en lugar de los built-ins modernos (`list`, `dict`). El proyecto usa Python 3.11 según el Dockerfile.

**Fix:**
```python
# Cambiar:
from typing import List, Tuple, Dict, Any
def extract_zip(file_bytes: bytes, passwords: List[str]) -> List[Tuple[str, bytes]]:

# Por (Python 3.9+):
def extract_zip(file_bytes: bytes, passwords: list[str]) -> list[tuple[str, bytes]]:
```

---

### [BAJO-4] Docker image del agente sin usuario no-root

**Archivo:** `scripts/attachment_processor/Dockerfile`
**Problema:** El Dockerfile no define un usuario no-root. El proceso uvicorn corre como `root` dentro del contenedor.

**Riesgo:** Si hay vulnerabilidad de path traversal o RCE en el procesamiento de archivos, el atacante tendría acceso root dentro del contenedor.

**Fix:**
```dockerfile
# Al final del Dockerfile, antes del CMD:
RUN adduser --disabled-password --gecos '' appuser
USER appuser
```

---

### [BAJO-5] n8n workflow v4 usa console.log con datos de emails en producción

**Archivo:** `scripts/n8n/pipeline_gmail_ingest_v4.json` (nodo "Evaluar Respuesta Ingest")
**Problema:** El código JS en el nodo de n8n contiene:
```javascript
console.log(`email/ingest: status=${statusCode}, strategy=${strategy}, tramite_id=${tramiteId}, requiere_accion=${requiereAccion}`);
```
Los logs de n8n son accesibles desde la UI y pueden incluir IDs de trámites y estrategias.

**Riesgo:** Bajo. En producción, estos logs son accesibles para cualquier usuario con acceso a n8n (que ya de por sí tiene acceso completo al workflow).

**Fix:** Reemplazar `console.log` por comentario o remover. En entorno de producción n8n, los logs del workflow son visibles en el panel de ejecuciones.

---

## CHECKLIST DE CORRECCIONES EN ORDEN DE EJECUCIÓN

Las correcciones deben aplicarse en este orden exacto (algunas dependen de otras):

### Fase 1: Secretos y Credenciales (Bloquean go-live — hacer ANTES de cualquier commit)
- [ ] **1.1** Revocar `SUPABASE_SERVICE_ROLE_KEY` en Supabase Dashboard y generar nueva
- [ ] **1.2** Revocar `TWENTY_API_KEY` en Twenty Settings y generar nueva
- [ ] **1.3** Generar nuevo `APP_SECRET` con `openssl rand -base64 32`
- [ ] **1.4** Actualizar `packages/twenty-docker/.env` con los nuevos valores (1.1, 1.2, 1.3)
- [ ] **1.5** Rotar la `anon key` de Supabase (expuesta en `workflow-gmail-tramite-v2.json`)
- [ ] **1.6** Verificar que `.env` no está en staging: `git diff --name-only --cached | grep .env`
- [ ] **1.7** Agregar a `.gitignore` las reglas faltantes:
  ```
  scripts/n8n/*hardcoded*
  scripts/n8n/workflow-gmail-tramite.json
  scripts/n8n/workflow-gmail-tramite-v2.json
  ```
- [ ] **1.8** Reemplazar URL y tokens hardcodeados en `scripts/n8n/workflow-gmail-tramite.json` y `workflow-gmail-tramite-v2.json` con variables de entorno, o eliminar estos archivos del repositorio

### Fase 2: Autenticación y Seguridad de Red (Antes de exponer servicios)
- [ ] **2.1** Agregar autenticación por API Key a FastAPI (`CRÍTICO-6`)
- [ ] **2.2** Configurar `N8N_BASIC_AUTH_ACTIVE=true` y contraseña fuerte en `.env` (`ALTO-1`)
- [ ] **2.3** Cambiar `PG_DATABASE_PASSWORD` a valor aleatorio seguro (`ALTO-2`)
- [ ] **2.4** Agregar validación de firma en webhook de Twenty (`ALTO-3`)
- [ ] **2.5** Configurar `INTERNAL_API_KEY` en `.env` y en variables de n8n

### Fase 3: Base de Datos y Migraciones
- [ ] **3.1** Crear migración `019_rls_missing_tables.sql` para habilitar RLS en `cobertura_analistas`, `historial_asignaciones`, `pipeline_logs` (`MEDIO-1`)
- [ ] **3.2** Crear migración `019_missing_indexes.sql` para índice en `tramites_pipeline.message_id` (`MEDIO-7`)
- [ ] **3.3** Aplicar ambas migraciones en Supabase

### Fase 4: Código de Aplicación
- [ ] **4.1** Agregar rate limiting con `slowapi` a FastAPI (`ALTO-4`)
- [ ] **4.2** Agregar validación de tamaño de payload en `/process-email` (`ALTO-6`)
- [ ] **4.3** Reemplazar todos los `print()` de `supabase_client.py` por `logging` (`ALTO-7`, `MEDIO-3`)
- [ ] **4.4** Agregar validación de variables de entorno al arranque de FastAPI (`MEDIO-4`)
- [ ] **4.5** Corregir race condition en generación de folios (`ALTO-8`)

### Fase 5: Infraestructura y Dependencias
- [ ] **5.1** Fijar versiones exactas en `docker-compose.yml` (`ALTO-5`)
- [ ] **5.2** Ejecutar `pip freeze > requirements.txt` en entorno de desarrollo (`BAJO-2`)
- [ ] **5.3** Agregar usuario no-root en Dockerfile (`BAJO-4`)

### Fase 6: Deuda Técnica (Puede hacerse post go-live)
- [ ] **6.1** Agregar rollback scripts a las migraciones más críticas (`MEDIO-5`)
- [ ] **6.2** Refactorizar query del dashboard a `first: 100` con filtros de fecha (`MEDIO-2`)
- [ ] **6.3** Parametrizar PROJECT_REF en `apply_supabase_migrations.py` (`MEDIO-6`)
- [ ] **6.4** Actualizar type hints en `extractor.py` (`BAJO-3`)
- [ ] **6.5** Remover `console.log` en nodos de n8n (`BAJO-5`)

---

## Estimado de Tiempo por Categoría

| Categoría | Tiempo estimado | Responsable |
|-----------|----------------|-------------|
| Fase 1: Rotar secretos | 1–2 horas | DevOps/Backend |
| Fase 2: Autenticación | 3–4 horas | Backend |
| Fase 3: Migraciones BD | 1 hora | Backend/DB |
| Fase 4: Código aplicación | 4–6 horas | Backend |
| Fase 5: Infraestructura | 1–2 horas | DevOps |
| Fase 6: Deuda técnica | 4–8 horas | Full team |
| **Total go-live** | **~12 horas** | |
| **Total completo** | **~20 horas** | |

---

## Notas Adicionales

### Sobre el .env en el repo
El archivo `packages/twenty-docker/.env` **no está commiteado** (el `.gitignore` lo excluye correctamente). El riesgo es que contiene credenciales reales y podría commitearse accidentalmente. La solución a largo plazo es usar un gestor de secretos (Doppler, Vault, o AWS Secrets Manager) y nunca almacenar secretos en archivos del repositorio, ni siquiera los excluidos por `.gitignore`.

### Sobre los archivos n8n commiteados
Los archivos `workflow-gmail-tramite.json` y `workflow-gmail-tramite-v2.json` **ya están en el historial de git** (aparecen en `git ls-files`). Aunque en el futuro se eliminen del árbol de trabajo, las credenciales seguirán en el historial. Es necesario purgar el historial completo con `git filter-repo` y hacer un force push (coordinando con todos los colaboradores para que re-clonen).

### Sobre el APP_SECRET en docker-compose
El fallback `APP_SECRET:-replace_me_with_a_random_string` en `docker-compose.yml` es un buen patrón, pero el `.env` tiene el valor real. Considerar eliminar el valor del `.env` y requerirlo como variable de entorno del sistema en producción.
