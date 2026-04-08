---
name: n8n API Quirks Community Edition
description: Campos read-only en la API, limitaciones de licencia Community y valores validos para settings
type: feedback
---

Al crear/actualizar workflows via API en n8n Community, hay varias restricciones no documentadas:

**Campos read-only en POST/PUT de workflows:**
- `active`, `tags`, `shared`, `versionId`, `updatedAt`, `createdAt`, `isArchived`, `versionCounter`, `triggerCount`, `activeVersionId`, `description`, `staticData`, `meta`, `pinData`
- Incluir cualquiera de estos en el body devuelve `400 "is read-only"`

**Why:** La API de n8n 2.x gestiona estos campos internamente y no permite sobreescribirlos en el cuerpo de la peticion.

**How to apply:** Antes de cada POST o PUT de workflow, filtrar estos campos del JSON. Usar el JSON de disco (fuente), no el GET de la instancia (que incluye los campos read-only).

---

**`saveDataSuccessExecution` solo acepta `"all"` o `"none"`**, no `"last"`.

**Why:** Cambio de schema en n8n 2.x — la opcion `"last"` fue eliminada.

**How to apply:** Siempre usar `"all"` en produccion para tener historial completo.

---

**`feat:variables` no disponible en Community.** No se pueden usar `$env.XXX` en expresiones de nodos.

**Why:** Es una feature de pago (Enterprise/Team).

**How to apply:** Hardcodear valores directamente en los parametros de nodos. Usar el JSON de disco como template y hacer string replacement antes de importar.

---

**Workflow PUT requiere el mismo `name` que el GET** — si el nombre cambia n8n puede crear duplicados. Siempre verificar con GET antes de PUT.
