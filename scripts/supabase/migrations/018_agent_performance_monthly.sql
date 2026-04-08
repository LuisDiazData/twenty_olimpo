-- Migration 018: agent_performance_monthly
-- Snapshot mensual de desempeño por agente externo.
-- Calculado cada inicio de mes por un CRON; sincronizado a Twenty CRM.
-- Base para cálculo de bonos y rankeo de agentes.

CREATE TABLE IF NOT EXISTS agent_performance_monthly (
    id                              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    agente_cua                      TEXT    NOT NULL,   -- CUA del agente (FK lógica)
    agente_twenty_id                TEXT,               -- ID en Twenty CRM
    mes_anio                        TEXT    NOT NULL,   -- Formato "04-2026"

    -- Volumen
    tramites_totales                INTEGER NOT NULL DEFAULT 0,
    tramites_resueltos              INTEGER NOT NULL DEFAULT 0,
    tramites_rechazados             INTEGER NOT NULL DEFAULT 0,
    tramites_cancelados             INTEGER NOT NULL DEFAULT 0,

    -- Calidad documental
    first_pass_yield                NUMERIC(5,2),       -- % tramites que pasan sin rechazo en 1er intento
    promedio_docs_faltantes         NUMERIC(5,2),       -- Promedio de documentos que falta por trámite

    -- Tiempos
    tiempo_promedio_resolucion_horas NUMERIC(10,2),
    tramites_vencidos_sla           INTEGER DEFAULT 0,
    tasa_cumplimiento_sla           NUMERIC(5,2),       -- % tramites dentro de SLA

    -- Económico
    prima_emitida                   NUMERIC(15,2) DEFAULT 0,  -- Suma de montos de tramites resueltos
    bono_proyectado                 NUMERIC(15,2) DEFAULT 0,  -- Calculado según esquema de bono

    -- Desglose por ramo (JSONB para no multiplicar columnas)
    desglose_ramo                   JSONB,  -- {VIDA:{total:5,resueltos:4}, GMM:{...}}

    -- Referencia a Twenty CRM
    twenty_snapshot_id              TEXT,               -- ID del objeto AgentPerformanceMonthly en Twenty

    calculado_at                    TIMESTAMPTZ DEFAULT NOW(),
    es_vigente                      BOOLEAN NOT NULL DEFAULT TRUE,

    UNIQUE (agente_cua, mes_anio)
);

CREATE INDEX IF NOT EXISTS idx_apm_agente_cua
    ON agent_performance_monthly (agente_cua, mes_anio DESC);

CREATE INDEX IF NOT EXISTS idx_apm_mes_anio
    ON agent_performance_monthly (mes_anio, prima_emitida DESC)
    WHERE es_vigente = TRUE;

CREATE INDEX IF NOT EXISTS idx_apm_twenty_id
    ON agent_performance_monthly (twenty_snapshot_id)
    WHERE twenty_snapshot_id IS NOT NULL;

-- RLS
ALTER TABLE agent_performance_monthly ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_apm"
    ON agent_performance_monthly FOR ALL
    TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read_apm"
    ON agent_performance_monthly FOR SELECT
    TO authenticated USING (true);

-- Vista: ranking de agentes del mes actual
CREATE OR REPLACE VIEW v_ranking_agentes_mes_actual AS
SELECT
    agente_cua,
    agente_twenty_id,
    mes_anio,
    tramites_totales,
    tramites_resueltos,
    first_pass_yield,
    prima_emitida,
    tasa_cumplimiento_sla,
    bono_proyectado,
    RANK() OVER (ORDER BY prima_emitida DESC NULLS LAST) AS ranking_prima,
    RANK() OVER (ORDER BY first_pass_yield DESC NULLS LAST) AS ranking_calidad
FROM agent_performance_monthly
WHERE mes_anio = TO_CHAR(DATE_TRUNC('month', NOW()), 'MM-YYYY')
  AND es_vigente = TRUE
ORDER BY prima_emitida DESC NULLS LAST;
