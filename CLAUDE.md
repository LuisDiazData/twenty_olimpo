# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Contexto del Negocio

Este repositorio adapta **Twenty CRM** (open-source) para una **promotoría de seguros** que actúa como intermediario entre agentes independientes y la aseguradora **GNP (Grupo Nacional Provincial)**.

### Problema que se resuelve

Los trámites (pólizas, endosos, siniestros, emisiones) llegan por WhatsApp y correo electrónico de los agentes. El proceso actual es manual y sin trazabilidad:

1. Un agente envía documentos por WhatsApp o correo
2. Un analista revisa si la documentación está completa por ramo
3. Los documentos se turnan a la plataforma interna de GNP
4. GNP procesa el trámite (puede tardar días o quedar detenido)
5. Si el trámite se detiene, hay que avisar al agente oportunamente

**Sin CRM**: los trámites se pierden, los avisos llegan tarde, no hay visibilidad de qué está pendiente.

### Estructura Organizacional

```
Director General
└── Director de Operaciones
    ├── Gerente de Vida
    │   └── Analistas de Vida (N analistas)
    ├── Gerente de GMM (Gastos Médicos Mayores)
    │   └── Analistas de GMM
    ├── Gerente de PyMES
    │   └── Analistas de PyMES
    └── Gerente de Autos
        └── Analistas de Autos
```

Los agentes son externos a la promotoría — son los "clientes" del CRM (equivalen a `Person` o `Company` en Twenty).

### Ramos de Seguros

| Ramo | Descripción | Tipos de trámite comunes |
|------|-------------|--------------------------|
| **Vida** | Seguros de vida individual y colectivo | Emisión, endoso de beneficiario, siniestro por fallecimiento |
| **GMM** | Gastos Médicos Mayores (individual y grupo) | Alta de asegurado, siniestro médico, renovación, endoso |
| **PyMES** | Seguros para pequeñas y medianas empresas | Paquete PyME, responsabilidad civil, vida grupal |
| **Autos** | Seguros de automóvil | Emisión, siniestro, endoso de datos, renovación |

---

## Modelo de Dominio

### Objetos Personalizados (Custom Objects en Twenty)

#### `Agente` (reemplaza/extiende `Person`)
Representa al agente externo que envía trámites.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `claveAgente` | TEXT | Clave única GNP del agente |
| `nombre` | FULL_NAME | Nombre completo |
| `celular` | PHONES | WhatsApp principal |
| `email` | EMAILS | Correo de contacto |
| `ramos` | MULTI_SELECT | Ramos autorizados (Vida, GMM, PyMES, Autos) |
| `promotoriaAsignada` | TEXT | Nombre del gerente responsable |
| `activo` | BOOLEAN | Si está activo en la promotoría |

#### `Tramite` (objeto central — reemplaza `Opportunity`)
El trámite es el objeto de trabajo principal. Tiene ciclo de vida completo.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `folio` | TEXT | Folio interno de la promotoría |
| `folioGnp` | TEXT | Folio asignado por GNP (se llena al turnar) |
| `ramo` | SELECT | Vida / GMM / PyMES / Autos |
| `tipoTramite` | SELECT | Emisión / Endoso / Siniestro / Renovación / Cancelación |
| `estatus` | SELECT | Ver estados abajo |
| `agente` | RELATION | → `Agente` que solicita el trámite |
| `analistaAsignado` | RELATION | → `WorkspaceMember` analista responsable |
| `gerenteRamo` | RELATION | → `WorkspaceMember` gerente del ramo |
| `canalIngreso` | SELECT | WhatsApp / Correo / Manual |
| `fechaIngreso` | DATE_TIME | Cuándo llegó el trámite |
| `fechaLimiteDocumentacion` | DATE | Fecha máxima para completar docs |
| `fechaTurnoGnp` | DATE_TIME | Cuándo se turnó a GNP |
| `fechaResolucion` | DATE_TIME | Cuándo GNP resolvió |
| `motivoDetencion` | RICH_TEXT | Por qué se detuvo (si aplica) |
| `notasInternas` | RICH_TEXT | Notas del analista |
| `prioridad` | SELECT | Normal / Alta / Urgente |
| `monto` | CURRENCY | Monto de la póliza o siniestro (si aplica) |

