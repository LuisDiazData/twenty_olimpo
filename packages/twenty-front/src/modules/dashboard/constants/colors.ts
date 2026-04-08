export const DASHBOARD_COLORS = {
  bg: '#0f1117',
  card: '#1a1d27',
  border: '#2a2d3a',
  text: '#e8e6e1',
  textSec: '#9c9a92',
  verde: '#1D9E75',
  amarillo: '#BA7517',
  rojo: '#A32D2D',
  azul: '#185FA5',
} as const;

export const RAMO_COLORS: Record<string, string> = {
  VIDA: '#1D9E75',
  GMM: '#378ADD',
  AUTOS: '#BA7517',
  PYMES: '#D85A30',
  DANOS: '#7F77DD',
};

// Mapeo estatus reales del schema de Twenty → etiqueta legible
export const ESTADO_LABEL: Record<string, string> = {
  RECIBIDO: 'Recibido',
  EN_REVISION_DOC: 'En revisión',
  DOCUMENTACION_COMPLETA: 'Doc. completa',
  TURNADO_GNP: 'Turnado GNP',
  EN_PROCESO_GNP: 'En proceso GNP',
  DETENIDO: 'Detenido',
  RESUELTO: 'Resuelto',
  CANCELADO: 'Cancelado',
};

export const ESTADO_COLORS: Record<string, { bg: string; color: string }> = {
  RECIBIDO: { bg: 'rgba(156,154,146,.15)', color: '#9c9a92' },
  EN_REVISION_DOC: { bg: 'rgba(24,95,165,.2)', color: '#5fa8e8' },
  DOCUMENTACION_COMPLETA: { bg: 'rgba(186,117,23,.2)', color: '#e6a020' },
  TURNADO_GNP: { bg: 'rgba(24,95,165,.2)', color: '#5fa8e8' },
  EN_PROCESO_GNP: { bg: 'rgba(24,95,165,.15)', color: '#378add' },
  DETENIDO: { bg: 'rgba(163,45,45,.2)', color: '#e05252' },
  RESUELTO: { bg: 'rgba(29,158,117,.2)', color: '#22c78a' },
  CANCELADO: { bg: 'rgba(156,154,146,.15)', color: '#9c9a92' },
};

export const TIPO_LABEL: Record<string, string> = {
  EMISION: 'Emisión',
  ENDOSO: 'Endoso',
  RENOVACION: 'Renovación',
  CANCELACION: 'Cancelación',
  SINIESTRO: 'Siniestro',
};

export const RAMOS = ['VIDA', 'GMM', 'AUTOS', 'PYMES', 'DANOS'] as const;

export const NIVO_THEME = {
  background: '#1a1d27',
  text: { fill: '#9c9a92', fontSize: 11 },
  axis: {
    domain: { line: { stroke: '#2a2d3a' } },
    ticks: {
      line: { stroke: '#2a2d3a' },
      text: { fill: '#9c9a92', fontSize: 10 },
    },
    legend: { text: { fill: '#e8e6e1', fontSize: 11 } },
  },
  grid: { line: { stroke: '#2a2d3a', strokeDasharray: '4 2' } },
  legends: { text: { fill: '#9c9a92', fontSize: 11 } },
  tooltip: {
    container: {
      background: '#1a1d27',
      color: '#e8e6e1',
      fontSize: 11,
      border: '1px solid #2a2d3a',
      borderRadius: 4,
      padding: '6px 10px',
    },
  },
} as const;
