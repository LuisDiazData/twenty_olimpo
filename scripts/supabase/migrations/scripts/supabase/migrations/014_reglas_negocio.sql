-- ============================================================
-- Migración 014: Reglas de Negocio
--
-- Externaliza la lógica hardcodeada en agente_asignacion.py:
--   _SLA_DIAS = {"VIDA": 5, "GMM": 3, "AUTOS": 4, "PYME": 7, "DANOS": 5}
--
-- También reemplaza procedure_requirements (migración 006) con
-- soporte de producto_id y checklist detallado por tipo de trámite.
--
-- El pipeline debe consultar esta tabla en lugar del dict Python
-- para calcular sla_dias_habiles y documentos_requeridos.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.reglas_negocio (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Clasificadores del trámite
    tipo_tramite            TEXT        NOT NULL,
    ramo                    TEXT        NOT NULL,
    producto_twenty_id      TEXT,       -- ID del objeto producto en Twenty (referencia suelta, no FK)

    -- SLA
    sla_horas               INTEGER     NOT NULL DEFAULT 40,
    sla_dias_habiles        INTEGER     NOT NULL DEFAULT 5,

    -- Checklist de documentos
    documentos_requeridos   JSONB       NOT NULL DEFAULT '[]',  -- ["INE", "SOL_GNP", ...]
    documentos_opcionales   JSONB       NOT NULL DEFAULT '[]',
    checklist_minimo        INTEGER     NOT NULL DEFAULT 0,      -- mínimo de docs para DOCUMENTACION_COMPLETA

    -- Metadatos
    activo                  BOOLEAN     NOT NULL DEFAULT TRUE,
    version                 INTEGER     NOT NULL DEFAULT 1,
    notas                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),

    -- Unicidad: una regla por (tipo_tramite, ramo, producto)
    -- NULL en producto_twenty_id = aplica a todos los productos del ramo
    CONSTRAINT uq_regla_negocio
        UNIQUE NULLS NOT DISTINCT (tipo_tramite, ramo, producto_twenty_id)
);

-- ── Índices ────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_reglas_tipo_ramo
    ON public.reglas_negocio (tipo_tramite, ramo)
    WHERE activo = TRUE;

CREATE INDEX IF NOT EXISTS idx_reglas_producto
    ON public.reglas_negocio (producto_twenty_id)
    WHERE producto_twenty_id IS NOT NULL;

-- ── Trigger updated_at ────────────────────────────────────────────────────────

CREATE TRIGGER trg_reglas_negocio_updated_at
    BEFORE UPDATE ON public.reglas_negocio
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at();

-- ── RLS ────────────────────────────────────────────────────────────────────────

ALTER TABLE public.reglas_negocio ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_reglas" ON public.reglas_negocio
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read_reglas" ON public.reglas_negocio
    FOR SELECT TO authenticated USING (true);

-- ── Datos iniciales ────────────────────────────────────────────────────────────
-- Migra el dict _SLA_DIAS de agente_asignacion.py y
-- los checklist del CLAUDE.md (Checklists de Documentos por Ramo)

INSERT INTO public.reglas_negocio
    (tipo_tramite, ramo, sla_horas, sla_dias_habiles, documentos_requeridos, documentos_opcionales, checklist_minimo, notas)
