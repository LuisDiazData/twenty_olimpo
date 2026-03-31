-- ============================================================
-- Olimpo Promotoría GNP — Supabase Migration 007
-- Agente 3: Columnas para extracción y clasificación de documentos
-- Aplica a la tabla attachments_log (registros por-documento del pipeline)
-- ============================================================

ALTER TABLE attachments_log
  ADD COLUMN IF NOT EXISTS tipo_documento          TEXT,
  ADD COLUMN IF NOT EXISTS texto_extraido          TEXT,
  ADD COLUMN IF NOT EXISTS datos_extraidos         JSONB,
  ADD COLUMN IF NOT EXISTS metodo_extraccion       TEXT,
  ADD COLUMN IF NOT EXISTS ocr_completado          BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS clasificacion_completada BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS twenty_documento_id     TEXT,
  ADD COLUMN IF NOT EXISTS error_detalle           TEXT,
  ADD COLUMN IF NOT EXISTS procesado_at            TIMESTAMPTZ;

COMMENT ON COLUMN attachments_log.tipo_documento           IS 'Tipo clasificado por LLM: INE/IFE, Póliza GNP, Formato GNP, etc.';
COMMENT ON COLUMN attachments_log.texto_extraido           IS 'Texto crudo extraído del documento (pdfplumber, OCR o XML)';
COMMENT ON COLUMN attachments_log.datos_extraidos          IS 'Campos estructurados extraídos: nombre_titular, numero_poliza, rfc, etc.';
COMMENT ON COLUMN attachments_log.metodo_extraccion        IS 'pdf_texto | ocr_runpod | xml_texto | texto_plano';
COMMENT ON COLUMN attachments_log.ocr_completado           IS 'TRUE si se usó RunPod OCR para este documento';
COMMENT ON COLUMN attachments_log.clasificacion_completada IS 'TRUE cuando el LLM terminó de clasificar el documento';
COMMENT ON COLUMN attachments_log.twenty_documento_id      IS 'ID del objeto Documento en Twenty CRM (si ya fue creado)';
COMMENT ON COLUMN attachments_log.error_detalle            IS 'Detalle del error si la clasificación falló';
COMMENT ON COLUMN attachments_log.procesado_at             IS 'Timestamp UTC en que se completó el procesamiento';
