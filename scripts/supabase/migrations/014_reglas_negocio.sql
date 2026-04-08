-- Migration 014: reglas_negocio
-- "Cerebro" de configuración que los agentes de IA consultan para validar documentos y calcular SLAs.
-- Una regla = (tipo_tramite × ramo × [producto_opcional]) → documentos + SLA.
-- La función get_regla_negocio() devuelve la regla más específica disponible.

CREATE TABLE IF NOT EXISTS reglas_negocio (
    id                    UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_tramite          TEXT    NOT NULL
                          CONSTRAINT chk_rn_tipo CHECK (tipo_tramite IN (
                              'NUEVA_POLIZA','ENDOSO','RENOVACION','SINIESTRO','CANCELACION','COTIZACION_PYME'
                          )),
    ramo                  TEXT    NOT NULL
                          CONSTRAINT chk_rn_ramo CHECK (ramo IN ('VIDA','GMM','AUTOS','PYME','DANOS')),
    producto_twenty_id    TEXT,                   -- NULL = aplica a todos los productos del ramo
    sla_horas             INTEGER NOT NULL DEFAULT 40,
    sla_dias_habiles      INTEGER NOT NULL DEFAULT 5,
    documentos_requeridos JSONB   NOT NULL DEFAULT '[]',   -- ["INE","SOL_GNP",...]
    documentos_opcionales JSONB   NOT NULL DEFAULT '[]',
    checklist_minimo      INTEGER NOT NULL DEFAULT 0,       -- Mínimo de docs para considerar completo
    activo                BOOLEAN NOT NULL DEFAULT TRUE,
    version               INTEGER NOT NULL DEFAULT 1,
    notas                 TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE NULLS NOT DISTINCT (tipo_tramite, ramo, producto_twenty_id)
);

CREATE INDEX IF NOT EXISTS idx_reglas_tipo_ramo
    ON reglas_negocio (tipo_tramite, ramo)
    WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_reglas_producto
    ON reglas_negocio (producto_twenty_id)
    WHERE producto_twenty_id IS NOT NULL;

-- Trigger updated_at
CREATE OR REPLACE FUNCTION update_updated_at_reglas()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

CREATE TRIGGER trg_reglas_updated_at
    BEFORE UPDATE ON reglas_negocio
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_reglas();

-- RLS
ALTER TABLE reglas_negocio ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_reglas"
    ON reglas_negocio FOR ALL
    TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read_reglas"
    ON reglas_negocio FOR SELECT
    TO authenticated USING (true);

-- Función: obtener la regla más específica (con producto > sin producto)
CREATE OR REPLACE FUNCTION get_regla_negocio(
    p_tipo_tramite TEXT,
    p_ramo         TEXT,
    p_producto_id  TEXT DEFAULT NULL
)
RETURNS TABLE (
    id                    UUID,
    tipo_tramite          TEXT,
    ramo                  TEXT,
    sla_horas             INTEGER,
    sla_dias_habiles      INTEGER,
    documentos_requeridos JSONB,
    documentos_opcionales JSONB,
    checklist_minimo      INTEGER
)
LANGUAGE sql STABLE AS $$
    -- Primero busca regla específica por producto, luego genérica por ramo
    SELECT id, tipo_tramite, ramo, sla_horas, sla_dias_habiles,
           documentos_requeridos, documentos_opcionales, checklist_minimo
    FROM reglas_negocio
    WHERE tipo_tramite = p_tipo_tramite
      AND ramo = p_ramo
      AND activo = TRUE
      AND (
            (p_producto_id IS NOT NULL AND producto_twenty_id = p_producto_id)
            OR producto_twenty_id IS NULL
          )
    ORDER BY (producto_twenty_id IS NOT NULL) DESC   -- específica primero
    LIMIT 1;
$$;

-- Semilla: 25 reglas base (tipo × ramo)
INSERT INTO reglas_negocio (tipo_tramite, ramo, sla_horas, sla_dias_habiles, documentos_requeridos, checklist_minimo) VALUES
-- NUEVA PÓLIZA
('NUEVA_POLIZA', 'VIDA',  40, 5, '["INE","SOL_GNP","ACTA_NAC","COMP_DOM","FMT_GNP","COMP_PAGO"]', 4),
('NUEVA_POLIZA', 'GMM',   24, 3, '["INE","SOL_GNP","COMP_DOM","CARNET","COMP_PAGO"]',              3),
('NUEVA_POLIZA', 'AUTOS', 32, 4, '["INE","SOL_GNP","COMP_DOM"]',                                   3),
('NUEVA_POLIZA', 'PYME',  56, 7, '["INE","SOL_GNP","ACTA_CONST","PODER","COMP_DOM"]',              4),
('NUEVA_POLIZA', 'DANOS', 40, 5, '["INE","SOL_GNP","COMP_DOM"]',                                   3),
-- ENDOSO
('ENDOSO', 'VIDA',  40, 5, '["INE","CARTA_INS"]',       2),
('ENDOSO', 'GMM',   24, 3, '["INE","CARTA_INS"]',       2),
('ENDOSO', 'AUTOS', 24, 3, '["INE","CARTA_INS"]',       2),
('ENDOSO', 'PYME',  40, 5, '["INE","CARTA_INS","PODER"]',3),
('ENDOSO', 'DANOS', 32, 4, '["INE","CARTA_INS"]',       2),
-- RENOVACIÓN
('RENOVACION', 'VIDA',  40, 5, '["POL_GNP","COMP_PAGO"]', 2),
('RENOVACION', 'GMM',   24, 3, '["POL_GNP","COMP_PAGO"]', 2),
('RENOVACION', 'AUTOS', 24, 3, '["POL_GNP","COMP_PAGO"]', 2),
('RENOVACION', 'PYME',  40, 5, '["POL_GNP","COMP_PAGO"]', 2),
('RENOVACION', 'DANOS', 32, 4, '["POL_GNP","COMP_PAGO"]', 2),
-- SINIESTRO
('SINIESTRO', 'VIDA',  24, 3, '["INE","POL_GNP","ACTA_DEFUNCION"]',      3),
('SINIESTRO', 'GMM',   16, 2, '["INE","POL_GNP","CFDI","COMP_DOM"]',     3),
('SINIESTRO', 'AUTOS', 24, 3, '["INE","POL_GNP","LICENCIA","REPORTE"]',  3),
('SINIESTRO', 'DANOS', 32, 4, '["INE","POL_GNP","COMP_DOM","FOTOS"]',    3),
('SINIESTRO', 'PYME',  32, 4, '["INE","POL_GNP","CFDI"]',                2),
-- CANCELACIÓN
('CANCELACION', 'VIDA',  40, 5, '["INE","POL_GNP","CARTA_INS"]', 2),
('CANCELACION', 'GMM',   24, 3, '["INE","POL_GNP","CARTA_INS"]', 2),
('CANCELACION', 'AUTOS', 24, 3, '["INE","POL_GNP","CARTA_INS"]', 2),
('CANCELACION', 'PYME',  40, 5, '["INE","POL_GNP","CARTA_INS"]', 2),
-- COTIZACIÓN PYME (proceso especial: requiere Acta + RFC empresa + estados financieros)
('COTIZACION_PYME', 'PYME', 56, 7, '["INE","ACTA_CONST","RFC_EMP","COMP_DOM","EDO_FINANCIERO"]', 4)
ON CONFLICT DO NOTHING;