**Estados del trámite (`estatus`):**
```
RECIBIDO → EN_REVISION_DOC → DOCUMENTACION_COMPLETA → TURNADO_GNP
    → EN_PROCESO_GNP → DETENIDO → RESUELTO → CANCELADO
```

#### `DocumentoTramite` (adjunto con metadatos — extiende `Attachment`)
Cada trámite tiene una checklist de documentos requeridos por ramo.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `tramite` | RELATION | → `Tramite` al que pertenece |
| `tipoDocumento` | SELECT | INE, Acta nacimiento, Formato GNP, Comprobante domicilio, etc. |
| `estatusDocumento` | SELECT | Pendiente / Recibido / Aceptado / Rechazado |
| `motivoRechazo` | TEXT | Si fue rechazado, por qué |
| `archivo` | FILES | El archivo adjunto |
| `fechaRecepcion` | DATE_TIME | Cuándo se recibió el documento |

#### `AlertaTramite` (registro de notificaciones enviadas)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `tramite` | RELATION | → `Tramite` asociado |
| `tipoAlerta` | SELECT | Documentación incompleta / Trámite detenido / Resolución disponible / Recordatorio |
| `canal` | SELECT | WhatsApp / Email / Interno |
| `mensaje` | RICH_TEXT | Contenido del mensaje enviado |
| `fechaEnvio` | DATE_TIME | Cuándo se envió |
| `respondido` | BOOLEAN | Si el agente respondió |

---

## Flujos de Trabajo Clave

### Flujo 1: Ingesta de Trámite

```
Agente envía docs (WhatsApp/Correo)
    ↓
Analista crea Tramite con estatus = RECIBIDO
    ↓
Selecciona Ramo → sistema muestra checklist de documentos requeridos
    ↓
Analista revisa cada documento y marca estatus (Recibido/Rechazado)
    ↓
Si documentación completa → estatus = DOCUMENTACION_COMPLETA
Si documentación incompleta → alert automática al agente
```

### Flujo 2: Turno a GNP

```
Tramite en DOCUMENTACION_COMPLETA
    ↓
Analista sube documentos a plataforma GNP manualmente
    ↓
Registra folioGnp y fechaTurnoGnp en el Tramite
    ↓
Estatus → TURNADO_GNP → EN_PROCESO_GNP
```

### Flujo 3: Supervisión y Alerta de Detenidos

```
Tramite en EN_PROCESO_GNP por más de N días sin resolución
    ↓
Workflow automático lo marca como DETENIDO
    ↓
Notificación al gerente del ramo
    ↓
Analista investiga con GNP y llena motivoDetencion
    ↓
Alerta enviada al agente vía WhatsApp/Email
```

### Flujo 4: Resolución

```
GNP resuelve el trámite
    ↓
Analista actualiza estatus → RESUELTO + fechaResolucion
    ↓
Notificación automática al agente
```

---

## Vistas por Rol

### Director / Director de Operaciones
- **Dashboard global**: trámites por estatus, por ramo, tiempo promedio de resolución
- **Vista detenidos**: todos los trámites `DETENIDO` con días de antigüedad
- **Vista pendientes GNP**: todos en `TURNADO_GNP` / `EN_PROCESO_GNP`

### Gerente de Ramo
- **Vista mi ramo**: todos los trámites del ramo (filtrado automático por ramo del gerente)
- **Vista analistas**: trámites agrupados por analista asignado
- **Vista urgentes**: prioridad = Urgente + detenidos de su ramo

### Analista
- **Mi bandeja**: trámites asignados a mí, ordenados por prioridad y fecha
- **En revisión**: trámites en `EN_REVISION_DOC` que necesitan acción
- **Vista documentos pendientes**: checklist de documentos incompletos

### Vista pública / por agente
- Trámites del agente X con sus estatus actuales (para soporte telefónico)

---

## Roles y Permisos en Twenty

| Rol | Puede crear | Puede editar | Puede ver |
|-----|-------------|--------------|-----------|
| `director` | Todo | Todo | Todo |
| `director_operaciones` | Todo | Todo | Todo |
| `gerente_ramo` | Trámites de su ramo | Trámites de su ramo | Solo su ramo |
| `analista` | Trámites asignados | Trámites asignados | Solo asignados |
| `viewer` | No | No | Solo lectura |

