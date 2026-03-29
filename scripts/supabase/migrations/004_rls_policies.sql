-- ============================================================
-- Olimpo Promotoría GNP — Row Level Security (RLS)
-- Migración 004: Políticas de seguridad por fila
--
-- Arquitectura de acceso:
-- - FastAPI (Railway): usa service_role key → bypassa RLS
-- - n8n: usa service_role key → bypassa RLS
-- - Vercel frontend (futuro): usaría anon/authenticated key → sujeto a RLS
-- ============================================================

-- Habilitar RLS en todas las tablas del pipeline
ALTER TABLE incoming_emails      ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_attachments    ENABLE ROW LEVEL SECURITY;
ALTER TABLE dedup_index          ENABLE ROW LEVEL SECURITY;
ALTER TABLE ocr_results          ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_processing_log    ENABLE ROW LEVEL SECURITY;
ALTER TABLE contact_email_map    ENABLE ROW LEVEL SECURITY;

-- -------------------------------------------------------
-- Por ahora: acceso completo solo para service_role
-- (FastAPI y n8n usan service_role key)
-- Cuando se implemente Vercel frontend, agregar políticas
-- por authenticated role con filtros de workspace.
-- -------------------------------------------------------

CREATE POLICY "service_role_incoming_emails"
  ON incoming_emails FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_email_attachments"
  ON email_attachments FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_dedup_index"
  ON dedup_index FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_ocr_results"
  ON ocr_results FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_ai_processing_log"
  ON ai_processing_log FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_contact_email_map"
  ON contact_email_map FOR ALL TO service_role USING (true) WITH CHECK (true);

-- -------------------------------------------------------
-- Placeholder: políticas para Vercel frontend (futuro)
-- Se activarán cuando se implemente autenticación en Vercel.
-- Descomenta y adapta cuando sea necesario.
-- -------------------------------------------------------

-- Ejemplo: analistas pueden ver incoming_emails de su workspace
-- CREATE POLICY "authenticated_read_incoming_emails"
--   ON incoming_emails FOR SELECT TO authenticated
--   USING (auth.uid() IS NOT NULL);
