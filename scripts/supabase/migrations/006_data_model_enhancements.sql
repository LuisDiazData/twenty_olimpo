-- ============================================================
-- Olimpo Promotoría GNP — Supabase Data Model Enhancements
-- Migración 006: Extensiones para pre-análisis de documentos, manejo de ZIPs/Passwords, y métricas operativas
-- ============================================================

-- -------------------------------------------------------
-- 1. Actualizaciones a INCOMING_EMAILS
-- Soporte para pre-análisis de documentos y SLA
-- -------------------------------------------------------
ALTER TABLE incoming_emails
  ADD COLUMN IF NOT EXISTS inferred_procedure_type TEXT,
  ADD COLUMN IF NOT EXISTS missing_documents_json JSONB,
  ADD COLUMN IF NOT EXISTS checklist_status TEXT 
    CHECK (checklist_status IN ('pending', 'complete', 'incomplete')),
  ADD COLUMN IF NOT EXISTS is_manual_intervention BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS intervention_reason TEXT,
  ADD COLUMN IF NOT EXISTS first_response_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS sla_deadline TIMESTAMPTZ;

COMMENT ON COLUMN incoming_emails.checklist_status IS 'Estado del checklist según LiteLLM (pending, complete, incomplete)';
COMMENT ON COLUMN incoming_emails.is_manual_intervention IS 'Indica si requirió intervención humana en el dashboard operativo';

-- -------------------------------------------------------
-- 2. Actualizaciones a EMAIL_ATTACHMENTS
-- Soporte para ZIPs parent/child, PDFs con contraseña y clasificación
-- -------------------------------------------------------
ALTER TABLE email_attachments
  ADD COLUMN IF NOT EXISTS parent_attachment_id UUID REFERENCES email_attachments(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS is_compressed_archive BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS is_encrypted BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS decryption_status TEXT 
    CHECK (decryption_status IN ('pending', 'success', 'failed', 'not_needed')) DEFAULT 'not_needed',
  ADD COLUMN IF NOT EXISTS inferred_document_type TEXT, -- e.g. INE, Comprobante Domicilio
  ADD COLUMN IF NOT EXISTS document_validation_status TEXT 
    CHECK (document_validation_status IN ('pending', 'valid', 'invalid', 'needs_review')) DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS validation_details_json JSONB; -- Respuestas detalladas del LLM respecto a la validez

COMMENT ON COLUMN email_attachments.parent_attachment_id IS 'Si el archivo proviene de un ZIP extraído, referencia al adjunto original';
COMMENT ON COLUMN email_attachments.is_encrypted IS 'Indica si el PDF requería descifrado en cascada';

-- -------------------------------------------------------
-- 3. Tabla: PROCEDURE_REQUIREMENTS
-- Diccionario de documentos requeridos por tipo de trámite
-- Evita hardcodear las reglas en Python, permitiendo escalar a más tipos
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS procedure_requirements (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    procedure_type TEXT NOT NULL UNIQUE,  
    required_document_types JSONB NOT NULL, -- Ej: '["INE", "Comprobante Domicilio", "Solicitud"]'
    optional_document_types JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE procedure_requirements IS 'Catálogo dinámico de documentos requeridos por tipo de trámite (Nueva Póliza, Endoso, etc.)';

CREATE TRIGGER trg_procedure_requirements_updated_at
  BEFORE UPDATE ON procedure_requirements
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- -------------------------------------------------------
-- 4. Tabla: ANALYST_METRICS_LOG
-- Seguimiento granular para el Dashboard Operativo
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS analyst_metrics_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tramite_twenty_id TEXT NOT NULL,
    incoming_email_id UUID REFERENCES incoming_emails(id) ON DELETE CASCADE,
    analyst_email TEXT, -- o ID referenciado a Twenty
    action_type TEXT NOT NULL, -- 'status_change', 'manual_approval', 'requested_more_info'
    action_details JSONB,
    time_taken_ms INTEGER, -- Tiempo transcurrido desde la creación o última acción
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE analyst_metrics_log IS 'Log de acciones de los analistas en Twenty para calcular tiempos de respuesta y SLAs en el Dashboard';
