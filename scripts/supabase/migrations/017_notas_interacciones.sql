-- Migration 017: notas_interacciones
-- Registro polimórfico de interacciones: correos, WhatsApp, llamadas, notas internas.
-- Cubre tanto tramites como agentes como entidad de referencia.
-- El campo resumen_ia lo llena Agente 1 (claude) después de procesar cada email/mensaje.

CREATE TABLE IF NOT EXISTS notas_interacciones (
    id                  UUID    PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Entidad a la que pertenece (polimórfico: tramite o agente)
    entidad_tipo        TEXT    NOT NULL
                        CONSTRAINT chk_ni_entidad CHECK (entidad_tipo IN ('tramite','agente')),
    entidad_twenty_id   TEXT    NOT NULL,       -- ID en Twenty CRM

    -- Tipo y canal
    tipo                TEXT    NOT NULL
                        CONSTRAINT chk_ni_tipo CHECK (tipo IN ('Email','WhatsApp','Nota_Interna','Llamada')),
    canal_origen        TEXT    DEFAULT 'CORREO'
                        CONSTRAINT chk_ni_canal CHECK (canal_origen IN ('CORREO','WHATSAPP','MANUAL')),

    -- Contenido
    asunto              TEXT,                   -- Asunto del correo (si aplica)
    contenido           TEXT,                   -- Cuerpo completo (truncado si muy largo)
    resumen_ia          TEXT,                   -- Resumen de 2-3 oraciones generado por IA
    sentimiento         TEXT
                        CONSTRAINT chk_ni_sentimiento CHECK (sentimiento IN ('Positivo','Neutro','Negativo')),

    -- Threading
    hilo_id             TEXT,                   -- Gmail Thread-ID o WhatsApp conversation ID
    gmail_message_id    TEXT,                   -- Para trazabilidad a incoming_emails
    incoming_email_id   UUID REFERENCES incoming_emails(id) ON DELETE SET NULL,

    -- Actor
    autor_email         TEXT,                   -- Quién escribió (agente, analista, sistema)
    autor_twenty_id     TEXT,                   -- ID del WorkspaceMember si fue interno

    -- Urgencia detectada por IA
    urgencia_detectada  BOOLEAN DEFAULT FALSE,
    etiquetas           TEXT[],                 -- ["reclamo","urgente","documentos"] clasificadas por IA

    -- Referencia cruzada con trámite en pipeline
    tramite_pipeline_id UUID REFERENCES tramites_pipeline(id) ON DELETE SET NULL,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Índices principales
CREATE INDEX IF NOT EXISTS idx_notas_entidad
    ON notas_interacciones (entidad_tipo, entidad_twenty_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notas_hilo
    ON notas_interacciones (hilo_id)
    WHERE hilo_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_notas_urgencia
    ON notas_interacciones (urgencia_detectada, created_at DESC)
    WHERE urgencia_detectada = TRUE;

CREATE INDEX IF NOT EXISTS idx_notas_tipo
    ON notas_interacciones (tipo, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notas_email_id
    ON notas_interacciones (incoming_email_id)
    WHERE incoming_email_id IS NOT NULL;

-- Trigger updated_at
CREATE OR REPLACE FUNCTION update_updated_at_notas()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

CREATE TRIGGER trg_notas_updated_at
    BEFORE UPDATE ON notas_interacciones
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_notas();

-- RLS
ALTER TABLE notas_interacciones ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_notas"
    ON notas_interacciones FOR ALL
    TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read_notas"
    ON notas_interacciones FOR SELECT
    TO authenticated USING (true);

-- Vista: últimas interacciones urgentes sin atender
CREATE OR REPLACE VIEW v_interacciones_urgentes AS
SELECT
    ni.id,
    ni.entidad_tipo,
    ni.entidad_twenty_id,
    ni.tipo,
    ni.asunto,
    ni.resumen_ia,
    ni.sentimiento,
    ni.autor_email,
    ni.created_at,
    ni.etiquetas
FROM notas_interacciones ni
WHERE ni.urgencia_detectada = TRUE
  AND ni.created_at > NOW() - INTERVAL '72 hours'
ORDER BY ni.created_at DESC;
