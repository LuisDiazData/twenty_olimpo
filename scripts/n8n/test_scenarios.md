# Test Scenarios — Pipeline Trámites v3

Escenarios para verificar el comportamiento end-to-end del workflow antes de poner en producción.

---

## Escenario 1 — Trámite válido, agente registrado

**Input de prueba**
- Correo de: `juan.perez@agente.com` (agente registrado en Twenty, clave GNP `A-12345`)
- Asunto: `Emisión de vida — Juan García`
- Cuerpo: "Adjunto solicitud de seguro de vida para Juan García, incluye INE y cuestionario médico firmado. Suma asegurada 500,000 MXN."
- Adjuntos: `solicitud_vida.pdf`, `ine_juan_garcia.pdf`, `cuestionario_medico.pdf`

**Output esperado en Supabase**

| Tabla | Campo | Valor esperado |
|-------|-------|----------------|
| `tramites_pipeline` | `status` | `completado` |
| `tramites_pipeline` | `ramo` | `Vida` |
| `tramites_pipeline` | `tipo_tramite` | `Emision` |
| `tramites_pipeline` | `correo_remitente` | `juan.perez@agente.com` |
| `attachments_log` | `clasificacion_completada` | `true` (1 registro por adjunto) |
| `historial_asignaciones` | `tipo_asignacion` | `automatica` |

**Output esperado en Twenty CRM**
- Objeto `Tramite` creado con `estatus = RECIBIDO`
- `agente` vinculado a Juan Pérez (encontrado por email)
- `analistaAsignado` asignado automáticamente al analista activo de Vida
- `folio` generado formato `TRM-YYYYMMDD-XXXXX`

**Acuse esperado al remitente**
- Asunto: `Tu trámite fue recibido — Folio TRM-XXXXXX`
- Incluye nombre del analista asignado

**Estado esperado:** `creado`

---

## Escenario 2 — ZIP cifrado (adjunto con contraseña)

**Input de prueba**
- Correo de: `ana.lopez@agente.com`
- Asunto: `Endoso GMM — Grupo Empresarial XYZ`
- Cuerpo: "Documentos del endoso en el ZIP adjunto. La contraseña es: seguro2024"
- Adjuntos: `documentos_endoso.zip` (ZIP protegido con contraseña)

**Output esperado en Supabase**

| Tabla | Campo | Valor esperado |
|-------|-------|----------------|
| `attachments_log` | `error` | mensaje indicando ZIP cifrado o error de extracción |
| `attachments_log` | `clasificacion_completada` | `false` |
| `tramites_pipeline` | `documentos_con_error` | `1` |
| `tramites_pipeline` | `status` | `revision_manual` (Agente 4 detecta docs incompletos) |

**Output esperado en Twenty CRM**
- Objeto `Tramite` creado o en modo `revision_manual`
- `notasInternas` puede incluir aviso de adjunto no procesable

**Acuse esperado al remitente**
- Asunto: `Tu trámite está en revisión`
- Sin folio de analista asignado

**Estado esperado:** `revision_manual` (documentos no procesados correctamente)

---

## Escenario 3 — Reply de hilo (email que es respuesta de cadena previa)

**Input de prueba**
- Correo con header `In-Reply-To` apuntando a un `message_id` ya registrado en `tramites_pipeline`
- De: `carlos.ramos@agente.com`
- Asunto: `Re: Trámite de siniestro — María Rodríguez`
- Cuerpo: "Adjunto el acta policial que me solicitaron."
- Adjuntos: `acta_policial.pdf`

**Output esperado en Supabase**

| Tabla | Campo | Valor esperado |
|-------|-------|----------------|
| `tramites_pipeline` | `thread_id` | coincide con registro previo → deduplicado |
| `pipeline_logs` | (no debe haber entrada de error) | sin errores |

**Comportamiento esperado en workflow**
- El nodo `Check Reply` detecta `is_reply = true`
- El flujo se desvía al branch `Process Reply` (no crea nuevo trámite)
- El reply se añade como nota o documento al trámite existente
- No se envía acuse de nuevo trámite

