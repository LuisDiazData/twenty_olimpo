-- ============================================================
-- Migración 001 — Columnas thread_id / message_id / inline
-- Ejecutar en: Supabase Dashboard → SQL Editor
-- ============================================================

-- tramites_pipeline: soporte de hilos de conversación Gmail
ALTER TABLE tramites_pipeline
  ADD COLUMN IF NOT EXISTS thread_id  TEXT,
  ADD COLUMN IF NOT EXISTS message_id TEXT;

CREATE INDEX IF NOT EXISTS idx_tramites_thread_id
  ON tramites_pipeline(thread_id)
  WHERE thread_id IS NOT NULL;

-- attachments_log: distinguir adjuntos normales vs imágenes inline del HTML
ALTER TABLE attachments_log
  ADD COLUMN IF NOT EXISTS es_inline  BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS mime_type  TEXT;

-- Verificación: muestra las columnas nuevas (debe devolver 4 filas)
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name IN ('tramites_pipeline', 'attachments_log')
  AND column_name IN ('thread_id', 'message_id', 'es_inline', 'mime_type')
ORDER BY table_name, column_name;
