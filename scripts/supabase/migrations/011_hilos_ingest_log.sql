-- ============================================================
-- Olimpo Promotoría GNP — Supabase Migration 011
-- Tabla de auditoría para el pipeline de ingesta de emails
-- y matching de hilos de conversación → trámites.
--
-- Aplicar en: Supabase Dashboard > SQL Editor
-- ============================================================

-- -------------------------------------------------------
-- 1. HILOS_INGEST_LOG
-- Registro inmutable de cada email procesado por el endpoint
-- POST /api/v1/email/ingest de FastAPI.
-- Fuente de verdad para debugging, auditoría y métricas.
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS hilos_ingest_log (
  id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,

  -- Identificadores del email
  message_id          TEXT        NOT NULL,        -- Gmail Message-ID
  thread_id           TEXT        NOT NULL,        -- Gmail threadId
  from_email          TEXT        NOT NULL,
  subject             TEXT,
  received_at         TIMESTAMPTZ,

  -- Resultado del matching
  match_strategy      TEXT        NOT NULL,        -- ver enum abajo
  match_confianza     INTEGER     DEFAULT 0        -- 0-100
                      CHECK (match_confianza BETWEEN 0 AND 100),

  -- Referencias en Twenty CRM
  tramite_twenty_id   TEXT,                        -- null si no se pudo identificar
  agente_twenty_id    TEXT,                        -- null si remitente no es agente conocido
  hilo_twenty_id      TEXT,                        -- UUID del HiloConversacion creado/actualizado

  -- Flags de estado
  requiere_accion     BOOLEAN     NOT NULL DEFAULT FALSE,
  urgencia_detectada  BOOLEAN     NOT NULL DEFAULT FALSE,

  -- Motivo cuando no hay match
  motivo_sin_match    TEXT,

  -- Contexto
  canal_origen        TEXT        DEFAULT 'CORREO'
                      CHECK (canal_origen IN ('CORREO', 'WHATSAPP')),
  tiene_adjuntos      BOOLEAN     DEFAULT FALSE,

  created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE hilos_ingest_log IS
  'Log de auditoría del pipeline de matching email → HiloConversacion → Trámite. '
  'Registro inmutable — no se actualiza, solo se inserta. '
  'Cada fila representa un email procesado por el endpoint /api/v1/email/ingest.';

COMMENT ON COLUMN hilos_ingest_log.match_strategy IS
  'Estrategia que produjo el match: '
  'thread_id_known | reply_headers | folio_regex | poliza_regex | '
  'agente_tramites:agente_single_tramite | agente_tramites:llm_disambig | '
  'agente_tramites:llm_disambig_low_confidence | agente_tramites:agente_sin_tramites_activos | '
  'agente_tramites:agente_not_found | manual_queue';

-- -------------------------------------------------------
-- 2. Índices de consulta frecuente
-- -------------------------------------------------------

-- Buscar logs por thread (para ver historial de un hilo)
CREATE INDEX IF NOT EXISTS idx_hilos_ingest_log_thread_id
  ON hilos_ingest_log (thread_id);

-- Buscar logs por tramite vinculado
CREATE INDEX IF NOT EXISTS idx_hilos_ingest_log_tramite
  ON hilos_ingest_log (tramite_twenty_id)
  WHERE tramite_twenty_id IS NOT NULL;

-- Cola de revisión manual pendiente
CREATE INDEX IF NOT EXISTS idx_hilos_ingest_log_requiere_accion
  ON hilos_ingest_log (requiere_accion, created_at DESC)
  WHERE requiere_accion = TRUE;

-- Alertas de urgencia
CREATE INDEX IF NOT EXISTS idx_hilos_ingest_log_urgencia
  ON hilos_ingest_log (urgencia_detectada, created_at DESC)
  WHERE urgencia_detectada = TRUE;

-- Búsqueda por remitente
CREATE INDEX IF NOT EXISTS idx_hilos_ingest_log_from_email
  ON hilos_ingest_log (from_email, created_at DESC);

-- -------------------------------------------------------
-- 3. Vista: bandeja de revisión manual
-- Útil para el analista que clasifica los hilos sin match.
-- -------------------------------------------------------
CREATE OR REPLACE VIEW v_bandeja_sin_clasificar AS
SELECT
  h.id,
  h.message_id,
  h.thread_id,
  h.from_email,
  h.subject,
  h.received_at,
  h.match_strategy,
  h.match_confianza,
  h.agente_twenty_id,
  h.hilo_twenty_id,
  h.urgencia_detectada,
  h.motivo_sin_match,
  h.canal_origen,
  h.tiene_adjuntos,
  h.created_at
FROM hilos_ingest_log h
WHERE h.requiere_accion = TRUE
  AND h.tramite_twenty_id IS NULL
ORDER BY
  h.urgencia_detectada DESC,   -- urgentes primero
  h.created_at ASC             -- más antiguos primero (FIFO)
;

COMMENT ON VIEW v_bandeja_sin_clasificar IS
  'Emails que llegaron pero no pudieron vincularse automáticamente a un trámite. '
  'Pendientes de clasificación manual por el analista. '
  'Ordenados: urgentes primero, luego por antigüedad (FIFO).';

-- -------------------------------------------------------
-- 4. Vista: métricas diarias de matching
-- Para el dashboard del director de operaciones.
-- -------------------------------------------------------
CREATE OR REPLACE VIEW v_metricas_matching_diario AS
SELECT
  DATE(created_at AT TIME ZONE 'America/Mexico_City') AS fecha,
  COUNT(*)                                             AS total_emails,
  COUNT(*) FILTER (WHERE tramite_twenty_id IS NOT NULL) AS con_match,
  COUNT(*) FILTER (WHERE requiere_accion = TRUE)        AS sin_match,
  COUNT(*) FILTER (WHERE urgencia_detectada = TRUE)     AS urgentes,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE tramite_twenty_id IS NOT NULL) / NULLIF(COUNT(*), 0),
    1
  )                                                    AS pct_auto_match,
  COUNT(*) FILTER (WHERE match_strategy = 'thread_id_known')        AS via_thread,
  COUNT(*) FILTER (WHERE match_strategy = 'reply_headers')          AS via_reply,
  COUNT(*) FILTER (WHERE match_strategy = 'folio_regex')            AS via_folio,
  COUNT(*) FILTER (WHERE match_strategy = 'poliza_regex')           AS via_poliza,
  COUNT(*) FILTER (WHERE match_strategy LIKE 'agente_tramites:%')   AS via_agente,
  AVG(match_confianza) FILTER (WHERE tramite_twenty_id IS NOT NULL) AS confianza_promedio
FROM hilos_ingest_log
GROUP BY 1
ORDER BY 1 DESC
;

COMMENT ON VIEW v_metricas_matching_diario IS
  'Métricas diarias del pipeline de matching de emails. '
  'pct_auto_match es la tasa de clasificación automática (meta: >85%).';

-- -------------------------------------------------------
-- 5. RLS — solo el service role puede escribir,
--    los analistas pueden leer
-- -------------------------------------------------------
ALTER TABLE hilos_ingest_log ENABLE ROW LEVEL SECURITY;

-- Service role (FastAPI) tiene acceso total
CREATE POLICY "service_role_full_access" ON hilos_ingest_log
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

-- Usuarios autenticados solo lectura
CREATE POLICY "authenticated_read" ON hilos_ingest_log
  FOR SELECT TO authenticated USING (TRUE);
