-- Migration 016: productos
-- Catálogo de productos de seguros GNP que comercializa la promotoría.
-- Referenciado por tramites_pipeline, reglas_negocio y el objeto Producto en Twenty CRM.
-- El campo twenty_producto_id enlaza cada fila con su contraparte en Twenty.

CREATE TABLE IF NOT EXISTS productos (
    id                  UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    clave               TEXT    NOT NULL UNIQUE,        -- Ej: "VIDA_IND_TOTAL", "GMM_FLEX"
    nombre              TEXT    NOT NULL,               -- Nombre comercial GNP
    ramo                TEXT    NOT NULL
                        CONSTRAINT chk_prod_ramo CHECK (ramo IN ('VIDA','GMM','AUTOS','PYME','DANOS')),
    tipo_tramite_aplica TEXT[]  NOT NULL DEFAULT '{}',  -- ["NUEVA_POLIZA","RENOVACION"]
    aseguradora         TEXT    NOT NULL DEFAULT 'GNP',
    descripcion         TEXT,
    vigencia_meses      INTEGER,                        -- Duración estándar de la póliza
    prima_referencia    NUMERIC(12,2),                  -- Prima anual de referencia (orientativo)
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    twenty_producto_id  TEXT,                           -- ID del objeto Producto en Twenty CRM
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_productos_ramo
    ON productos (ramo)
    WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_productos_twenty_id
    ON productos (twenty_producto_id)
    WHERE twenty_producto_id IS NOT NULL;

-- Trigger updated_at
CREATE OR REPLACE FUNCTION update_updated_at_productos()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

CREATE TRIGGER trg_productos_updated_at
    BEFORE UPDATE ON productos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_productos();

-- RLS
ALTER TABLE productos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_productos"
    ON productos FOR ALL
    TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read_productos"
    ON productos FOR SELECT
    TO authenticated USING (true);

-- Semilla: productos base por ramo
INSERT INTO productos (clave, nombre, ramo, tipo_tramite_aplica, vigencia_meses, descripcion) VALUES
-- Vida
('VIDA_IND_TOTAL',   'Vida Individual Total',        'VIDA',  '{"NUEVA_POLIZA","RENOVACION","ENDOSO","SINIESTRO","CANCELACION"}', 12, 'Seguro de vida individual con cobertura total'),
('VIDA_COLECTIVO',   'Vida Colectivo Empresarial',   'VIDA',  '{"NUEVA_POLIZA","RENOVACION","ENDOSO","SINIESTRO","CANCELACION"}', 12, 'Vida colectivo para grupos empresariales'),
('VIDA_HIPOTECARIO', 'Vida Saldo Deudor Hipotecario','VIDA',  '{"NUEVA_POLIZA","CANCELACION"}',                                   NULL,'Vida ligado a crédito hipotecario'),
-- GMM
('GMM_FLEX',         'Gastos Médicos Mayores Flex',  'GMM',   '{"NUEVA_POLIZA","RENOVACION","ENDOSO","SINIESTRO","CANCELACION"}', 12, 'GMM individual con red amplia'),
('GMM_EMPRESARIAL',  'GMM Grupo Empresarial',        'GMM',   '{"NUEVA_POLIZA","RENOVACION","ENDOSO","SINIESTRO","CANCELACION"}', 12, 'GMM para grupos empresa 5+ vidas'),
('GMM_NACIONAL',     'GMM Nacional Plus',            'GMM',   '{"NUEVA_POLIZA","RENOVACION","SINIESTRO"}',                        12, 'GMM con cobertura nacional y reembolso'),
-- Autos
('AUTOS_AMPLIA',     'Auto Amplia',                  'AUTOS', '{"NUEVA_POLIZA","RENOVACION","ENDOSO","SINIESTRO","CANCELACION"}', 12, 'Cobertura amplia para autos'),
('AUTOS_RC',         'Auto Responsabilidad Civil',   'AUTOS', '{"NUEVA_POLIZA","RENOVACION","CANCELACION"}',                      12, 'Solo responsabilidad civil'),
('AUTOS_FLOTILLA',   'Auto Flotilla Empresarial',    'AUTOS', '{"NUEVA_POLIZA","RENOVACION","ENDOSO","SINIESTRO"}',               12, 'Flotillas de 5+ vehículos'),
-- Pyme
('PYME_PAQUETE',     'Pyme Paquete Integral',        'PYME',  '{"NUEVA_POLIZA","RENOVACION","COTIZACION_PYME","ENDOSO"}',         12, 'Paquete multirriesgo para PyME'),
('PYME_RC',          'Pyme Responsabilidad Civil',   'PYME',  '{"NUEVA_POLIZA","RENOVACION","COTIZACION_PYME"}',                  12, 'RC profesional y general para PyME'),
-- Daños
('DANOS_HOGAR',      'Daños Hogar',                  'DANOS', '{"NUEVA_POLIZA","RENOVACION","SINIESTRO","ENDOSO"}',               12, 'Seguro de casa habitación'),
('DANOS_COMERCIO',   'Daños Comercio',               'DANOS', '{"NUEVA_POLIZA","RENOVACION","SINIESTRO","COTIZACION_PYME"}',      12, 'Seguro de local comercial y contenidos')
ON CONFLICT (clave) DO NOTHING;
