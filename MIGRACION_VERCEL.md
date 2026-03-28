# Plan de Migración a Vercel — Promotoría GNP CRM

> Análisis realizado el 2026-03-25

---

## Diagnóstico rápido

**¿Se puede migrar a Vercel hoy?**

| Componente | ¿Va a Vercel? | ¿Está listo? |
|---|---|---|
| `twenty-front` (frontend React) | ✅ SÍ | ✅ Listo |
| Dashboard GNP (módulo custom) | ✅ SÍ (va dentro del frontend) | ✅ Listo |
| `twenty-server` (NestJS API) | ❌ NO — Vercel no soporta procesos persistentes | Necesita servidor propio |
| PostgreSQL | ❌ NO | Necesita base de datos gestionada |
| Redis | ❌ NO | Necesita Redis gestionado |
| Worker BullMQ | ❌ NO | Proceso continuo |

**Conclusión:** El frontend (incluyendo el dashboard de la promotoría) va a Vercel. El backend va a Railway o Fly.io.

---

## Por qué el backend NO puede ir a Vercel

1. **Vercel Functions tienen timeout de 15 min** — los jobs de BullMQ, las migraciones de TypeORM y las subscripciones WebSocket de GraphQL necesitan procesos de larga duración.
2. **Sin estado persistente** — Twenty necesita un pool de conexiones a PostgreSQL y conexión continua a Redis para sesiones, cache y colas.
3. **WebSockets** — Las subscripciones GraphQL (actualizaciones en tiempo real del CRM) no funcionan en Vercel Functions.
4. **Worker de cola** — El `queue-worker` (BullMQ) debe correr de forma continua; Vercel solo ejecuta código en respuesta a requests.

---

## Arquitectura objetivo

```
┌─────────────────────────────────────────────────────────────┐
│  VERCEL (CDN global, gratis)                                │
│                                                             │
│  twenty-front → build estático (React + Vite)              │
│  Incluye: Dashboard GNP (Directora / Gerente / Especialista)│
│  URL: https://tu-promotoria.vercel.app                      │
└───────────────────────┬─────────────────────────────────────┘
                        │ API calls (REACT_APP_SERVER_BASE_URL)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  RAILWAY o FLY.IO (backend, ~$5-15/mes)                     │
│                                                             │
│  ├─ twenty-server (NestJS + GraphQL)  puerto 3000           │
│  ├─ queue-worker (BullMQ)                                   │
│  ├─ PostgreSQL 16  (base de datos)                          │
│  └─ Redis 7  (sesiones + cache)                             │
└─────────────────────────────────────────────────────────────┘
                        │ archivos adjuntos
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  AWS S3 / Cloudflare R2  (storage, muy barato)              │
└─────────────────────────────────────────────────────────────┘
```

---

## Estado actual del proyecto

### Lo que ya existe y está listo

- ✅ Modelo de datos completo (Trámite, Agente, Asignación, Documento, RazónRechazo)
- ✅ Datos de prueba (`seed_data.py`)
- ✅ Módulo Dashboard GNP integrado en `twenty-front` (`src/modules/dashboard/`)
- ✅ TypeScript compila sin errores (`npx nx typecheck twenty-front`)
- ✅ Docker Compose funcional para entorno local
- ✅ Frontend construye con Vite → carpeta `build/`

### Lo que falta antes de migrar

1. **Variables de entorno de producción** — definir los valores reales de BD, Redis, auth
2. **`vercel.json`** — configuración del proyecto en Vercel (creada en este plan)
3. **Backend desplegado** — la URL del servidor (`REACT_APP_SERVER_BASE_URL`) debe existir
4. **SSL/TLS** — el backend debe servir en HTTPS (Railway y Fly.io lo dan automático)
5. **Dominio personalizado** (opcional) — si quieres usar `crm.tupromotoria.com.mx`

---

## Plan de ejecución paso a paso

### PASO 1 — Desplegar el backend en Railway (30-60 min)

Railway es el camino más sencillo para este stack.

**1.1 — Crear cuenta en Railway**
```
https://railway.app
```
Conectar con tu cuenta de GitHub.