VALUES
    -- ── NUEVA_POLIZA ──────────────────────────────────────────────────────────
    ('NUEVA_POLIZA', 'VIDA', 40, 5,
     '["INE","SOL_GNP","ACTA_NAC","COMP_DOM","FMT_GNP","COMP_PAGO"]',
     '["PASAPORTE"]',
     4, 'Emisión Vida. SLA 5 días hábiles GNP.'),

    ('NUEVA_POLIZA', 'GMM', 24, 3,
     '["INE","SOL_GNP","COMP_DOM","CARNET","COMP_PAGO"]',
     '["RFC_EMPRESA","ACTA_CONSTITUTIVA"]',
     3, 'Emisión GMM Individual. SLA 3 días hábiles.'),

    ('NUEVA_POLIZA', 'AUTOS', 32, 4,
     '["INE","SOL_GNP","COMP_DOM"]',
     '["FACTURA_AUTO","TARJETA_CIRCULACION"]',
     2, 'Emisión Autos. SLA 4 días hábiles.'),

    ('NUEVA_POLIZA', 'PYME', 56, 7,
     '["INE","SOL_GNP","ACTA_CONSTITUTIVA","PODER_NOTARIAL","COMP_DOM"]',
     '["EDO_CUENTA","INVENTARIO_BIENES"]',
     4, 'Emisión PyME. SLA 7 días hábiles.'),

    ('NUEVA_POLIZA', 'DANOS', 40, 5,
     '["INE","SOL_GNP","COMP_DOM"]',
     '["INVENTARIO_BIENES","FMT_GNP"]',
     2, 'Emisión Daños. SLA 5 días hábiles.'),

    -- ── ENDOSO ───────────────────────────────────────────────────────────────
    ('ENDOSO', 'VIDA', 40, 5,
     '["INE","CARTA_INS"]',
     '["FMT_GNP"]',
     2, 'Endoso Vida — cambio de beneficiario, datos, etc.'),

    ('ENDOSO', 'GMM', 24, 3,
     '["INE","CARTA_INS"]',
     '["CARNET"]',
     2, 'Endoso GMM — alta/baja de asegurado.'),

    ('ENDOSO', 'AUTOS', 24, 3,
     '["INE","CARTA_INS"]',
     '["FACTURA_AUTO"]',
     1, 'Endoso Autos — cambio de datos.'),

    ('ENDOSO', 'PYME', 40, 5,
     '["INE","CARTA_INS","PODER_NOTARIAL"]',
     '[]',
     2, 'Endoso PyME — cambio de representante legal o datos.'),

    ('ENDOSO', 'DANOS', 32, 4,
     '["INE","CARTA_INS"]',
     '[]',
     1, 'Endoso Daños.'),

    -- ── RENOVACION ───────────────────────────────────────────────────────────
    ('RENOVACION', 'VIDA', 40, 5,
     '["POL_GNP","COMP_PAGO"]',
     '["FMT_GNP"]',
     1, 'Renovación Vida.'),

    ('RENOVACION', 'GMM', 24, 3,
     '["POL_GNP","COMP_PAGO"]',
     '["CARNET"]',
     1, 'Renovación GMM.'),

    ('RENOVACION', 'AUTOS', 24, 3,
     '["POL_GNP","COMP_PAGO"]',
     '[]',
     1, 'Renovación Autos.'),

    ('RENOVACION', 'PYME', 40, 5,
     '["POL_GNP","COMP_PAGO"]',
     '["EDO_CUENTA"]',
     1, 'Renovación PyME.'),

    -- ── SINIESTRO ─────────────────────────────────────────────────────────────
    ('SINIESTRO', 'VIDA', 24, 3,
     '["INE","POL_GNP","ACTA_DEFUNCION"]',
     '["ACTA_NAC","FMT_GNP"]',
     2, 'Siniestro Vida — fallecimiento. SLA urgente 3 días.'),

    ('SINIESTRO', 'GMM', 16, 2,
     '["INE","POL_GNP","CFDI","COMP_DOM"]',
     '["CARNET","RECETA_MEDICA"]',
     2, 'Siniestro GMM — hospitalización/médico. SLA 2 días.'),

    ('SINIESTRO', 'AUTOS', 24, 3,
     '["INE","POL_GNP","LICENCIA_CONDUCIR","REPORTE_VIAL"]',
     '["FOTOS_SINIESTRO"]',
     2, 'Siniestro Autos — accidente/robo. SLA 3 días.'),

    ('SINIESTRO', 'DANOS', 32, 4,
     '["INE","POL_GNP","COMP_DOM","FOTOS_DANOS"]',
     '["COTIZACION_REPARACION"]',
     2, 'Siniestro Daños. SLA 4 días.'),

    -- ── CANCELACION ──────────────────────────────────────────────────────────
    ('CANCELACION', 'VIDA', 40, 5,
     '["INE","POL_GNP","CARTA_INS"]',
     '[]',
     2, 'Cancelación Vida. Requiere carta instrucción firmada.'),

    ('CANCELACION', 'GMM', 24, 3,
     '["INE","POL_GNP","CARTA_INS"]',
     '[]',
     2, 'Cancelación GMM.'),

    ('CANCELACION', 'AUTOS', 24, 3,
     '["INE","POL_GNP","CARTA_INS"]',
     '[]',
     2, 'Cancelación Autos.'),

    -- ── COTIZACION_PYME ───────────────────────────────────────────────────────
    ('COTIZACION_PYME', 'PYME', 56, 7,
     '["INE","ACTA_CONSTITUTIVA","RFC_EMPRESA","COMP_DOM"]',
     '["EDO_CUENTA","INVENTARIO_BIENES"]',
     3, 'Cotización PyME. SLA 7 días hábiles.')

ON CONFLICT ON CONSTRAINT uq_regla_negocio DO NOTHING;

-- ── Función helper: obtener regla para un trámite ─────────────────────────────

CREATE OR REPLACE FUNCTION public.get_regla_negocio(
    p_tipo_tramite TEXT,
    p_ramo         TEXT,
    p_producto_id  TEXT DEFAULT NULL
) RETURNS SETOF public.reglas_negocio AS $$
BEGIN
    -- Buscar regla específica de producto primero, luego genérica del ramo
    RETURN QUERY
        SELECT * FROM public.reglas_negocio
        WHERE tipo_tramite = p_tipo_tramite
          AND ramo = p_ramo
          AND activo = TRUE
          AND (
              (producto_twenty_id = p_producto_id AND p_producto_id IS NOT NULL)
              OR
              (producto_twenty_id IS NULL)
          )
        ORDER BY
            CASE WHEN producto_twenty_id IS NOT NULL THEN 0 ELSE 1 END,  -- específico primero
            version DESC
        LIMIT 1;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION public.get_regla_negocio IS
    'Obtiene la regla de negocio más específica para un tipo_tramite + ramo + producto. '
    'Si existe una regla específica de producto, la prefiere sobre la genérica del ramo.';

COMMENT ON TABLE public.reglas_negocio IS
    'Reglas de negocio por tipo_tramite + ramo + producto. '
    'Externaliza _SLA_DIAS de agente_asignacion.py y los checklist del CLAUDE.md. '
    'El pipeline debe consultar get_regla_negocio() para fechaLimiteSla y documentos requeridos.';
