-- ============================================================
-- Seed 013b: Festivos nacionales México 2025-2026
--
-- Fuente: Código Federal de Procedimientos Civiles (CFF)
-- Artículo 74 — Días de descanso obligatorio.
-- Aplicar DESPUÉS de 013_calendario_operativo.sql.
-- Idempotente: INSERT ... ON CONFLICT DO NOTHING
-- ============================================================

INSERT INTO public.calendario_operativo (fecha, es_habil, tipo_dia, descripcion, anio)
VALUES
    -- ── 2025 ──────────────────────────────────────────────────────────────────
    ('2025-01-01', FALSE, 'FESTIVO',     'Año Nuevo',                                        2025),
    ('2025-02-03', FALSE, 'FESTIVO',     'Día de la Constitución (lunes próximo)',            2025),
    ('2025-03-17', FALSE, 'FESTIVO',     'Natalicio de Benito Juárez (lunes próximo)',        2025),
    ('2025-04-17', FALSE, 'FESTIVO',     'Jueves Santo (GNP)',                                2025),
    ('2025-04-18', FALSE, 'FESTIVO_GNP', 'Viernes Santo',                                    2025),
    ('2025-05-01', FALSE, 'FESTIVO',     'Día del Trabajo',                                  2025),
    ('2025-09-16', FALSE, 'FESTIVO',     'Día de la Independencia',                          2025),
    ('2025-11-17', FALSE, 'FESTIVO',     'Día de la Revolución (lunes próximo)',              2025),
    ('2025-12-25', FALSE, 'FESTIVO',     'Navidad',                                          2025),
    -- Puentes adicionales GNP (sujeto a confirmación anual)
    ('2025-04-14', FALSE, 'FESTIVO_GNP', 'Lunes Santo (puente GNP)',                         2025),
    ('2025-11-01', FALSE, 'FESTIVO_GNP', 'Día de Todos Santos (puente GNP)',                 2025),
    ('2025-12-24', FALSE, 'FESTIVO_GNP', 'Nochebuena (puente GNP)',                          2025),
    ('2025-12-26', FALSE, 'FESTIVO_GNP', 'Puente Navidad GNP',                               2025),
    ('2025-12-31', FALSE, 'FESTIVO_GNP', 'Nochevieja (puente GNP)',                          2025),

    -- ── 2026 ──────────────────────────────────────────────────────────────────
    ('2026-01-01', FALSE, 'FESTIVO',     'Año Nuevo',                                        2026),
    ('2026-02-02', FALSE, 'FESTIVO',     'Día de la Constitución (lunes próximo)',            2026),
    ('2026-03-16', FALSE, 'FESTIVO',     'Natalicio de Benito Juárez (lunes próximo)',        2026),
    ('2026-04-02', FALSE, 'FESTIVO_GNP', 'Jueves Santo (GNP)',                                2026),
    ('2026-04-03', FALSE, 'FESTIVO',     'Viernes Santo',                                    2026),
    ('2026-05-01', FALSE, 'FESTIVO',     'Día del Trabajo',                                  2026),
    ('2026-09-16', FALSE, 'FESTIVO',     'Día de la Independencia',                          2026),
    ('2026-11-16', FALSE, 'FESTIVO',     'Día de la Revolución (lunes próximo)',              2026),
    ('2026-12-25', FALSE, 'FESTIVO',     'Navidad',                                          2026),
    -- Puentes GNP 2026
    ('2026-03-30', FALSE, 'FESTIVO_GNP', 'Lunes Santo (puente GNP)',                         2026),
    ('2026-11-02', FALSE, 'FESTIVO_GNP', 'Día de Muertos (puente GNP)',                      2026),
    ('2026-12-24', FALSE, 'FESTIVO_GNP', 'Nochebuena (puente GNP)',                          2026),
    ('2026-12-28', FALSE, 'FESTIVO_GNP', 'Puente fin de año GNP',                            2026),
    ('2026-12-31', FALSE, 'FESTIVO_GNP', 'Nochevieja (puente GNP)',                          2026)

ON CONFLICT (fecha) DO NOTHING;

-- Verificación: contar festivos cargados
DO $$
DECLARE
    cnt INTEGER;
BEGIN
    SELECT COUNT(*) INTO cnt
    FROM public.calendario_operativo
    WHERE anio IN (2025, 2026) AND es_habil = FALSE;
    RAISE NOTICE 'Días inhábiles cargados (2025-2026): %', cnt;
END$$;
