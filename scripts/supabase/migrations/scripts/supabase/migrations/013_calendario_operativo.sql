-- ============================================================
-- Migración 013: Calendario Operativo
--
-- Días hábiles y festivos para cálculo correcto de SLA.
-- El método _add_business_days() en agente_asignacion.py actualmente
-- calcula días hábiles ignorando festivos nacionales y de GNP.
-- Esta tabla y la función add_business_days() corrigen eso.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.calendario_operativo (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    fecha       DATE        NOT NULL UNIQUE,
    es_habil    BOOLEAN     NOT NULL DEFAULT TRUE,
    tipo_dia    TEXT        NOT NULL DEFAULT 'LABORAL'
                CHECK (tipo_dia IN (
                    'LABORAL',      -- día hábil normal (lunes-viernes)
                    'FESTIVO',      -- festivo nacional mexicano (CFF)
                    'FESTIVO_GNP',  -- festivo interno de GNP
                    'SABADO',       -- sábado (inhábil por defecto)
                    'DOMINGO'       -- domingo (inhábil)
                )),
    descripcion TEXT,               -- Ej: "Día de la Independencia"
    anio        INTEGER     NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Índices ────────────────────────────────────────────────────────────────────

-- Índice principal: consultar si una fecha es hábil
CREATE INDEX IF NOT EXISTS idx_calendario_fecha_habil
    ON public.calendario_operativo (fecha)
    WHERE es_habil = TRUE;

-- Índice para carga/sync por año
CREATE INDEX IF NOT EXISTS idx_calendario_anio
    ON public.calendario_operativo (anio, fecha);

-- ── RLS ────────────────────────────────────────────────────────────────────────

ALTER TABLE public.calendario_operativo ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_calendario" ON public.calendario_operativo
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read_calendario" ON public.calendario_operativo
    FOR SELECT TO authenticated USING (true);

-- ── Función: add_business_days ─────────────────────────────────────────────────
-- Reemplaza la lógica Python de agente_asignacion.py:143-150
-- que ignora festivos. Esta versión los excluye correctamente.

CREATE OR REPLACE FUNCTION public.add_business_days(
    p_start DATE,
    p_days  INTEGER
) RETURNS DATE AS $$
DECLARE
    v_current DATE := p_start;
    v_added   INTEGER := 0;
BEGIN
    WHILE v_added < p_days LOOP
        v_current := v_current + 1;
        -- Es hábil si:
        -- 1. No es sábado (DOW=6) ni domingo (DOW=0)
        -- 2. No está marcado como inhábil en el calendario
        IF EXTRACT(DOW FROM v_current) NOT IN (0, 6)
           AND NOT EXISTS (
               SELECT 1 FROM public.calendario_operativo
               WHERE fecha = v_current
                 AND es_habil = FALSE
           )
        THEN
            v_added := v_added + 1;
        END IF;
    END LOOP;
    RETURN v_current;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION public.add_business_days IS
    'Suma p_days días hábiles a p_start, excluyendo fines de semana y '
    'fechas marcadas como inhábiles en calendario_operativo. '
    'Reemplaza _add_business_days() de agente_asignacion.py.';

COMMENT ON TABLE public.calendario_operativo IS
    'Calendario de días hábiles e inhábiles. '
    'Incluye festivos nacionales MX (CFF) y festivos internos de GNP. '
    'Usado por add_business_days() para cálculo correcto de fechaLimiteSla.';
