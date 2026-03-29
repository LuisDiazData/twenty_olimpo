-- ============================================================
-- Olimpo Promotoría GNP — Supabase Pipeline Indexes
-- Migración 002: Índices para performance del pipeline
-- ============================================================

-- incoming_emails
CREATE INDEX IF NOT EXISTS idx_incoming_emails_status
  ON incoming_emails(processing_status);

CREATE INDEX IF NOT EXISTS idx_incoming_emails_sender
  ON incoming_emails(sender_email);

CREATE INDEX IF NOT EXISTS idx_incoming_emails_received_at
  ON incoming_emails(received_at DESC);

CREATE INDEX IF NOT EXISTS idx_incoming_emails_tramite
  ON incoming_emails(tramite_twenty_id)
  WHERE tramite_twenty_id IS NOT NULL;

-- email_attachments
CREATE INDEX IF NOT EXISTS idx_email_attachments_email
  ON email_attachments(incoming_email_id);

CREATE INDEX IF NOT EXISTS idx_email_attachments_ocr_status
  ON email_attachments(ocr_status)
  WHERE ocr_status IN ('pending', 'queued', 'processing');

-- dedup_index
-- content_hash ya tiene UNIQUE que crea índice implícito

-- ocr_results
CREATE INDEX IF NOT EXISTS idx_ocr_results_attachment
  ON ocr_results(attachment_id);

CREATE INDEX IF NOT EXISTS idx_ocr_results_status
  ON ocr_results(status)
  WHERE status IN ('queued', 'processing');

CREATE INDEX IF NOT EXISTS idx_ocr_results_runpod_job
  ON ocr_results(runpod_job_id)
  WHERE runpod_job_id IS NOT NULL;

-- ai_processing_log
CREATE INDEX IF NOT EXISTS idx_ai_log_email
  ON ai_processing_log(incoming_email_id);

CREATE INDEX IF NOT EXISTS idx_ai_log_created_at
  ON ai_processing_log(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_log_agent_action
  ON ai_processing_log(agent_name, action);

-- contact_email_map
-- email ya tiene UNIQUE que crea índice implícito
CREATE INDEX IF NOT EXISTS idx_contact_email_twenty_person
  ON contact_email_map(twenty_person_id)
  WHERE twenty_person_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_contact_email_twenty_company
  ON contact_email_map(twenty_company_id)
  WHERE twenty_company_id IS NOT NULL;
