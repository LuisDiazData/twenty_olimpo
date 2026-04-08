-- Migration 012: historial_estatus
-- Auditoría completa de cambios de estatus en trámites.
-- Cada vez que un trámite cambia de estatus (humano o agente IA), se registra aquí.
-- Inmutable: no se actualiza, solo se inserta.

CREATE TABLE IF NOT EXISTS historial_estatus (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tramite_pipeline_id  UUID        REFERENCES tramites_pipeline(id) ON DELETE SET NULL,
    twenty_tramite_id    TEXT,                        -- ID del tramite en Twenty CRM
    estatus_anterior     TEXT        NOT NULL,
    estatus_nuevo        TEXT        NOT NULL,
    fecha_cambio         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor                TEXT        NOT NULL DEFAULT 'sistema',  -- sistema|analista|gerente|ai_agent
    usuario_twenty_id    TEXT,                        -- ID del usuario en Twenty (si fue humano)
    motivo_rechazo_clave TEXT,                        -- FK lógica a motivoRechazo.clave (si aplica)
    duracion_en_estatus_horas NUMERIC(10,2),          -- Horas que duró en el estatus anterior
    notas                TEXT,                        -- Contexto adicional del cambio
    fuente               TEXT DEFAULT 'pipeline',     -- pipeline|crm_manual|webhook_gnp|cron
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_historial_estatus_tramite_pipeline
    ON historial_estatus (tramite_pipeline_id)
    WHERE tramite_pipeline_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_historial_estatus_twenty_tramite
    ON historial_estatus (twenty_tramite_id)
    WHERE twenty_tramite_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_historial_estatus_fecha
    ON historial_estatus (fecha_cambio DESC);

CREATE INDEX IF NOT EXISTS idx_historial_estatus_actor_nuevo
    ON historial_estatus (actor, estatus_nuevo, fecha_cambio DESC);

-- RLS: solo service_role puede escribir; authenticated puede leer para reportes
ALTER TABLE historial_estatus ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_historial_estatus"
    ON historial_estatus FOR ALL
    TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read_historial_estatus"
    ON historial_estatus FOR SELECT
    TO authenticated USING (true);

-- Vista: tiempo promedio en cada estatus (útil para SLA analytics)
CREATE OR REPLACE VIEW v_tiempo_promedio_por_estatus AS
SELECT
    estatus_anterior                          AS estatus,
    COUNT(*)                                  AS total_transiciones,
    ROUND(AVG(duracion_en_estatus_horas), 2)  AS promedio_horas,
    ROUND(MIN(duracion_en_estatus_horas), 2)  AS minimo_horas,
    ROUND(MAX(duracion_en_estatus_horas), 2)  AS maximo_horas,
    DATE_TRUNC('week', fecha_cambio)          AS semana
FROM historial_estatus
WHERE duracion_en_estatus_horas IS NOT NULL
GROUP BY estatus, semana
ORDER BY semana DESC, total_transiciones DESC;
