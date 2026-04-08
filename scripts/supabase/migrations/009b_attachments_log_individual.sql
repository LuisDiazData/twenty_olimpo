-- ============================================================
-- Olimpo Promotoría GNP — Supabase Migration 009
-- Columnas nuevas en attachments_log para modelo 1:1 por documento
-- Permite registrar un documentoAdjunto en Twenty por cada archivo
-- ============================================================

ALTER TABLE public.attachments_log
  ADD COLUMN IF NOT EXISTS tramite_id           TEXT,
  ADD COLUMN IF NOT EXISTS nombre               TEXT,
  ADD COLUMN IF NOT EXISTS storage_path         TEXT,
  ADD COLUMN IF NOT EXISTS mime_type            TEXT,
  ADD COLUMN IF NOT EXISTS tamano_bytes         INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS was_encrypted        BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS decryption_successful BOOLEAN DEFAULT TRUE;

-- Índices para consultas frecuentes del pipeline
CREATE INDEX IF NOT EXISTS idx_attachments_log_tramite_id
  ON public.attachments_log (tramite_id);

CREATE INDEX IF NOT EXISTS idx_attachments_log_twenty_id
  ON public.attachments_log (twenty_documento_id);

COMMENT ON COLUMN public.attachments_log.tramite_id
  IS 'ID del trámite (email_id del pipeline) al que pertenece este documento';
COMMENT ON COLUMN public.attachments_log.nombre
  IS 'Nombre original del archivo recibido';
COMMENT ON COLUMN public.attachments_log.storage_path
  IS 'Ruta en Supabase Storage: {email_id}/{filename}';
COMMENT ON COLUMN public.attachments_log.mime_type
  IS 'MIME type detectado del archivo';
COMMENT ON COLUMN public.attachments_log.tamano_bytes
  IS 'Tamaño del archivo en bytes';
COMMENT ON COLUMN public.attachments_log.was_encrypted
  IS 'TRUE si el archivo (PDF/ZIP/RAR) estaba protegido con contraseña';
COMMENT ON COLUMN public.attachments_log.decryption_successful
  IS 'TRUE si se logró desencriptar el archivo';
