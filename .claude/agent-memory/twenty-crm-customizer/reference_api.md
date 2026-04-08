---
name: Twenty CRM API reference para Hypnos
description: Endpoints, auth, y patrones de uso de la API de Twenty para la instancia Hypnos
type: reference
---

# Twenty CRM API Reference — Instancia Hypnos

## Endpoints

| Endpoint | Uso |
|----------|-----|
| `http://localhost:3000/metadata` | Metadata API: crear/editar objetos, campos, vistas, filtros, sorts |
| `http://localhost:3000/graphql` | Workspace API: CRUD de registros (tramites, agentes, etc.) |

## Autenticación

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkODdjNGM4NS03MDVhLTQ2ZjgtOWM1OC0xNzQ2ZDEwZWNkMDYiLCJ0eXBlIjoiQVBJX0tFWSIsIndvcmtzcGFjZUlkIjoiZDg3YzRjODUtNzA1YS00NmY4LTljNTgtMTc0NmQxMGVjZDA2IiwiaWF0IjoxNzc1MTk0MjU0LCJleHAiOjQ5Mjg3OTQyNTMsImp0aSI6ImYxYzE1NDgxLTM5ZWYtNGQ5MS04M2VmLTIwZjM0NDY4ZGUxMSJ9.m3OgIt9HGVXGtaNH74wejqwaPo0r2NOJ3k1UsyzDtec
```

## Patrones importantes

### Crear vista
```graphql
mutation CreateView($input: CreateViewInput!) {
  createView(input: $input) { id name }
}
# variables: { input: { name, objectMetadataId, type: TABLE, icon, position } }
```

### Agregar sort a vista
```graphql
mutation { createViewSort(input: { viewId, fieldMetadataId, direction: ASC|DESC }) { id } }
```

### Agregar filter simple a vista
```graphql
mutation { createViewFilter(input: { viewId, fieldMetadataId, operand: IS, value: "VALOR" }) { id } }
```

### Agregar OR filter group
```graphql
# 1. Crear grupo
mutation { createViewFilterGroup(input: { viewId, logicalOperator: OR, positionInViewFilterGroup: 0 }) { id } }
# 2. Agregar filtros con viewFilterGroupId
mutation { createViewFilter(input: { viewId, fieldMetadataId, operand: IS, value: "V1", viewFilterGroupId: "grupoId", positionInViewFilterGroup: 0 }) { id } }
```

### Eliminar vista
```graphql
mutation { destroyView(id: "viewId") }  # devuelve Boolean, id es String directo
```

### Eliminar filtro
```graphql
mutation { destroyViewFilter(input: { id: "filterId" }) { id } }  # usa wrapper input
```

### Consultar vistas existentes
```graphql
{ getViews(objectMetadataId: "objId") { id name type key position } }
```

### Consultar filtros de una vista
```graphql
{ getViewFilters(viewId: "viewId") { id operand value viewFilterGroupId } }
```

### Crear relación entre objetos
Las relaciones se crean como campos `RELATION` via `createOneField`, NO existe `createOneRelation` en esta versión.

```graphql
mutation {
  createOneField(input: {
    field: {
      objectMetadataId: "ID_OBJETO_MANY_SIDE"
      name: "nombreCampo"
      label: "Label Campo"
      icon: "IconUser"
      type: RELATION
      isNullable: true
      relationCreationPayload: {
        type: "MANY_TO_ONE"           # CLAVE: usar "type", no "relationType"
        targetObjectMetadataId: "ID_OBJETO_ONE_SIDE"
        targetFieldName: "coleccion"  # nombre del campo inverso en el one-side
        targetFieldLabel: "Label coleccion"
        targetFieldIcon: "IconXxx"    # REQUERIDO — falla sin este campo
      }
    }
  }) {
    id name type
  }
}
```

**CRÍTICO**: En `relationCreationPayload`, el campo de tipo se llama `type` (no `relationType`). Omitir `targetFieldIcon` también falla con error de validación.

## Gotchas conocidos

1. `ViewSortDirection` acepta `ASC` y `DESC` (no `AscNullsLast` — eso es para workspace API).
2. El campo `name` (label identifier) en cualquier objeto custom ya tiene un `viewField` en posición 0 por defecto. Intentar re-añadirlo falla con `INVALID_VIEW_DATA`. Omitirlo en `createViewField`.
3. `destroyView` toma `id: String!` directo. `destroyViewFilter` toma `input: { id }`. No son consistentes.
4. `value` en `CreateViewFilterInput` es tipo `JSON` — puede ser string, boolean, número directamente.
5. La workspace API (`/graphql`) no tiene queries `views` — todo lo de vistas va por `/metadata`.
6. Endpoint `/api` no existe; la workspace API está en `/graphql`.
7. No existe `CreateOneRelationInput` ni mutación `createOneRelation` en esta versión de Twenty. Las relaciones se crean como campos de tipo `RELATION` con `relationCreationPayload`.
8. En `relationCreationPayload`, usar `type` (no `relationType`) y siempre incluir `targetFieldIcon` (string requerido).
9. El `defaultValue` de CURRENCY debe omitirse (null) — enviar `{"amountMicros": 0, "currencyCode": "MXN"}` falla con "Migration action 'create' failed".
10. Opciones de SELECT: usar `value` en SCREAMING_SNAKE_CASE sin caracteres especiales. El campo `id` en opciones NO se incluye al crear (Twenty lo genera automáticamente).
11. Opciones de SELECT requieren campo `position` (entero, empezando en 0) en cada opción. Sin `position`, la API responde con "Duplicated option position" y falla la creación.
12. `nameSingular` y `namePlural` de un objeto NO pueden ser iguales (ej: `historialEstatus`/`historialEstatus`). Usar un plural distinto (ej: `historialEstatusLogs`).