Los roles se configuran en `Settings > Roles` en la UI de Twenty.

---

## Integraciones Planeadas

### WhatsApp (vía API de Meta o Twilio)
- Webhook que recibe mensajes → crea `Tramite` con `canalIngreso = WhatsApp`
- Los adjuntos del chat se guardan automáticamente como `DocumentoTramite`
- Alertas de salida: el sistema envía mensajes WhatsApp al agente cuando hay novedades

### Correo Electrónico
- Cuenta de correo de la promotoría conectada vía IMAP (ya soportado por Twenty)
- Correos entrantes de agentes → se vinculan al `Tramite` correspondiente
- Los adjuntos de correo → `DocumentoTramite`

### Plataforma GNP
- GNP no tiene API pública disponible → el turno es manual
- El analista sube los documentos en la plataforma de GNP
- Registra el `folioGnp` en el CRM como confirmación

### Webhooks de Salida (Twenty → externo)
- Eventos como `tramite.detenido`, `tramite.resuelto` disparan webhooks configurables
- Permite integrar con sistemas de notificación externos en el futuro

---

## Checklists de Documentos por Ramo

Estos son los documentos mínimos requeridos. Se implementan como datos semilla o como configuración por ramo.

### Vida
- [ ] Solicitud de seguro firmada (formato GNP)
- [ ] Identificación oficial vigente (INE/Pasaporte) del contratante
- [ ] Acta de nacimiento del asegurado
- [ ] Comprobante de domicilio (no mayor a 3 meses)
- [ ] Cuestionario médico firmado
- [ ] Designación de beneficiarios firmada
- [ ] Comprobante de pago del primer recibo (si aplica)

### GMM
- [ ] Solicitud de seguro firmada
- [ ] Identificación oficial del contratante
- [ ] Comprobante de domicilio
- [ ] Cuestionario de salud por asegurado
- [ ] Comprobante de pago
- [ ] RFC del contratante (si es empresa)
- [ ] Acta constitutiva (si es grupo empresarial)

### PyMES
- [ ] Solicitud de seguro empresarial
- [ ] Acta constitutiva de la empresa
- [ ] Poder notarial del representante legal
- [ ] RFC y comprobante de domicilio fiscal
- [ ] Identificación del representante legal
- [ ] Estados financieros (si aplica al ramo)
- [ ] Inventario de bienes (para seguros de daños)

### Autos
- [ ] Solicitud de seguro de auto
- [ ] Factura o tarjeta de circulación del vehículo
- [ ] Identificación oficial del propietario
- [ ] Licencia de conducir vigente
- [ ] Comprobante de domicilio
- [ ] Fotografías del vehículo (frente, atrás, laterales, interiores, número de serie)

---

## Convenciones de Desarrollo para este Proyecto

### Nomenclatura de Objetos Personalizados

Todos los objetos custom siguen el patrón de Twenty pero con prefijo de dominio claro:

```typescript
// Objeto custom — nameSingular en camelCase, namePlural en camelCase plural
nameSingular: 'tramite'       // NO: 'Tramite', NO: 'tramites'
namePlural:   'tramites'
labelSingular: 'Trámite'      // Label con tilde, para UI
labelPlural:   'Trámites'
```

### Constantes de Dominio

Definir constantes en `packages/twenty-shared/src/` para los valores de negocio:

```typescript
// Estatus válidos de un trámite
export const TRAMITE_ESTATUS = {
  RECIBIDO: 'RECIBIDO',
  EN_REVISION_DOC: 'EN_REVISION_DOC',
  DOCUMENTACION_COMPLETA: 'DOCUMENTACION_COMPLETA',
  TURNADO_GNP: 'TURNADO_GNP',
  EN_PROCESO_GNP: 'EN_PROCESO_GNP',
  DETENIDO: 'DETENIDO',
  RESUELTO: 'RESUELTO',
  CANCELADO: 'CANCELADO',
} as const;

export const RAMOS = ['Vida', 'GMM', 'PyMES', 'Autos'] as const;
export type Ramo = typeof RAMOS[number];
```

