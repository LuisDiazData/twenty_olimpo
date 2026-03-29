-- ============================================================
-- Olimpo Promotoría GNP — Supabase Pipeline Tables
-- Migración 001: Tablas del pipeline de procesamiento de emails
--
-- Aplicar en: Supabase Dashboard > SQL Editor
-- O via psql: psql $SUPABASE_DB_URL -f 001_pipeline_tables.sql
-- ============================================================

-- -------------------------------------------------------
-- 1. INCOMING_EMAILS
-- Staging de emails recibidos desde Gmail vía n8n.
-- Estado del ciclo de vida antes de convertirse en Tramite.
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS incoming_emails (
  id                 UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  gmail_message_id   TEXT        UNIQUE NOT NULL,
  gmail_thread_id    TEXT,
  sender_email       TEXT        NOT NULL,
  sender_name        TEXT,
  subject            TEXT,
  body_text          TEXT,
  body_html          TEXT,
  received_at        TIMESTAMPTZ NOT NULL,
  attachment_count   INTEGER     DEFAULT 0,
  -- received | parsing | extracting | ready_for_tramite | linked | duplicate | error
  processing_status  TEXT        NOT NULL DEFAULT 'received'
                     CHECK (processing_status IN (
                       'received', 'parsing', 'extracting',
                       'ready_for_tramite', 'linked', 'duplicate', 'error'
                     )),
  error_message      TEXT,
  -- Referencia al Tramite en Twenty CRM (UUID del objeto Tramite)
  tramite_twenty_id  TEXT,
  created_at         TIMESTAMPTZ DEFAULT NOW(),
  updated_at         TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE incoming_emails IS
  'Staging de emails entrantes desde Gmail. Fuente de verdad del pipeline de ingesta.';

-- -------------------------------------------------------
-- 2. EMAIL_ATTACHMENTS
-- Archivos adjuntos de emails. Referencia a Supabase Storage.
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_attachments (
  id                 UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  incoming_email_id  UUID        NOT NULL REFERENCES incoming_emails(id) ON DELETE CASCADE,
  filename           TEXT        NOT NULL,
  mime_type          TEXT,
  size_bytes         INTEGER,
  -- Ruta dentro del bucket: incoming-raw/{email_id}/{filename}
  storage_path       TEXT,
  storage_bucket     TEXT        DEFAULT 'incoming-raw',
  -- pending | queued | processing | completed | skipped | failed
  ocr_status         TEXT        NOT NULL DEFAULT 'pending'
                     CHECK (ocr_status IN (
                       'pending', 'queued', 'processing',
                       'completed', 'skipped', 'failed'
                     )),
  created_at         TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE email_attachments IS
  'Archivos adjuntos de emails. storage_path apunta al bucket de Supabase Storage.';

-- -------------------------------------------------------
-- 3. DEDUP_INDEX
-- Índice de deduplicación para evitar Tramites duplicados.
-- Hash de (sender_email + subject_normalizado + ventana_fecha).
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS dedup_index (
  id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  content_hash        TEXT        UNIQUE NOT NULL,
  gmail_message_id    TEXT,
  incoming_email_id   UUID        REFERENCES incoming_emails(id),
  -- UUID del Tramite en Twenty CRM si ya fue procesado
  tramite_twenty_id   TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dedup_index IS
  'Índice de deduplicación. content_hash = sha256(sender+subject_norm+fecha_ventana).';

-- -------------------------------------------------------
-- 4. OCR_RESULTS
-- Resultados de OCR procesados por RunPod.
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS ocr_results (
  id                     UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  attachment_id          UUID        NOT NULL REFERENCES email_attachments(id) ON DELETE CASCADE,
  runpod_job_id          TEXT,
  extracted_text         TEXT,
  -- Campos estructurados extraídos: {"nombre": "...", "curp": "...", "poliza": "..."}
  extracted_json         JSONB,
  -- Confianza global del OCR (0.0 - 1.0)
  confidence_score       FLOAT,
  processing_duration_ms INTEGER,
  -- queued | processing | completed | failed
  status                 TEXT        NOT NULL DEFAULT 'queued'
                         CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
  error_message          TEXT,
  created_at             TIMESTAMPTZ DEFAULT NOW(),
  updated_at             TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE ocr_results IS
  'Resultados de OCR de RunPod. extracted_json contiene campos estructurados del documento.';

-- -------------------------------------------------------
-- 5. AI_PROCESSING_LOG
-- Auditoría de cada paso del agente de IA en FastAPI.
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_processing_log (
  id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  incoming_email_id   UUID        REFERENCES incoming_emails(id) ON DELETE SET NULL,
  -- Nombre del agente FastAPI que procesó: 'classifier', 'extractor', 'contact_matcher'
  agent_name          TEXT        NOT NULL,
  -- Acción ejecutada: 'classify_ramo', 'extract_fields', 'match_contact', 'create_tramite'
  action              TEXT        NOT NULL,
  input_data          JSONB,
  output_data         JSONB,
  model_used          TEXT,
  tokens_used         INTEGER,
  duration_ms         INTEGER,
  success             BOOLEAN     DEFAULT TRUE,
  error_message       TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE ai_processing_log IS
  'Log de auditoría del pipeline de IA. Permite debuggear y mejorar los agentes de FastAPI.';

-- -------------------------------------------------------
-- 6. CONTACT_EMAIL_MAP
-- Cache de mapeo email → IDs de Twenty CRM.
-- Sincronizado periódicamente desde Twenty para evitar
-- consultas por cada email entrante.
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS contact_email_map (
  id                   UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  email                TEXT        UNIQUE NOT NULL,
  -- IDs de objetos en Twenty CRM
  twenty_person_id     TEXT,
  twenty_company_id    TEXT,
  display_name         TEXT,
  -- Rol del contacto en la promotoría: agente, asistente, despacho
  rol_contacto         TEXT,
  last_synced_at       TIMESTAMPTZ DEFAULT NOW(),
  created_at           TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE contact_email_map IS
  'Cache email→Twenty. Sincronizado desde Twenty CRM. FastAPI lo consulta para match rápido.';

-- -------------------------------------------------------
-- Trigger: actualizar updated_at automáticamente
-- -------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_incoming_emails_updated_at
  BEFORE UPDATE ON incoming_emails
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_ocr_results_updated_at
  BEFORE UPDATE ON ocr_results
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
