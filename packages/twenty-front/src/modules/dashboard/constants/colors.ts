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
  PYME: '#D85A30',
  DANOS: '#7F77DD',
};

export const ESTADO_LABEL: Record<string, string> = {
  PENDIENTE: 'Pendiente',
  EN_REVISION: 'En revisión',
  LISTO_PARA_GNP: 'Listo para GNP',
  ENVIADO_A_GNP: 'Enviado a GNP',
  APROBADO_GNP: 'Aprobado GNP',
  RECHAZADO_GNP: 'Rechazado GNP',
  CERRADO: 'Cerrado',
};

export const TIPO_LABEL: Record<string, string> = {
  NUEVA_POLIZA: 'Nueva póliza',
  ENDOSO: 'Endoso',
  RENOVACION: 'Renovación',
  CANCELACION: 'Cancelación',
  SINIESTRO: 'Siniestro',
  COTIZACION_PYME: 'Cotización PYME',
};

export const RAMOS = ['VIDA', 'GMM', 'AUTOS', 'PYME', 'DANOS'] as const;

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
