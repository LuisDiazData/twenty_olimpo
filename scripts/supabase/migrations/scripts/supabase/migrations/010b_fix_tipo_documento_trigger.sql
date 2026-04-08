-- ============================================================
-- Migración 010b: Corrección de trigger en tipo_documento_config
--
-- Problema: 010_tipo_documento_config.sql usa moddatetime(updated_at)
-- que requiere la extensión pg_moddatetime no instalada en este workspace.
-- El proyecto usa update_updated_at() definida en 001_pipeline_tables.sql.
--
-- Esta migración es idempotente y segura de re-ejecutar.
-- ============================================================

DROP TRIGGER IF EXISTS trg_tipo_doc_config_updated_at ON public.tipo_documento_config;

CREATE TRIGGER trg_tipo_doc_config_updated_at
  BEFORE UPDATE ON public.tipo_documento_config
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();
