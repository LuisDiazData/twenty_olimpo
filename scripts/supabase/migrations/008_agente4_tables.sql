-- ============================================================
-- Olimpo Promotoría GNP — Supabase Migration 008
-- Agente 4: tablas y columnas para identificación y asignación
-- ============================================================

-- Tabla de cobertura por vacaciones / sustituciones
CREATE TABLE IF NOT EXISTS cobertura_analistas (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  analista_twenty_id  TEXT NOT NULL,
  sustituto_twenty_id TEXT NOT NULL,
  ramo                TEXT NOT NULL,
  fecha_inicio        DATE NOT NULL,
  fecha_fin           DATE NOT NULL,
  activo              BOOLEAN DEFAULT TRUE,
  creado_por          TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cobertura_analista
  ON cobertura_analistas(analista_twenty_id) WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_cobertura_fechas
  ON cobertura_analistas(fecha_inicio, fecha_fin) WHERE activo = TRUE;

COMMENT ON TABLE cobertura_analistas IS 'Sustituciones activas por vacaciones o ausencia. Agente 4 lo consulta para asignar al sustituto cuando el titular no está disponible.';

-- Tabla de auditoría de cada asignación (automatica, manual, cobertura, reasignacion)
CREATE TABLE IF NOT EXISTS historial_asignaciones (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tramite_pipeline_id UUID REFERENCES tramites_pipeline(id),
  twenty_tramite_id   TEXT,
  analista_twenty_id  TEXT NOT NULL,
  agente_twenty_id    TEXT,
  tipo_asignacion     TEXT NOT NULL,
  -- valores: 'automatica' | 'manual' | 'reasignacion' | 'cobertura'
  motivo              TEXT,
  asignado_por        TEXT DEFAULT 'sistema',
  ramo                TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE historial_asignaciones IS 'Auditoría de todas las asignaciones: quién asignó, qué tipo, cuándo.';

-- Columnas adicionales en tramites_pipeline para Agente 4
ALTER TABLE tramites_pipeline
  ADD COLUMN IF NOT EXISTS agente_twenty_id    TEXT,
  ADD COLUMN IF NOT EXISTS analista_twenty_id  TEXT,
  ADD COLUMN IF NOT EXISTS motivo_revision     TEXT,
  ADD COLUMN IF NOT EXISTS asignado_at         TIMESTAMPTZ;

COMMENT ON COLUMN tramites_pipeline.agente_twenty_id   IS 'ID del Company en Twenty que representa al agente identificado';
COMMENT ON COLUMN tramites_pipeline.analista_twenty_id IS 'ID del WorkspaceMember en Twenty asignado como analista';
COMMENT ON COLUMN tramites_pipeline.motivo_revision    IS 'Motivo cuando el trámite va a revisión manual';
COMMENT ON COLUMN tramites_pipeline.asignado_at        IS 'Timestamp UTC en que se completó la asignación';
