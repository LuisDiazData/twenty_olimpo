-- Migration 015: kpi_snapshots_cache
-- Caché de métricas calculadas desde Supabase y sincronizadas a Twenty CRM.
-- Los directivos consultan esta tabla a través del frontend/Twenty para ver dashboards.
-- Se recalcula periódicamente (CRON diario/semanal/mensual).

CREATE TABLE IF NOT EXISTS kpi_snapshots_cache (
    id                      UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    periodo_inicio          DATE    NOT NULL,
    periodo_fin             DATE    NOT NULL,
    granularidad            TEXT    NOT NULL
                            CONSTRAINT chk_kpi_granularidad CHECK (granularidad IN ('DIARIO','SEMANAL','MENSUAL')),

    -- Métricas operativas generales
    total_tramites          INTEGER DEFAULT 0,
    tramites_resueltos      INTEGER DEFAULT 0,
    tramites_pendientes     INTEGER DEFAULT 0,
    tramites_vencidos_sla   INTEGER DEFAULT 0,
    tramites_en_riesgo_sla  INTEGER DEFAULT 0,
    tiempo_promedio_horas   NUMERIC(10,2),

    -- Métricas de pipeline IA
    tasa_auto_matching_pct  NUMERIC(5,2),  -- % emails asignados automáticamente (meta: >85%)
    tasa_exito_ocr_pct      NUMERIC(5,2),  -- % documentos con OCR exitoso
    tasa_primera_vez_pct    NUMERIC(5,2),  -- First Pass Yield global

    -- Desgloses en JSONB para no proliferar columnas
    desglose_ramo           JSONB,  -- {VIDA: {total:45, resueltos:40, vencidos:2}, ...}
    desglose_estatus        JSONB,  -- {RECIBIDO:5, EN_REVISION:10, ...}
    desglose_analista       JSONB,  -- {analista_id: {total:20, resueltos:18}, ...}
    metricas_json           JSONB,  -- Métricas adicionales / extensibles

    -- Referencia al objeto Twenty CRM correspondiente (para no duplicar en UI)
    twenty_snapshot_id      TEXT,

    calculado_at            TIMESTAMPTZ DEFAULT NOW(),
    es_vigente              BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE NULLS NOT DISTINCT (periodo_inicio, periodo_fin, granularidad)
);

CREATE INDEX IF NOT EXISTS idx_kpi_cache_periodo
    ON kpi_snapshots_cache (periodo_inicio DESC, granularidad)
    WHERE es_vigente = TRUE;

CREATE INDEX IF NOT EXISTS idx_kpi_cache_twenty_id
    ON kpi_snapshots_cache (twenty_snapshot_id)
    WHERE twenty_snapshot_id IS NOT NULL;

-- RLS
ALTER TABLE kpi_snapshots_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_kpi"
    ON kpi_snapshots_cache FOR ALL
    TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read_kpi"
    ON kpi_snapshots_cache FOR SELECT
    TO authenticated USING (true);

-- Vista: snapshot vigente más reciente por granularidad
CREATE OR REPLACE VIEW v_kpi_vigentes AS
SELECT DISTINCT ON (granularidad)
    id, periodo_inicio, periodo_fin, granularidad,
    total_tramites, tramites_resueltos, tramites_pendientes, tramites_vencidos_sla,
    tiempo_promedio_horas, tasa_auto_matching_pct, tasa_primera_vez_pct,
    desglose_ramo, desglose_estatus, calculado_at
FROM kpi_snapshots_cache
WHERE es_vigente = TRUE
ORDER BY granularidad, periodo_inicio DESC;
