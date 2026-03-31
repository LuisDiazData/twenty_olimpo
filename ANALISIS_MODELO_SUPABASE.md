# Análisis y Planificación del Modelo de Datos en Supabase para InsuraCRM AI

He revisado el contexto del proyecto **Twenty Olimpo** (integración CRM para Promotoría GNP con N8N, FastAPI, LiteLLM y Supabase) y he evaluado los requerimientos de las diferentes fases funcionales (procesamiento de reclamos/trámites con IA, pre-análisis de documentos, dashboard de métricas operativas y procesamiento avanzado de adjuntos).

A continuación, detallo el **análisis de la situación actual**, los **puntos ciegos identificados** y el **modelo de datos resultante** (el cual ya he implementado en el archivo de migración `scripts/supabase/migrations/006_data_model_enhancements.sql`).

---

## 1. Situación Actual vs. Nuevas Funcionalidades
Actualmente Supabase es la fuente de verdad técnica del pipeline antes de que los datos lleguen a **Twenty CRM**. Existen las siguientes tablas base:
1. `incoming_emails` (Ingesta original)
2. `email_attachments` (Metadatos de Storage)
3. `dedup_index` (Control de duplicados)
4. `ocr_results` (Resultados de RunPod)
5. `contact_email_map` (Caché de IDs de Twenty)
6. `ai_processing_log` (Auditoría de agentes IA en FastAPI)

## 2. Puntos Ciegos Identificados (Blind Spots)

Al analizar las nuevas funcionalidades solicitadas, detecté las siguientes carencias:

### A. Extracción de Archivos ZIP y Lineaje
- **Problema:** Si un email trae un `.zip` del cual extraemos 5 PDFs, las tablas no registrarían fácilmente que esos PDFs provienen de dicho ZIP. Si fallara la validación, sería difícil relacionar el PDF extraído con el archivo "padre".
- **Solución:** Agregar una referencia jerárquica (`parent_attachment_id`) a la tabla `email_attachments`, además de un indicador (`is_compressed_archive`).

### B. Descifrado de PDFs con Contraseñas
- **Problema:** El sistema intentará descifrar PDFs protegidos en cascada (cascading password strategy). Sin un seguimiento, el pipeline no podrá reportar eficientemente al analista si un trámite está trabado porque un PDF no pudo ser desencriptado.
- **Solución:** Agregar metadatos de cifrado: `is_encrypted` y el estado de dicho proceso (`decryption_status`).

### C. Sistema Dinámico del Checklist Documental (Pre-análisis)
- **Problema:** La evaluación del checklist requiere saber qué documentos son obligatorios para cada trámite. Si esto se codifica "en duro" en Python, cada vez que GNP modifique sus reglas será necesario cambiar el código. Además, no se guardaban explícitamente los tipos documentales detectados por documento (ej. "INE").
- **Solución:** Crear una tabla catálogo `procedure_requirements` en Supabase para tener la regla de forma dinámica. Además, en vez de crear tablas de análisis separadas, decidí agregar columnas a `email_attachments` (análisis por documento) y `incoming_emails` (evaluación completa de los faltantes) para evitar duplicidad o joins innecesarios.

### D. Métricas para el Dashboard Operativo
- **Problema:** Twenty CRM guarda eventos base, pero no detalla analíticamente el "Tiempo de Intervención Manual" u otras métricas propias del dashboard. Intentar sacar esos tiempos de procesamiento intermedio directo por GraphQL sería ineficiente.
- **Solución:** Añadir `is_manual_intervention` y `resolved_at` a `incoming_emails` y crear `analyst_metrics_log`. Esto registrará acciones atómicas del equipo de gestión (ej. "Aprobación manual del OCR") permitiendo consultas SQL ligeras para el dashboard.

---

## 3. Implementación del Modelo (Migración 006 Creada)

He diseñado el archivo `scripts/supabase/migrations/006_data_model_enhancements.sql`:

#### Extensiones a `incoming_emails` (Manejo del caso y SLA)
- `inferred_procedure_type`: El tipo de trámite detectado por LiteLLM.
- `missing_documents_json`: Lista de documentos pendientes frente al checklist.
- `checklist_status`: Estado general del checklist (`pending`, `complete`, `incomplete`).
- `is_manual_intervention`: Flag detonado si se requirió la ayuda de un analista.
- `intervention_reason`: Motivo del desvío manual (Ej. "OCR de credencial ilegible").
- Columnas de cálculo de SLAs: `first_response_at`, `resolved_at`, y `sla_deadline`.

#### Extensiones a `email_attachments` (Manejo avanzado de archivos)
- `parent_attachment_id`: Llave foránea a sí mismo para vincular extracción de ZIPs/RARs.
- `is_compressed_archive`: `true` si es un ZIP original.
- `is_encrypted` y `decryption_status`: Metadatos de contraseñas de PDFs.
- `inferred_document_type`: Etiqueta clasificada por IA (Ej. `Póliza`, `INE`).
- `document_validation_status`: Estatus de verificaciones de legibilidad.
- `validation_details_json`: Notas o justificación de validación de la IA.

#### Tablas Nuevas
1. **`procedure_requirements`:** Catálogo de apoyo. Contiene `procedure_type` (Ej. Endoso), `required_document_types` (JSONB). Es la base técnica para cotejar automáticamente "qué falta" sin tocar Python.
2. **`analyst_metrics_log`:** Un registro especializado donde FastAPI y los Webhooks de Twenty almacenarán las interacciones humanas con métricas de tiempo (`time_taken_ms`).