### Workflows de Alerta

Los workflows para alertas automáticas se crean en la UI de Twenty (`Settings > Workflows`) o vía código en `packages/twenty-server/src/modules/workflow/`. Los triggers relevantes son:

- `tramite.created` → notificar al gerente del ramo
- `tramite.updated` (cuando `estatus = DETENIDO`) → notificar al gerente + alert al agente
- `tramite.updated` (cuando `estatus = RESUELTO`) → notificar al agente
- CRON diario → revisar trámites en `EN_PROCESO_GNP` sin actualización en 3+ días

---

## Comandos Clave

### Development
```bash
# Levantar el entorno completo con Docker (recomendado para este proyecto)
cd packages/twenty-docker && docker compose up -d

# O en modo desarrollo (requiere Node.js 20+)
yarn start

# Individual
npx nx start twenty-front     # Frontend en http://localhost:3001
npx nx start twenty-server    # Backend en http://localhost:3000
npx nx run twenty-server:worker  # Worker de background jobs
```

### Testing
```bash
# Archivo individual (preferido — más rápido)
npx jest path/to/test.test.ts --config=packages/PROJECT/jest.config.mjs

# Por paquete
npx nx test twenty-front
npx nx test twenty-server
npx nx run twenty-server:test:integration:with-db-reset

# Patrón específico
cd packages/twenty-server && npx jest "tramite"

# UI end-to-end: usar "Continue with Email" con credenciales prefilled
```

### Calidad de Código
```bash
# Linting (siempre preferir diff-with-main, es más rápido)
npx nx lint:diff-with-main twenty-front
npx nx lint:diff-with-main twenty-server
npx nx lint:diff-with-main twenty-front --configuration=fix  # auto-fix

# Type checking
npx nx typecheck twenty-front
npx nx typecheck twenty-server

# Formato
npx nx fmt twenty-front
npx nx fmt twenty-server
```

### Build
```bash
npx nx build twenty-shared   # Siempre primero
npx nx build twenty-front
npx nx build twenty-server
```

### Base de Datos
```bash
# Reset completo
npx nx database:reset twenty-server

# Generar migración (nombre en kebab-case)
npx nx run twenty-server:typeorm migration:generate src/database/typeorm/core/migrations/common/[nombre] -d src/database/typeorm/core/core.datasource.ts

# Aplicar migraciones
npx nx run twenty-server:database:migrate:prod

# Sincronizar metadata (después de cambiar objetos/campos)
npx nx run twenty-server:command workspace:sync-metadata
```

### GraphQL
```bash
# Regenerar tipos (después de cambiar el schema)
npx nx run twenty-front:graphql:generate
npx nx run twenty-front:graphql:generate --configuration=metadata
```

---

## Arquitectura Técnica

### Stack

| Capa | Tecnología |
|------|-----------|
| **Frontend** | React 18, TypeScript, Vite, React Router v6 |
| **Estado** | Jotai (global), Apollo Client (GraphQL cache) |
| **Estilos** | Linaria (CSS-in-JS zero-runtime) |
| **Backend** | NestJS, TypeScript |
| **GraphQL** | GraphQL Yoga + nestjs-query |
| **BD Principal** | PostgreSQL 16 |
| **Cache/Sesiones** | Redis 7 |
| **Jobs** | BullMQ |
| **Monorepo** | Nx + Yarn 4 |
| **i18n** | Lingui |
| **Email templates** | React Email |
| **Tests** | Jest + Playwright |

### Estructura de Paquetes
```
packages/
├── twenty-front/          # Aplicación React (frontend)
├── twenty-server/         # API NestJS (backend)
├── twenty-ui/             # Componentes UI compartidos (Linaria)
├── twenty-shared/         # Tipos y utilidades comunes
├── twenty-emails/         # Templates de email (React Email)
├── twenty-website/        # Sitio web (Next.js)
├── twenty-docs/           # Documentación (Mintlify)
├── twenty-zapier/         # Integración Zapier
├── twenty-e2e-testing/    # Tests E2E con Playwright
├── twenty-sdk/            # SDK publicado (ESM+CJS dual, reemplaza twenty-cli)
├── twenty-client-sdk/     # Client SDK
├── create-twenty-app/     # CLI para scaffolding
├── twenty-apps/           # Ejemplos de apps custom
├── twenty-companion/      # App desktop (Electron)
├── twenty-oxlint-rules/   # Reglas oxlint custom
├── twenty-docker/         # Configuraciones Docker Compose
└── twenty-utils/          # Scripts de setup (setup-dev-env.sh)
```