**1.2 — Crear nuevo proyecto desde GitHub**
- New Project → Deploy from GitHub repo → selecciona `twenty_olimpo`
- Railway detectará el Dockerfile automáticamente

**1.3 — Configurar el servicio `server`**

En Railway → Settings → Build:
```
Dockerfile Path:  packages/twenty-docker/twenty/Dockerfile
```

Variables de entorno a agregar en Railway:
```env
# Base de datos (Railway provisiona PostgreSQL automáticamente)
PG_DATABASE_URL=${{Postgres.DATABASE_URL}}

# Redis (Railway provisiona Redis automáticamente)
REDIS_URL=${{Redis.REDIS_URL}}

# Seguridad — genera un string aleatorio de 64 chars
APP_SECRET=GENERA_UN_STRING_ALEATORIO_AQUI

# URL pública del servidor (Railway la da al deployar)
SERVER_URL=https://tu-proyecto.up.railway.app

# Almacenamiento (para archivos adjuntos de trámites)
STORAGE_TYPE=local
# O si usas S3:
# STORAGE_TYPE=s3
# STORAGE_S3_REGION=us-east-1
# STORAGE_S3_NAME=tu-bucket
# STORAGE_S3_ENDPOINT=https://s3.amazonaws.com

# Auth básico (requerido)
AUTH_PASSWORD_ENABLED=true

# Desactiva pagos/features enterprise que no usarás
IS_BILLING_ENABLED=false
IS_EMAIL_VERIFICATION_REQUIRED=false
```

**1.4 — Agregar PostgreSQL y Redis en Railway**
- Dashboard → + New → Database → PostgreSQL
- Dashboard → + New → Database → Redis
- Railway conecta automáticamente las variables

**1.5 — Primer deploy**
- Railway desplegará, ejecutará migraciones y levantará el servidor
- Nota la URL: `https://tu-proyecto.up.railway.app`

**Verificar que funciona:**
```bash
curl https://tu-proyecto.up.railway.app/healthz
# Debe responder: {"status":"ok"}
```

---

### PASO 2 — Crear `vercel.json` en la raíz del proyecto

Crea el archivo `/vercel.json`:

```json
{
  "buildCommand": "npx nx build twenty-front",
  "outputDirectory": "packages/twenty-front/build",
  "framework": null,
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ],
  "headers": [
    {
      "source": "/assets/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }
      ]
    }
  ]
}
```

> La regla `rewrites` es crítica: como es una SPA (Single Page App), todas las rutas deben apuntar a `index.html` para que React Router funcione.

---

### PASO 3 — Crear `.vercelignore`

Crea el archivo `/.vercelignore` para que Vercel no suba código del backend:

```
packages/twenty-server
packages/twenty-docker
packages/twenty-e2e-testing
packages/twenty-companion
packages/twenty-cli
packages/twenty-website
packages/twenty-docs
packages/twenty-zapier
packages/twenty-emails
.git
*.log
```

---

### PASO 4 — Configurar variables de entorno en Vercel

En Vercel Dashboard → Settings → Environment Variables:

| Variable | Valor |
|---|---|
| `REACT_APP_SERVER_BASE_URL` | `https://tu-proyecto.up.railway.app` |
| `NODE_VERSION` | `24` |

> `REACT_APP_SERVER_BASE_URL` debe apuntar al backend de Railway que configuraste en el Paso 1.

---

### PASO 5 — Conectar repositorio a Vercel y hacer el primer deploy

```bash
# Opción A: desde CLI de Vercel
npm i -g vercel
cd C:/Users/wichi/twenty_olimpo
vercel --prod

# Opción B: desde el dashboard
# https://vercel.com/new → Import Git Repository → twenty_olimpo
```

Al importar en Vercel Dashboard:
- **Framework Preset:** Other
- **Build Command:** `npx nx build twenty-front`
- **Output Directory:** `packages/twenty-front/build`
- **Install Command:** `yarn install`

---

### PASO 6 — Verificar que el dashboard GNP funciona

Una vez deployado:

