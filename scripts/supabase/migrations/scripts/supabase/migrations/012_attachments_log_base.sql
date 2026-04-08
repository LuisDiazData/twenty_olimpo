-- ============================================================
-- Migración 012: Tabla base attachments_log
--
-- La tabla attachments_log estaba definida en
-- scripts/attachment_processor/schema.sql fuera del sistema de
-- migraciones. Esta migración la formaliza y es 100% idempotente.
--
-- Columnas consolidadas de:
--   - schema.sql (base original)
--   - 001_thread_inline_columns.sql (es_inline, mime_type)
--   - 007_attachments_log_agente3.sql (tipo_documento, ocr_*, etc.)
--   - 009b_attachments_log_individual.sql (tramite_id, nombre, etc.)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.attachments_log (
    -- Identidad
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relación con el email fuente
    email_id                TEXT        NOT NULL,               -- Gmail Message-ID o pipeline UUID
    bucket_id               TEXT        NOT NULL DEFAULT 'tramites-docs',

    -- Contadores batch (uso legacy de log_attachment_processing)
    total_attachments       INT         DEFAULT 0,
    successful_attachments  INT         DEFAULT 0,
    file_paths              JSONB,                              -- array de paths en batch

    -- Referencia en Twenty CRM
    twenty_documento_id     TEXT,                              -- ID del documentoAdjunto en Twenty

    -- Referencia al trámite
    tramite_id              TEXT,                              -- ID de tramite (pipeline o Twenty)

    -- Datos del archivo individual
    nombre                  TEXT,                              -- nombre original del archivo
    storage_path            TEXT,                              -- ruta en Supabase Storage
    mime_type               TEXT,
    tamano_bytes            INTEGER     DEFAULT 0,

    -- Cifrado
    was_encrypted           BOOLEAN     DEFAULT FALSE,
    decryption_successful   BOOLEAN     DEFAULT TRUE,

    -- Inline images
    es_inline               BOOLEAN     DEFAULT FALSE,

    -- Clasificación IA (Agente 3)
    tipo_documento          TEXT,                              -- clasificado por LLM
    texto_extraido          TEXT,                              -- texto crudo extraído
    datos_extraidos         JSONB,                             -- nombre_titular, rfc, etc.
    metodo_extraccion       TEXT,                              -- pdf_texto/ocr_runpod/xml_texto
    ocr_completado          BOOLEAN     DEFAULT FALSE,
    clasificacion_completada BOOLEAN    DEFAULT FALSE,

    -- Error
    error_detalle           TEXT,

    -- Timestamps
    procesado_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ── Índices ────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_attachments_log_email_id
    ON public.attachments_log (email_id);

CREATE INDEX IF NOT EXISTS idx_attachments_log_tramite_id
    ON public.attachments_log (tramite_id)
    WHERE tramite_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_attachments_log_twenty_id
    ON public.attachments_log (twenty_documento_id)
    WHERE twenty_documento_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_attachments_log_clasificacion
    ON public.attachments_log (clasificacion_completada, ocr_completado)
    WHERE clasificacion_completada = FALSE OR ocr_completado = FALSE;

-- ── RLS ────────────────────────────────────────────────────────────────────────

ALTER TABLE public.attachments_log ENABLE ROW LEVEL SECURITY;

-- Service role (FastAPI) — acceso total
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'attachments_log'
          AND policyname = 'Allow server to insert logs'
    ) THEN
        CREATE POLICY "Allow server to insert logs"
            ON public.attachments_log
            FOR INSERT WITH CHECK (true);
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'attachments_log'
          AND policyname = 'Allow authenticated to read logs'
    ) THEN
        CREATE POLICY "Allow authenticated to read logs"
            ON public.attachments_log
            FOR SELECT TO authenticated USING (true);
    END IF;
END$$;

-- Service role full access
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'attachments_log'
          AND policyname = 'service_role_full_access'
    ) THEN
        CREATE POLICY "service_role_full_access"
            ON public.attachments_log
            FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END$$;

COMMENT ON TABLE public.attachments_log IS
    'Log de documentos adjuntos procesados por el pipeline de IA. '
    'Cada fila es un archivo individual o un batch. '
    'twenty_documento_id enlaza con documentoAdjunto en Twenty CRM. '
    'Fuente de verdad en Supabase — Twenty es best-effort.';
