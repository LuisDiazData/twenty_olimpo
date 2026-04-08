-- ============================================================
-- Olimpo Promotoría GNP — Supabase Migration 010
-- Tabla de configuración de tipos de documento
--
-- Propósito: mapeo administrable entre etiquetas del agente IA
-- y claves del catálogo catalogoTipoDocumento en Twenty CRM.
-- No requiere redeploy del servicio para agregar/cambiar tipos.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.tipo_documento_config (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  etiqueta_ia      TEXT        NOT NULL UNIQUE,  -- lo que devuelve el LLM, ej: "INE/IFE"
  clave_twenty     TEXT        NOT NULL,          -- clave en Twenty, ej: "INE"
  nombre           TEXT        NOT NULL,          -- nombre legible para UI
  ramo             TEXT,                          -- NULL = todos; "VIDA", "GMM", "AUTOS", etc.
  es_obligatorio   BOOLEAN     NOT NULL DEFAULT TRUE,
  activo           BOOLEAN     NOT NULL DEFAULT TRUE,
  notas            TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger para updated_at automático
CREATE OR REPLACE TRIGGER trg_tipo_doc_config_updated_at
  BEFORE UPDATE ON public.tipo_documento_config
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

-- RLS: service_role escribe; authenticated lee
ALTER TABLE public.tipo_documento_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tipo_doc_service_all"
  ON public.tipo_documento_config
  FOR ALL TO service_role
  USING (true) WITH CHECK (true);

CREATE POLICY "tipo_doc_authenticated_read"
  ON public.tipo_documento_config
  FOR SELECT TO authenticated
  USING (true);

COMMENT ON TABLE public.tipo_documento_config
  IS 'Mapeo administrable: etiqueta_ia (LLM) → clave_twenty (catalogoTipoDocumento). Editar aquí para agregar tipos sin redeploy.';

-- ── Datos iniciales (13 tipos base del dominio GNP) ──────────────────────────

INSERT INTO public.tipo_documento_config
  (etiqueta_ia, clave_twenty, nombre, ramo, es_obligatorio, activo, notas)
VALUES
  ('INE/IFE',                   'INE',        'INE / IFE',                    NULL,   TRUE,  TRUE, 'Ambas caras, vigente'),
  ('Póliza GNP',                'POL_GNP',    'Póliza GNP',                   NULL,   TRUE,  TRUE, NULL),
  ('Solicitud de seguro',       'SOL_GNP',    'Solicitud de seguro GNP',       NULL,   TRUE,  TRUE, 'Debe estar firmada'),
  ('Comprobante de domicilio',  'COMP_DOM',   'Comprobante de domicilio',      NULL,   TRUE,  TRUE, 'No mayor a 3 meses'),
  ('Comprobante de pago',       'COMP_PAGO',  'Comprobante de pago',           NULL,   FALSE, TRUE, NULL),
  ('CFDI/Factura',              'CFDI',       'CFDI / Factura',                NULL,   FALSE, TRUE, NULL),
  ('Acta de nacimiento',        'ACTA_NAC',   'Acta de nacimiento',            'VIDA', FALSE, TRUE, NULL),
  ('Carta instrucción',         'CARTA_INS',  'Carta de instrucción',          NULL,   TRUE,  TRUE, NULL),
  ('Pasaporte',                 'PASAPORTE',  'Pasaporte',                     NULL,   FALSE, TRUE, 'Vigente'),
  ('Formato GNP',               'FMT_GNP',    'Formato GNP',                   NULL,   FALSE, TRUE, NULL),
  ('Carnet de salud',           'CARNET',     'Carnet de salud',               'GMM',  FALSE, TRUE, NULL),
  ('Estado de cuenta',          'EDO_CUENTA', 'Estado de cuenta',              NULL,   FALSE, TRUE, NULL),
  ('Otro',                      'OTRO',       'Otro',                          NULL,   FALSE, TRUE, 'Revisión manual requerida')
ON CONFLICT (etiqueta_ia) DO NOTHING;
