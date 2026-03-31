-- ============================================================
-- Olimpo Promotoría GNP — Supabase Migration 009
-- pipeline_logs: tabla de errores y auditoría del pipeline v3
-- ============================================================

-- Tabla de logs del pipeline (errores, advertencias, info por etapa)
CREATE TABLE IF NOT EXISTS pipeline_logs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tramite_id    UUID REFERENCES tramites_pipeline(id) ON DELETE SET NULL,
  etapa         TEXT NOT NULL,
  -- valores: 'crear_tramite' | 'adjuntos' | 'agente1' | 'agente3' | 'agente4' | 'acuse' | 'reply'
  nivel         TEXT NOT NULL DEFAULT 'error',
  -- valores: 'info' | 'warning' | 'error'
  error_message TEXT,
  contexto      JSONB,
  -- datos adicionales: email_id, remitente, http_status, etc.
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_logs_tramite
  ON pipeline_logs(tramite_id) WHERE tramite_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pipeline_logs_etapa
  ON pipeline_logs(etapa, nivel);

CREATE INDEX IF NOT EXISTS idx_pipeline_logs_created
  ON pipeline_logs(created_at DESC);

COMMENT ON TABLE pipeline_logs IS 'Registro de errores y eventos de auditoría del pipeline de trámites v3. n8n escribe aquí cuando falla un agente o hay una excepción no manejada.';
COMMENT ON COLUMN pipeline_logs.etapa IS 'Etapa del pipeline donde ocurrió el evento: crear_tramite, adjuntos, agente1, agente3, agente4, acuse, reply';
COMMENT ON COLUMN pipeline_logs.nivel IS 'Nivel del log: info, warning, error';
COMMENT ON COLUMN pipeline_logs.contexto IS 'JSON con datos adicionales: email_id, remitente, http_status_code, response_body (truncado), etc.';