1. Abre `https://tu-promotoria.vercel.app`
2. Inicia sesión con el usuario del workspace
3. En el sidebar izquierdo → sección "Other" → **Dashboard GNP**
4. Verifica que las 3 vistas cargan: Directora / Gerente / Especialista
5. Los datos deben venir de `https://tu-proyecto.up.railway.app/graphql`

---

### PASO 7 — (Opcional) Migrar datos actuales de Docker local

Si ya tienes datos en el Docker local que quieres llevar a producción:

```bash
# Exportar desde PostgreSQL local
docker exec twenty-db pg_dump -U postgres default > backup_local.sql

# Importar en Railway PostgreSQL
# Railway Dashboard → PostgreSQL → Connect → copia la connection string
psql "postgresql://user:pass@host:5432/railway" < backup_local.sql
```

---

### PASO 8 — (Opcional) Dominio personalizado

En Vercel Dashboard → Settings → Domains:
```
crm.tupromotoria.com.mx  →  add
```
Configura el CNAME en tu proveedor DNS:
```
crm  CNAME  cname.vercel-dns.com
```

---

## Costos estimados mensuales

| Servicio | Plan | Costo |
|---|---|---|
| **Vercel** (frontend) | Hobby (gratis hasta 100GB bandwidth) | **$0** |
| **Railway** (backend + BD + Redis) | Starter | **$5-15/mes** |
| **AWS S3** (archivos adjuntos de trámites) | Pay-per-use | **< $1/mes** inicialmente |
| **Total** | | **~$5-15/mes** |

---

## Checklist de migración

```
[ ] PASO 1 — Backend en Railway funcionando
    [ ] Server responde en /healthz
    [ ] Migraciones ejecutadas correctamente
    [ ] Workspace creado y accesible

[ ] PASO 2 — vercel.json creado en la raíz

[ ] PASO 3 — .vercelignore creado

[ ] PASO 4 — Variable REACT_APP_SERVER_BASE_URL configurada en Vercel

[ ] PASO 5 — Primer deploy exitoso en Vercel
    [ ] La URL de Vercel carga el CRM

[ ] PASO 6 — Dashboard GNP funcionando en producción
    [ ] Vista Directora muestra datos
    [ ] Vista Gerente filtra por ramo
    [ ] Vista Especialista filtra por usuario

[ ] PASO 7 — (Opcional) Datos migrados desde local

[ ] PASO 8 — (Opcional) Dominio personalizado configurado
```

---

## Comandos de build que usa Vercel

```bash
# Lo que Vercel ejecutará automáticamente:
yarn install
npx nx build twenty-front

# Esto produce:
packages/twenty-front/build/
├── index.html
├── assets/
│   ├── index-[hash].js   (~6.8 MB, minificado)
│   ├── [chunks]-[hash].js
│   └── [chunks]-[hash].css
└── public/
```

---

## Posibles problemas y soluciones

### Error: "Cannot find module twenty-shared"
```bash
# Vercel necesita construir las dependencias primero
# Cambiar buildCommand a:
npx nx build twenty-shared && npx nx build twenty-front
```

### Error: "CORS policy" en producción
Agregar la URL de Vercel a las variables del backend en Railway:
```env
FRONT_DOMAIN_URL=https://tu-promotoria.vercel.app
```

### Error: Rutas 404 en SPA (al refrescar /dashboard)
Verificar que el `vercel.json` tiene la regla `rewrites` del Paso 2.

### Error: "Your app uses Node X, but Vercel requires Y"
Configurar en Vercel Dashboard → Settings → Node.js Version → 20.x (LTS)

---

## Alternativas al backend en Railway

Si prefieres otras opciones:

| Plataforma | Pros | Contras |
|---|---|---|
| **Railway** | Más fácil, todo integrado (PostgreSQL + Redis en un clic) | $5/mes mínimo |
| **Fly.io** | Muy económico, buen control | Curva de aprendizaje de flyctl |
| **Render.com** | Tier gratuito limitado | Frío en tier gratuito (spin-down) |
| **Self-hosted VPS** (Hetzner, DigitalOcean) | Máximo control, barato a escala | Requiere sysadmin |
| **Docker local siempre encendido** | Cero costo, ya funciona | No accesible desde fuera |

**Recomendación para una promotoría pequeña:** Railway, al menos al inicio.
