-- ============================================================
-- Olimpo Promotoría GNP — Migración 000
-- CREATE TABLE tramites_pipeline (tabla central del pipeline)
-- Reconstruida desde la base de datos de producción (2026-04-02)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.tramites_pipeline (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    folio                 TEXT,
    ramo                  TEXT,
    tipo_tramite          TEXT,
    status                TEXT NOT NULL DEFAULT 'procesando',
    canal_ingreso         TEXT DEFAULT 'Correo',
    nombre_agente         TEXT,
    email_agente          TEXT,
    clave_agente          TEXT,
    nombre_asegurado      TEXT,
    numero_poliza         TEXT,
    monto                 NUMERIC,
    prioridad             TEXT,
    resumen_ia            TEXT,
    accion_requerida      TEXT,
    correo_asunto         TEXT,
    correo_remitente      TEXT,
    tiene_adjuntos        BOOLEAN DEFAULT FALSE,
    fecha_ingreso         TIMESTAMPTZ,
    thread_id             TEXT,
    message_id            TEXT,
    metadata_ia           JSONB,
    twenty_tramite_id     TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW(),
    -- Agente 1: comprensión
    agente_cua            TEXT,
    resumen               TEXT,
    confianza_global      NUMERIC,
    es_duplicado_posible  BOOLEAN DEFAULT FALSE,
    tramite_duplicado_ref TEXT,
    campos_confianza      JSONB,
    error_detalle         TEXT,
    -- Agente 4: asignación
    agente_twenty_id      TEXT,
    analista_twenty_id    TEXT,
    motivo_revision       TEXT,
    asignado_at           TIMESTAMPTZ
);

-- Índices para búsqueda de hilos y deduplicación
CREATE INDEX IF NOT EXISTS idx_tramites_thread_id
    ON tramites_pipeline(thread_id)
    WHERE thread_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tramites_status
    ON tramites_pipeline(status);

CREATE INDEX IF NOT EXISTS idx_tramites_numero_poliza
    ON tramites_pipeline(numero_poliza)
    WHERE numero_poliza IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tramites_remitente
    ON tramites_pipeline(correo_remitente);

CREATE INDEX IF NOT EXISTS idx_tramites_created_at
    ON tramites_pipeline(created_at DESC);

-- RLS: solo service_role puede operar (FastAPI + n8n)
ALTER TABLE public.tramites_pipeline ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON public.tramites_pipeline
    USING (true)
    WITH CHECK (true);

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tramites_pipeline_updated_at
    BEFORE UPDATE ON public.tramites_pipeline
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
