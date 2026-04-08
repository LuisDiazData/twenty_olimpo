-- Migration 013: calendario_operativo
-- Calendario de días hábiles para cálculo correcto de SLAs.
-- Excluye festivos nacionales MX y festivos internos de GNP.
-- La función add_business_days() la usan los agentes de IA para calcular fechaLimiteSla.

CREATE TABLE IF NOT EXISTS calendario_operativo (
    id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    fecha       DATE    NOT NULL UNIQUE,
    es_habil    BOOLEAN NOT NULL DEFAULT TRUE,
    tipo_dia    TEXT    NOT NULL DEFAULT 'LABORAL'
                CONSTRAINT chk_tipo_dia CHECK (tipo_dia IN ('LABORAL','FESTIVO','FESTIVO_GNP','SABADO','DOMINGO')),
    descripcion TEXT,                        -- Ej: "Día de la Independencia"
    anio        INTEGER NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calendario_fecha_habil
    ON calendario_operativo (fecha)
    WHERE es_habil = TRUE;

CREATE INDEX IF NOT EXISTS idx_calendario_anio
    ON calendario_operativo (anio, fecha);

-- RLS
ALTER TABLE calendario_operativo ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_calendario"
    ON calendario_operativo FOR ALL
    TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read_calendario"
    ON calendario_operativo FOR SELECT
    TO authenticated USING (true);

-- Función: sumar días hábiles a una fecha (excluyendo sábados, domingos y festivos)
CREATE OR REPLACE FUNCTION add_business_days(p_start DATE, p_days INTEGER)
RETURNS DATE
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_current DATE := p_start;
    v_counted INTEGER := 0;
BEGIN
    WHILE v_counted < p_days LOOP
        v_current := v_current + INTERVAL '1 day';
        -- Es día hábil si no está marcado como no-hábil en el calendario
        -- y no es sábado/domingo (fallback si no está en tabla)
        IF EXTRACT(DOW FROM v_current) NOT IN (0, 6) THEN  -- 0=domingo, 6=sábado
            IF NOT EXISTS (
                SELECT 1 FROM calendario_operativo
                WHERE fecha = v_current AND es_habil = FALSE
            ) THEN
                v_counted := v_counted + 1;
            END IF;
        END IF;
    END LOOP;
    RETURN v_current;
END;
$$;

-- Semilla: festivos nacionales MX 2025 y 2026
INSERT INTO calendario_operativo (fecha, es_habil, tipo_dia, descripcion, anio) VALUES
-- 2025
('2025-01-01', FALSE, 'FESTIVO',     'Año Nuevo',                         2025),
('2025-02-03', FALSE, 'FESTIVO',     'Día de la Constitución (puente)',    2025),
('2025-03-17', FALSE, 'FESTIVO',     'Natalicio de Juárez (puente)',       2025),
('2025-04-17', FALSE, 'FESTIVO',     'Jueves Santo',                       2025),
('2025-04-18', FALSE, 'FESTIVO',     'Viernes Santo',                      2025),
('2025-05-01', FALSE, 'FESTIVO',     'Día del Trabajo',                    2025),
('2025-09-16', FALSE, 'FESTIVO',     'Día de la Independencia',            2025),
('2025-11-17', FALSE, 'FESTIVO',     'Revolución Mexicana (puente)',       2025),
('2025-12-25', FALSE, 'FESTIVO',     'Navidad',                            2025),
-- 2026
('2026-01-01', FALSE, 'FESTIVO',     'Año Nuevo',                         2026),
('2026-02-02', FALSE, 'FESTIVO',     'Día de la Constitución (puente)',    2026),
('2026-03-16', FALSE, 'FESTIVO',     'Natalicio de Juárez (puente)',       2026),
('2026-04-02', FALSE, 'FESTIVO',     'Jueves Santo',                       2026),
('2026-04-03', FALSE, 'FESTIVO',     'Viernes Santo',                      2026),
('2026-05-01', FALSE, 'FESTIVO',     'Día del Trabajo',                    2026),
('2026-09-16', FALSE, 'FESTIVO',     'Día de la Independencia',            2026),
('2026-11-16', FALSE, 'FESTIVO',     'Revolución Mexicana (puente)',       2026),
('2026-12-25', FALSE, 'FESTIVO',     'Navidad',                            2026)
ON CONFLICT (fecha) DO NOTHING;
