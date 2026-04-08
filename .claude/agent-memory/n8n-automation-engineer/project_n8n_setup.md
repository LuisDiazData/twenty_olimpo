---
name: Estado setup n8n Olimpo
description: Estado actual del setup de n8n para el proyecto Olimpo — owner creado, API key generada, 0 workflows activos
type: project
---

## Estado al 2026-04-04

n8n está corriendo en Docker (`twenty-n8n-1`) pero la instancia está vacía:
- Setup de owner completado en esta sesión (antes estaba pendiente)
- API key `olimpo-automation` creada (ID: `BRCE2iKBGGNxlKhL`)
- 0 workflows cargados en n8n
- 0 credenciales configuradas en n8n
- 0 variables de entorno configuradas en n8n

**Why:** La instancia nunca fue configurada por completo — existían los JSONs en disco pero nunca se importaron.

**How to apply:** Antes de activar cualquier workflow, hay que:
1. Configurar la credencial Gmail OAuth2 en n8n
2. Configurar las variables de entorno (AGENTES_BASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY, TEAM_NOTIFICATION_EMAIL)
3. Importar `pipeline_tramites_v3_fixed.json` vía API
4. Activar el workflow