**Output esperado en Twenty CRM**
- El trámite original recibe la nota o documento adicional
- No se crea duplicado

**Acuse esperado al remitente**
- Sin acuse (el branch de reply no envía confirmación de nuevo trámite)

**Estado esperado:** `reply_procesado` (el flujo termina en `Log Reply`)

---

## Escenario 4 — Agente desconocido (remitente no en Twenty)

**Input de prueba**
- Correo de: `desconocido@nuevocliente.com` (dirección que no existe en Twenty CRM)
- Asunto: `Quiero contratar seguro de autos`
- Cuerpo: "Me recomendaron con ustedes para asegurar mi auto. ¿Qué necesito?"
- Adjuntos: ninguno

**Output esperado en Supabase**

| Tabla | Campo | Valor esperado |
|-------|-------|----------------|
| `tramites_pipeline` | `status` | `revision_manual` |
| `tramites_pipeline` | `agente_cua` | `null` |
| `historial_asignaciones` | `motivo` | contiene "agente no identificado" |

**Output esperado en Twenty CRM**
- El Agente 4 no encuentra al agente en Twenty por email, CUA ni nombre fuzzy
- No se asigna analista automáticamente
- El trámite queda en `revision_manual` sin analista

**Acuse esperado al remitente**
- Asunto: `Tu trámite está en revisión`
- Cuerpo genérico sin folio de analista

**Estado esperado:** `revision_manual`, motivo: `agente no identificado`

---

## Escenario 5 — Posible duplicado (alta similitud con trámite reciente)

**Input de prueba**
- Correo de: `roberto.silva@agente.com` (agente registrado)
- Asunto: `Emisión póliza vida — Pedro Martínez` (idéntico a un trámite procesado hace 2 horas)
- Cuerpo: texto casi idéntico al de un trámite reciente del mismo agente para el mismo asegurado
- Adjuntos: los mismos 3 documentos con nombres similares

**Output esperado en Supabase**

| Tabla | Campo | Valor esperado |
|-------|-------|----------------|
| `tramites_pipeline` | `es_duplicado_posible` | `true` |
| `tramites_pipeline` | `tramite_duplicado_ref` | ID del trámite original |
| `tramites_pipeline` | `status` | `revision_manual` |

**Output esperado en Twenty CRM**
- El Agente 4 detecta `es_duplicado_posible = true` con confianza alta
- No se crea un segundo trámite automáticamente
- Se registra en `revision_manual` con motivo visible para el analista

**Acuse esperado al remitente**
- Asunto: `Tu trámite está en revisión`
- Sin folio de analista asignado

**Estado esperado:** `revision_manual`, motivo: `posible duplicado`

---

## Variables de entorno requeridas para pruebas

```bash
AGENTES_BASE_URL=http://localhost:4000      # o http://host.docker.internal:4000 en Docker
SUPABASE_URL=https://<proyecto>.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>
EQUIPO_EMAIL=operaciones@olimpo.com.mx
```

## Cómo ejecutar los escenarios

1. Importar `pipeline_tramites_v3.json` en n8n (Settings → Import Workflow)
2. Configurar las variables de entorno en n8n (Settings → Variables)
3. Activar el workflow
4. Para cada escenario, enviar un correo de prueba a la cuenta Gmail conectada
5. Verificar en Supabase Table Editor las tablas indicadas
6. Verificar en Twenty CRM → Trámites el registro creado
7. Revisar el correo del remitente de prueba para confirmar el acuse

## Tabla resumen

| # | Escenario | Estado esperado | Acuse |
|---|-----------|----------------|-------|
| 1 | Trámite válido, agente registrado | `creado` | Folio + analista |
| 2 | ZIP cifrado | `revision_manual` | Genérico |
| 3 | Reply de hilo | `reply_procesado` | Sin acuse |
| 4 | Agente desconocido | `revision_manual` | Genérico |
| 5 | Posible duplicado | `revision_manual` | Genérico |
