-- ============================================================
-- Migración 015: Cache de KPI Snapshots
--
-- Supabase computa los KPIs; Twenty los muestra.
-- El campo twenty_snapshot_id enlaza con el objeto kpiSnapshot en Twenty CRM.
-- Diseño: solo se inserta, nunca se actualiza el mismo período — si se
-- recalcula, se marca es_vigente=FALSE el anterior y se inserta uno nuevo.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.kpi_snapshots_cache (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Período del snapshot
    periodo_inicio              DATE        NOT NULL,
    periodo_fin                 DATE        NOT NULL,
    granularidad                TEXT        NOT NULL
                                CHECK (granularidad IN ('DIARIO', 'SEMANAL', 'MENSUAL')),

    -- Métricas principales
    total_tramites              INTEGER     NOT NULL DEFAULT 0,
    tramites_resueltos          INTEGER     NOT NULL DEFAULT 0,
    tramites_pendientes         INTEGER     NOT NULL DEFAULT 0,
    tramites_vencidos_sla       INTEGER     NOT NULL DEFAULT 0,
    tiempo_promedio_horas       NUMERIC(10,2),
    tasa_auto_matching_pct      NUMERIC(5,2),
    tasa_exito_ocr_pct          NUMERIC(5,2),

    -- Desglose por ramo (JSONB para flexibilidad)
    -- Ej: {"VIDA": {"total": 45, "resueltos": 40}, "GMM": {...}}
    desglose_ramo               JSONB,

    -- Desglose por estatus
    -- Ej: {"RECIBIDO": 5, "EN_REVISION": 10, "DETENIDO": 3}
    desglose_estatus            JSONB,

    -- JSON extendido para métricas adicionales y detalles
    metricas_json               JSONB,

    -- Referencia en Twenty CRM
    twenty_snapshot_id          TEXT,

    -- Metadatos del cálculo
    calculado_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    es_vigente                  BOOLEAN     NOT NULL DEFAULT TRUE,

    -- Unicidad: un snapshot vigente por período + granularidad
    CONSTRAINT uq_kpi_periodo_vigente
        UNIQUE NULLS NOT DISTINCT (periodo_inicio, periodo_fin, granularidad)
        DEFERRABLE INITIALLY DEFERRED
);

-- ── Índices ────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_kpi_cache_periodo
    ON public.kpi_snapshots_cache (periodo_inicio DESC, granularidad)
    WHERE es_vigente = TRUE;

CREATE INDEX IF NOT EXISTS idx_kpi_cache_twenty_id
    ON public.kpi_snapshots_cache (twenty_snapshot_id)
    WHERE twenty_snapshot_id IS NOT NULL;

-- ── RLS ────────────────────────────────────────────────────────────────────────

ALTER TABLE public.kpi_snapshots_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_kpi" ON public.kpi_snapshots_cache
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read_kpi" ON public.kpi_snapshots_cache
    FOR SELECT TO authenticated USING (true);

-- ── Vista: último snapshot por granularidad ───────────────────────────────────

CREATE OR REPLACE VIEW public.v_kpi_vigentes AS
SELECT *
FROM public.kpi_snapshots_cache
WHERE es_vigente = TRUE
ORDER BY granularidad, periodo_inicio DESC;

COMMENT ON TABLE public.kpi_snapshots_cache IS
    'Cache de KPI snapshots calculados. Supabase computa, Twenty muestra. '
    'twenty_snapshot_id enlaza con el objeto kpiSnapshot en Twenty CRM. '
    'Un registro por período + granularidad. Marcar es_vigente=FALSE al recalcular.';