### Arquitectura Multi-tenant

Twenty usa multi-tenancy por esquema de PostgreSQL:
- `core` — datos del sistema (usuarios, workspaces, auth)
- `metadata_v[N]` — definición de objetos y campos
- `workspace_[ID]` — datos del tenant (registros de CRM)

Cada promotoría puede tener su propio workspace aislado.

### Sistema de Metadata (Customización)

El corazón de la extensibilidad de Twenty:
- **ObjectMetadata**: define objetos custom (equivale a una tabla)
- **FieldMetadata**: define campos de un objeto (con 24 tipos)
- **ViewEntity**: configuración de vistas (filtros, sorts, agrupaciones)
- **WorkflowEntity**: automatizaciones y triggers

Para crear objetos custom del dominio (Tramite, Agente, etc.):
- En UI: `Settings > Data Model > Add Object`
- En código: `packages/twenty-server/src/engine/metadata-modules/`

---

## Principios de Desarrollo

### General
- **Componentes funcionales** únicamente (no class components)
- **Named exports** únicamente (no default exports)
- **Types sobre interfaces** (excepto al extender interfaces de terceros)
- **String literals sobre enums** (excepto GraphQL enums)
- **Sin `any`** — TypeScript estricto
- **Sin abreviaciones**: `agente` no `ag`, `tramite` no `trm`
- **Event handlers** sobre `useEffect` para actualizaciones de estado

### Nomenclatura
- Variables/funciones: `camelCase`
- Constantes: `SCREAMING_SNAKE_CASE`
- Tipos/Clases: `PascalCase`
- Props de componentes: sufijo `Props` (e.g., `TramiteCardProps`)
- Archivos/directorios: `kebab-case` con sufijo descriptivo (`.component.tsx`, `.service.ts`, `.entity.ts`)
- Genéricos TypeScript: nombres descriptivos (`TData` no `T`)

### Estructura de Archivos
- Componentes < 300 líneas, servicios < 500 líneas
- Cada componente en su directorio con tests y stories
- Barrel exports con `index.ts`
- Import order: librerías externas → internos (`@/`) → relativos

### Comentarios
- Cortos (`//`), no JSDoc blocks
- Explican POR QUÉ (lógica de negocio), no QUÉ
- Múltiples líneas: varias líneas `//`, no `/** */`

### Estado
- **Jotai**: estado global (atoms primitivos, selectors derivados, atom families para colecciones dinámicas)
- **React hooks**: estado local del componente
- **Apollo Client**: cache de GraphQL
- Actualizaciones funcionales: `setState(prev => prev + 1)`

### Base de Datos y Migraciones
- Siempre generar migraciones cuando se cambian entidades
- Nombres en kebab-case (e.g., `add-tramite-folio-gnp`)
- Incluir lógica `up` y `down` en cada migración
- Nunca eliminar ni reescribir migraciones ya commiteadas

### Helpers de Utilidad
Usar los helpers de `twenty-shared` en lugar de type guards manuales:
- `isDefined()`, `isNonEmptyString()`, `isNonEmptyArray()`

### SDK y Paquetes Publicados
- Solo dependencias ESM-compatible (verificar `"type": "module"`, `"exports"` map)
- Usar `node:fs/promises` en lugar de `fs-extra` (CJS-only)
- `twenty-cli` está **deprecado** — usar `twenty-sdk`

---

## Setup del Entorno Local

### Con Docker (recomendado)

```bash
# El .env ya está configurado en packages/twenty-docker/.env
cd packages/twenty-docker
docker compose up -d

# Twenty disponible en:
# - Frontend + Backend: http://localhost:3000
```

Credenciales Docker:
- PostgreSQL: `postgres:postgres@localhost:5432`
- Redis: `localhost:6379`
- APP_SECRET: ver `packages/twenty-docker/.env`

### Modo Desarrollo (fuente)

