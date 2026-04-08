---
name: Views creadas para Hypnos CRM
description: IDs y configuración de todas las vistas por rol creadas en Twenty CRM para la promotoría Hypnos
type: project
---

# Vistas creadas en Twenty CRM — Hypnos

Todas las vistas fueron creadas el 2026-04-03 via metadata API (`http://localhost:3000/metadata`).

**Why:** Los analistas, gerentes y directores necesitan vistas pre-configuradas por rol para operar el CRM desde el primer día sin configuración manual.

**How to apply:** Al crear nuevas vistas, seguir el mismo patrón: `createView` → `createViewSort` → `createViewFilter` (con `createViewFilterGroup` para OR) → `createManyViewFields`.

---

## Vistas sobre el objeto `tramite` (objectMetadataId: f64ac7de-951d-4d46-9f51-6456310bc1e9)

| Nombre | ID | Rol objetivo | Filtros | Sort |
|--------|----|-------------|---------|------|
| All Trámites (default INDEX) | d0942ca0-a211-4c61-babf-e83e882c6603 | Sistema | ninguno | — |
| Todos los Trámites | 555de207-37f4-4d50-b0b1-78f87a0c1ba8 | Directores | ninguno | fechaIngreso DESC |
| Trámites Detenidos | e5164cb3-cd4b-41eb-bc0f-1ff97b347ff4 | Directores, Gerentes | estatus = DETENIDO | fechaIngreso ASC |
| Pendientes GNP | 5a62c423-85b0-4205-8349-0c4b63969c16 | Directores, Gerentes | estatus = TURNADO_GNP OR EN_PROCESO_GNP | fechaTurnoGnp ASC |
| Mi Bandeja (Analista) | acaf4753-804c-461b-97ec-6faa52f2b497 | Analistas | ninguno | prioridad DESC |
| En Revisión Documental | 4a5cab51-9079-4b32-8186-46f189372503 | Analistas | estatus = RECIBIDO OR EN_REVISION_DOC | fechaIngreso ASC |
| Urgentes | 85dcb0b5-d5bb-4bae-b800-1ce38d721c32 | Directores, Gerentes | prioridad = Urgente | fechaIngreso ASC |

### OR Filter Groups
- Pendientes GNP → grupo OR id: `a2ec72f8-3502-4278-a64b-bb3afeef06bb`
- En Revisión Documental → grupo OR id: `1abd3854-8c88-4755-bddb-5c1bcbfb2350`

---

## Vistas sobre el objeto `agente` (objectMetadataId: eea61f1e-ef36-458c-9982-36d31f478b8f)

| Nombre | ID | Filtros | Sort |
|--------|----|---------|------|
| All Agentes (default INDEX) | 08684cce-bf1b-4052-bec6-8e84ca17dda8 | ninguno | — |
| Agentes Activos | 12dc2052-87be-49ac-96b0-5ca342d6309f | activo = true | name ASC |

---

## Notas técnicas

- `destroyView(id: "...")` toma `id` como String directo (no como `input` wrapper) y devuelve Boolean.
- `destroyViewFilter(input: {id: "..."})` toma `input` wrapper.
- `destroyViewFilterGroup(id: "...")` toma `id` directo como String.
- El campo `name` (label identifier) en objetos como `agente` ya está en posición 0 por defecto; intentar re-añadirlo en `createViewField` causa error `INVALID_VIEW_DATA` — es seguro ignorarlo.
- Filters sin `viewFilterGroupId` son standalone (AND implícito). Para OR se requiere `createViewFilterGroup` con `logicalOperator: OR` y luego ligar los filtros con `viewFilterGroupId`.
- `ViewFilterOperand.IS` funciona para SELECT y BOOLEAN.
- `ViewSortDirection`: `ASC` o `DESC` (no `AscNullsLast` — eso es para la workspace API, no metadata).
