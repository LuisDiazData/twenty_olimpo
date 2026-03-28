import { styled } from '@linaria/react';
import { format, parseISO } from 'date-fns';
import { ESTADO_LABEL, RAMO_COLORS, TIPO_LABEL } from '../constants/colors';
import type { Tramite } from '../types/dashboard.types';
import { SEMAFORO_HEX, SEMAFORO_LABEL, getSemaforo } from '../utils/semaforo';

export type TableColumn =
  | 'folio'
  | 'agenteTitular'
  | 'tipoTramite'
  | 'ramo'
  | 'estadoTramite'
  | 'fechaLimiteSla'
  | 'especialistaAsignado';

interface SemaforoTableProps {
  tramites: Tramite[];
  columns: TableColumn[];
  onRowClick?: (tramite: Tramite) => void;
}

const COLUMN_LABELS: Record<TableColumn, string> = {
  folio: 'Folio',
  agenteTitular: 'Agente',
  tipoTramite: 'Tipo',
  ramo: 'Ramo',
  estadoTramite: 'Estado',
  fechaLimiteSla: 'Límite SLA',
  especialistaAsignado: 'Especialista',
};

const StyledTable = styled.table`
  width: 100%;
  border-collapse: collapse;
`;

const StyledTh = styled.th`
  font-size: 10px;
  color: #9c9a92;
  font-weight: 600;
  text-align: left;
  padding: 5px 10px;
  border-bottom: 1px solid #2a2d3a;
  white-space: nowrap;
  text-transform: uppercase;
  letter-spacing: 0.05em;
`;

const StyledTr = styled.tr`
  cursor: pointer;
  transition: background 0.1s;

  &:hover td {
    background: rgba(255, 255, 255, 0.03);
  }
`;

const StyledTd = styled.td`
  padding: 7px 10px;
  font-size: 12px;
  color: #e8e6e1;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);

  &:first-child {
    border-left: 3px solid transparent;
    padding-left: 9px;
  }
`;

const StyledBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
`;

const StyledRamoDot = styled.span`
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 5px;
`;

const memberFullName = (
  m: { name: { firstName: string; lastName: string } } | null,
) => {
  if (!m) return '—';
  return `${m.name.firstName} ${m.name.lastName}`.trim() || '—';
};

const formatDate = (d: string | null) => {
  if (!d) return '—';
  try {
    return format(parseISO(d), 'dd/MM/yyyy');
  } catch {
    return d;
  }
};

const estadoBg: Record<string, string> = {
  PENDIENTE: 'rgba(156,154,146,.15)',
  EN_REVISION: 'rgba(24,95,165,.2)',
  LISTO_PARA_GNP: 'rgba(186,117,23,.2)',
  ENVIADO_A_GNP: 'rgba(24,95,165,.2)',
  APROBADO_GNP: 'rgba(29,158,117,.2)',
  RECHAZADO_GNP: 'rgba(163,45,45,.2)',
  CERRADO: 'rgba(156,154,146,.15)',
};
const estadoColor: Record<string, string> = {
  PENDIENTE: '#9c9a92',
  EN_REVISION: '#5fa8e8',
  LISTO_PARA_GNP: '#e6a020',
  ENVIADO_A_GNP: '#5fa8e8',
  APROBADO_GNP: '#22c78a',
  RECHAZADO_GNP: '#e05252',
  CERRADO: '#9c9a92',
};

export const SemaforoTable = ({
  tramites,
  columns,
  onRowClick,
}: SemaforoTableProps) => {
  // Sort: rojo → amarillo → verde → gris
  const ORDER = { rojo: 0, amarillo: 1, verde: 2, gris: 3 };
  const sorted = [...tramites].sort((a, b) => {
    const sa = getSemaforo(a.fechaLimiteSla, a.estadoTramite);
    const sb = getSemaforo(b.fechaLimiteSla, b.estadoTramite);
    if (ORDER[sa] !== ORDER[sb]) return ORDER[sa] - ORDER[sb];
    const da = a.fechaLimiteSla
      ? new Date(a.fechaLimiteSla).getTime()
      : Infinity;
    const db = b.fechaLimiteSla
      ? new Date(b.fechaLimiteSla).getTime()
      : Infinity;
    return da - db;
  });

  const renderCell = (tramite: Tramite, col: TableColumn) => {
    switch (col) {
      case 'folio':
        return (
          <span style={{ fontFamily: 'monospace', fontSize: 11 }}>
            {tramite.folioInterno ?? tramite.name}
          </span>
        );
      case 'agenteTitular':
        return tramite.agenteTitular?.name ?? '—';
      case 'tipoTramite':
        return (
          TIPO_LABEL[tramite.tipoTramite ?? ''] ?? tramite.tipoTramite ?? '—'
        );
      case 'ramo':
        return tramite.ramo ? (
          <>
            <StyledRamoDot
              style={{ backgroundColor: RAMO_COLORS[tramite.ramo] }}
            />
            {tramite.ramo}
          </>
        ) : (
          '—'
        );
      case 'estadoTramite': {
        const est = tramite.estadoTramite ?? '';
        return (
          <StyledBadge
            style={{
              background: estadoBg[est] ?? 'rgba(156,154,146,.15)',
              color: estadoColor[est] ?? '#9c9a92',
            }}
          >
            {ESTADO_LABEL[est] ?? est}
          </StyledBadge>
        );
      }
      case 'fechaLimiteSla':
        return (
          <span style={{ color: '#9c9a92', fontSize: 11 }}>
            {formatDate(tramite.fechaLimiteSla)}
          </span>
        );
      case 'especialistaAsignado':
        return memberFullName(tramite.especialistaAsignado);
      default:
        return '—';
    }
  };

  if (sorted.length === 0) {
    return (
      <div
        style={{ color: '#9c9a92', textAlign: 'center', padding: '24px 0' }}
      >
        Sin trámites
      </div>
    );
  }

  return (
    <StyledTable>
      <thead>
        <tr>
          {columns.map((col) => (
            <StyledTh key={col}>{COLUMN_LABELS[col]}</StyledTh>
          ))}
          <StyledTh>SLA</StyledTh>
        </tr>
      </thead>
      <tbody>
        {sorted.map((t) => {
          const sem = getSemaforo(t.fechaLimiteSla, t.estadoTramite);
          return (
            <StyledTr key={t.id} onClick={() => onRowClick?.(t)}>
              {columns.map((col, idx) => (
                <StyledTd
                  key={col}
                  style={
                    idx === 0
                      ? { borderLeftColor: SEMAFORO_HEX[sem] }
                      : undefined
                  }
                >
                  {renderCell(t, col)}
                </StyledTd>
              ))}
              <StyledTd>
                <StyledBadge
                  style={{
                    background:
                      sem === 'rojo'
                        ? 'rgba(163,45,45,.25)'
                        : sem === 'amarillo'
                          ? 'rgba(186,117,23,.25)'
                          : 'rgba(29,158,117,.2)',
                    color: SEMAFORO_HEX[sem],
                  }}
                >
                  {SEMAFORO_LABEL[sem]}
                </StyledBadge>
              </StyledTd>
            </StyledTr>
          );
        })}
      </tbody>
    </StyledTable>
  );
};
