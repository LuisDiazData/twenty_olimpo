import type { SemaforoColor } from '../types/dashboard.types';

export const ESTADOS_CERRADOS = ['APROBADO_GNP', 'CERRADO'];

// Includes RECHAZADO_GNP as "resolved" for SLA purposes
export const ESTADOS_FINALES = ['APROBADO_GNP', 'CERRADO', 'RECHAZADO_GNP'];

export function getSemaforo(
  fechaLimiteSla: string | null | undefined,
  estadoTramite: string | null | undefined,
): SemaforoColor {
  if (!estadoTramite) return 'gris';
  if (ESTADOS_FINALES.includes(estadoTramite)) return 'verde';
  if (!fechaLimiteSla) return 'gris';
  const horas =
    (new Date(fechaLimiteSla).getTime() - Date.now()) / 3_600_000;
  if (horas < 0) return 'rojo';
  if (horas < 48) return 'amarillo';
  return 'verde';
}

export const SEMAFORO_HEX: Record<SemaforoColor, string> = {
  rojo: '#A32D2D',
  amarillo: '#BA7517',
  verde: '#1D9E75',
  gris: '#5F5E5A',
};

export const SEMAFORO_LABEL: Record<SemaforoColor, string> = {
  rojo: 'VENCIDO',
  amarillo: '<48 hrs',
  verde: 'OK',
  gris: 'Sin fecha',
};
