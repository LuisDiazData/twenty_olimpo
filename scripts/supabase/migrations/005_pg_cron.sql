-- ============================================================
-- Olimpo Promotoría GNP — pg_cron Scheduled Jobs
-- Migración 005: Tareas programadas
--
-- Requiere extensión pg_cron (habilitada en Supabase por defecto).
-- Habilitar en: Supabase Dashboard > Database > Extensions > pg_cron
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;  -- para llamadas HTTP desde cron

-- -------------------------------------------------------
-- JOB 1: Marcar emails atascados como error
-- Si un email lleva más de 2 horas en estado 'parsing' o
-- 'extracting', probablemente falló silenciosamente.
-- Corre cada hora.
-- -------------------------------------------------------
SELECT cron.schedule(
  'cleanup-stuck-emails',
  '0 * * * *',  -- cada hora
  $$
    UPDATE incoming_emails
    SET
      processing_status = 'error',
      error_message = 'Timeout: procesamiento atascado por más de 2 horas'
    WHERE processing_status IN ('parsing', 'extracting')
      AND updated_at < NOW() - INTERVAL '2 hours';
  $$
);

-- -------------------------------------------------------
-- JOB 2: Sincronizar contact_email_map desde Twenty CRM
-- Llama al endpoint de FastAPI que hace el sync.
-- Corre cada 6 horas.
--
-- IMPORTANTE: reemplaza FASTAPI_URL con la URL real en Railway
-- cuando esté desplegado.
-- -------------------------------------------------------
-- SELECT cron.schedule(
--   'sync-contact-email-map',
--   '0 */6 * * *',
--   $$
--     SELECT net.http_post(
--       url      := 'https://TU-FASTAPI.railway.app/sync/contact-email-map',
--       headers  := '{"Authorization": "Bearer TU-INTERNAL-TOKEN"}',
--       body     := '{}'
--     );
--   $$
-- );

-- -------------------------------------------------------
-- JOB 3: Limpiar logs de IA viejos (más de 90 días)
-- Evita que la tabla crezca indefinidamente.
-- Corre los domingos a las 3 AM.
-- -------------------------------------------------------
SELECT cron.schedule(
  'cleanup-old-ai-logs',
  '0 3 * * 0',  -- domingos 3:00 AM
  $$
    DELETE FROM ai_processing_log
    WHERE created_at < NOW() - INTERVAL '90 days';
  $$
);

-- -------------------------------------------------------
-- JOB 4: Mark overdue SLA en Twenty CRM
-- Equivalente al WF4 actual (CRON diario a las 8 AM).
-- Llama al endpoint de FastAPI /tramites/mark-overdue.
-- Corre de lunes a viernes a las 8 AM hora CDMX (UTC-6 = 14:00 UTC).
--
-- DESCOMENTA cuando FastAPI esté desplegado en Railway.
-- -------------------------------------------------------
-- SELECT cron.schedule(
--   'mark-overdue-sla',
--   '0 14 * * 1-5',  -- lun-vie 8:00 AM CDMX (14:00 UTC)
--   $$
--     SELECT net.http_post(
--       url      := 'https://TU-FASTAPI.railway.app/tramites/mark-overdue',
--       headers  := '{"Authorization": "Bearer TU-INTERNAL-TOKEN"}',
--       body     := '{}'
--     );
--   $$
-- );

-- -------------------------------------------------------
-- Consultar jobs activos
-- -------------------------------------------------------
-- SELECT * FROM cron.job;
-- SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 20;
