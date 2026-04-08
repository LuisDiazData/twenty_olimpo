---
name: n8n Instance Config
description: URL, API key, credenciales, workflows activos y configuración de la instancia n8n local para el proyecto Olimpo
type: reference
---

## Instancia n8n

- **URL:** `http://localhost:5678`
- **Contenedor Docker:** `twenty-n8n-1`
- **Version:** 2.14.2
- **Timezone:** `America/Mexico_City` (configurado en docker-compose)

## Credenciales de acceso

- **Owner email:** `admin@olimpo.com.mx`
- **Password:** `Olimpo2026!`
- **API Key (olimpo-automation):** `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4YmNmNzY3OC1iNjBhLTQ0NjEtOWEyNC0wYmU1MzNiYTYyMmUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiODVhY2Y4MzktZDcwOS00MGJmLWEyOGUtNWU1ZTA5ZGRhN2JjIiwiaWF0IjoxNzc1MjgyNTk2fQ.8lAbnSmYzvRfh458_qUE_hZM8Fke3RWo_Tr4U0njyTs`
- **API Key ID:** `BRCE2iKBGGNxlKhL`

## Workflows importados en instancia

| ID               | Nombre                          | Estado   | Descripcion                                      |
|------------------|---------------------------------|----------|--------------------------------------------------|
| cijncOdXmag1dv7z | promotoria-gmail-ingestion-v4   | INACTIVO | Pipeline Gmail → email/ingest → agentes (v4)     |

## Credencial Gmail

- La credencial Gmail OAuth2 no existe aun en la instancia — el usuario la creara manualmente
- Nombre esperado por el workflow: `Gmail OAuth2`
- Los nodos Gmail en el workflow tienen `id: "PENDIENTE_CONFIGURAR"` como placeholder
- Despues de que el usuario cree la credencial en n8n UI, hay que actualizar el workflow con el ID real

## Licencia y limitaciones

- **Licencia:** Community (gratuita)
- `feat:variables` NO disponible — no se pueden usar `$env.XXX` en expresiones
- Solucion aplicada: valores hardcoded directamente en los nodos del workflow
- `feat:tags` puede estar limitado — no intentar crear tags via API hasta verificar

## Valores hardcoded en workflows

Configurados en `promotoria-gmail-ingestion-v4` (ID: `cijncOdXmag1dv7z`):
- `AGENTES_BASE_URL` = `http://host.docker.internal:4000`
- `SUPABASE_URL` = `https://aczkvxveenycpnwyqqbs.supabase.co`
- `SUPABASE_SERVICE_KEY` = JWT de service_role de Supabase (ver .env)
- `EQUIPO_EMAIL` = `operaciones@olimpo.com.mx`

## Notas importantes

- Setup del owner completado el 2026-04-04
- API publica usa `/api/v1/` (no `/rest/`)
- Para crear API keys usar `/rest/api-keys` con sesion cookie (no la API publica)
- Al hacer PUT de workflow, NO incluir estos campos (read-only): `id`, `active`, `versionId`, `updatedAt`, `createdAt`, `isArchived`, `versionCounter`, `triggerCount`, `activeVersionId`, `description`, `staticData`, `meta`, `pinData`, `tags`, `shared`
- `saveDataSuccessExecution` solo acepta valores `"all"` o `"none"` (no `"last"`)
- FastAPI corre en `http://localhost:4000` (o `host.docker.internal:4000` desde Docker)