```bash
# Script único que configura todo
bash packages/twenty-utils/setup-dev-env.sh

# Flags útiles:
# --docker   forzar modo Docker
# --down     detener servicios
# --reset    limpiar datos y reiniciar
```

**Nota CI**: GitHub Actions gestiona servicios vía Actions service containers — no usa el script.

---

## Archivos Importantes
- `nx.json` — configuración de tareas Nx
- `tsconfig.base.json` — configuración TypeScript base
- `package.json` — definición del workspace
- `.cursor/rules/` — guías de desarrollo detalladas
- `.mcp.json` — configuración MCP (Postgres read-only + Playwright)
- `packages/twenty-docker/.env` — variables de entorno para Docker local

### Inspección de Base de Datos (MCP Postgres)

El servidor MCP Postgres de solo lectura en `.mcp.json` permite:
- Inspeccionar datos de workspace, metadata y objetos durante desarrollo
- Verificar resultados de migraciones (columnas, tipos, constraints)
- Explorar estructura multi-tenant (core, metadata, workspace schemas)
- Debug de generación de schema GraphQL y `workspace:sync-metadata`

Para operaciones de escritura (reset, migraciones), usar los comandos CLI.

### Comandos Nx Útiles
```bash
# Grafo de dependencias del proyecto
npx nx graph

# Ejecutar targets en proyectos afectados (relativo a main)
npx nx affected --target=test --base=main
npx nx affected --target=build --base=main
```

---

## Workflow de Desarrollo

**IMPORTANTE**: Usar Context7 para generación de código, pasos de configuración o documentación de librerías/APIs. Usar las herramientas MCP de Context7 automáticamente sin esperar solicitud explícita.

### Antes de Hacer Cambios
1. Correr linting (`lint:diff-with-main`) y type checking después de cambios
2. Probar con suites de tests relevantes (preferir runs de archivo único)
3. Generar migraciones de BD para cambios en entidades
4. Verificar que cambios en GraphQL schema sean backward compatible
5. Correr `graphql:generate` después de cualquier cambio de schema GraphQL

### Estrategia de Testing
- **Testear comportamiento, no implementación** — perspectiva del usuario
- **Pirámide**: 70% unit, 20% integration, 10% E2E
- Consultar por elementos visibles al usuario (texto, roles, labels) sobre test IDs
- Nombres descriptivos: "should [comportamiento] when [condición]"
- Limpiar mocks entre tests con `jest.clearAllMocks()`

## Contexto del problema
La promotoría actúa como intermediaria entre agentes de seguros GNP y la aseguradora. Los analistas reciben trámites de los agentes, los revisan y los envían al portal de GNP. El proceso hoy es completamente manual, disperso en correos personales y WhatsApp, sin visibilidad centralizada ni métricas de operación.

## Dolores confirmados
•	Trámites llegan por correo a cada analista individualmente — no hay bandeja centralizada
•	Sin visibilidad de estatus: el agente pregunta por WhatsApp cuándo va su trámite
•	Trámites se pierden cuando un analista no está disponible
•	Dos analistas pueden trabajar el mismo trámite sin saberlo
•	El director no sabe cuántos trámites hay abiertos ni cuáles están vencidos
•	Sin registro de fechas de entrada, límite de SLA ni resolución
•	GNP rechaza trámites y no hay seguimiento sistemático de las razones

## Estructura organizacional
•	Directora de Operaciones — visibilidad total, toma de decisiones
•	Gerentes de ramo (Vida, GMM, Autos, PYME, Daños) — cada uno con su equipo
•	Especialistas / Analistas — atienden cartera asignada por agente y ramo
•	Agentes externos — pueden ser individuales, con asistentes o despachos formales
•	Contactos — personas reales que envían los trámites (pueden ser asistentes del agente)


### arquitectura
- Gmail Fuente del correo entrante
- n8n Trigger y notificaciones salientes
- FastAPI Procesamiento, agentes de IA, lógica de negocio
- Supabase Persistencia, storage de docs, deduplicación
- RunPod OCR pesado en documentos escaneados
- Twenty CRM Registro final del Trámite + vista del analista
- Vercel Frontend si se necesita UI custom (bandeja manual)
- Railway Deploy de FastAPI
