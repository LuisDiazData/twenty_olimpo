---
name: Secretos expuestos en repositorio — pendiente de rotar
description: URGENTE: packages/twenty-docker/.env tiene credenciales reales commiteadas
type: project
---

# Secretos reales observados en packages/twenty-docker/.env

**Estado**: Este archivo está commiteado en el repositorio con credenciales de producción reales.

**Credenciales expuestas que deben rotarse ANTES del go-live:**

1. `TWENTY_API_KEY` — JWT real de la API Key de Twenty (formato eyJhbGciOi...)
2. `SUPABASE_KEY` — publishable key real (`sb_publishable_G3rw372qkoXAmoEJBsSuAQ_xsjDUjFE`)
3. `SUPABASE_SERVICE_ROLE_KEY` — service_role JWT real (CRÍTICO — bypasea RLS)
4. `APP_SECRET` — secret de JWT de Twenty (`E+N/rW4nW2W59JyWlHtTQi6COZP4HP7+92rOWnkSEkA=`)

**Credenciales aún pendientes (placeholders):**
- `OPENAI_API_KEY=<REEMPLAZAR_OPENAI_API_KEY>`
- `RUNPOD_API_KEY=<REEMPLAZAR_RUNPOD_API_KEY>`
- `RUNPOD_ENDPOINT_ID=<REEMPLAZAR_RUNPOD_ENDPOINT_ID>`
- `N8N_BASIC_AUTH_PASSWORD=<REEMPLAZAR_N8N_PASSWORD>`

**Acción requerida:**
1. Mover `packages/twenty-docker/.env` a `.gitignore`
2. Crear `packages/twenty-docker/.env.example` con valores placeholder
3. Rotar en Supabase: service_role key y anon key
4. Regenerar TWENTY_API_KEY en el dashboard de Twenty
5. Generar nuevo APP_SECRET (invalida sesiones activas)

**Why:** Credenciales en repositorio son un riesgo de seguridad crítico, especialmente la service_role key que bypasea RLS.
**How to apply:** Siempre recordar este punto al usuario cuando hable de seguridad o pre-deploy checklist.
