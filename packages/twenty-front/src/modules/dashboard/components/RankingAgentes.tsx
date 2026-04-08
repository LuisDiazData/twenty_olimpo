import { styled } from '@linaria/react';
import type { AgentPerformance, KpiSnapshot, Tramite } from '../types/dashboard.types';

interface RankingAgentesProps {
  agentPerformance: AgentPerformance[];
  kpiSnapshots: KpiSnapshot[];
  tramites: Tramite[];
}

interface AgentRow {
  rank: number;
  cua: string;
  nombre: string;
  primaEmitida: number;
  tramitesTotales: number;
  metaAlcanzada: boolean | null;
}

const formatMXN = (val: number) =>
  new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    maximumFractionDigits: 0,
  }).format(val);

const StyledTable = styled.table`
  width: 100%;
  border-collapse: collapse;
`;

const StyledTh = styled.th`
  font-size: 10px;
  color: #9c9a92;
  font-weight: 600;
  text-align: left;
  padding: 4px 8px;
  border-bottom: 1px solid #2a2d3a;
  text-transform: uppercase;
  letter-spacing: 0.04em;
`;

const StyledTd = styled.td`
  padding: 8px 8px;
  font-size: 12px;
  color: #c8c5bf;
  border-bottom: 1px solid #1e2130;
`;

const StyledRankBadge = styled.span`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 700;
  background: #2a2d3a;
  color: #9c9a92;

  &[data-top='true'] {
    background: rgba(29, 158, 117, 0.15);
    color: #22c78a;
  }
`;

const StyledMetaIndicator = styled.span`
  font-size: 13px;
  &[data-ok='true'] { color: #22c78a; }
  &[data-ok='false'] { color: #e05252; }
  &[data-ok='null'] { color: #5f5e5a; }
`;

const StyledCua = styled.span`
  font-family: 'Fira Code', 'Courier New', monospace;
  font-size: 10px;
  color: #5f5e5a;
`;

const StyledEmptyMsg = styled.div`
  color: #5f5e5a;
  font-size: 12px;
  text-align: center;
  padding: 24px 0;
`;

export const RankingAgentes = ({
  agentPerformance,
  kpiSnapshots: _kpiSnapshots,
  tramites,
}: RankingAgentesProps) => {
  let rows: AgentRow[];

  if (agentPerformance.length > 0) {
    // Usar datos de agentPerformanceMonthly
    rows = agentPerformance
      .slice(0, 5)
      .map((ap, i) => ({
        rank: i + 1,
        cua: ap.agente?.claveAgente ?? '—',
        nombre: ap.agente?.name ?? '—',
        primaEmitida: ap.primaEmitida ?? 0,
        tramitesTotales: ap.tramitesTotales ?? 0,
        metaAlcanzada: ap.tasaCumplimientoSla !== null ? ap.tasaCumplimientoSla >= 85 : null,
      }));
  } else {
    // Fallback: calcular desde tramites agrupados por agente
    const agentMap = new Map<string, { nombre: string; count: number }>();
    for (const t of tramites) {
      if (!t.agente) continue;
      const existing = agentMap.get(t.agente.id) ?? {
        nombre: t.agente.name,
        count: 0,
      };
      agentMap.set(t.agente.id, { ...existing, count: existing.count + 1 });
    }

    rows = [...agentMap.entries()]
      .sort((a, b) => b[1].count - a[1].count)
      .slice(0, 5)
      .map(([_id, { nombre, count }], i) => ({
        rank: i + 1,
        cua: '—',
        nombre,
        primaEmitida: 0,
        tramitesTotales: count,
        metaAlcanzada: null,
      }));
  }

  if (rows.length === 0) {
    return <StyledEmptyMsg>Sin datos de agentes en el período</StyledEmptyMsg>;
  }

  const showPrima = agentPerformance.length > 0;

  return (
    <StyledTable>
      <thead>
        <tr>
          <StyledTh>#</StyledTh>
          <StyledTh>CUA</StyledTh>
          <StyledTh>Nombre</StyledTh>
          {showPrima ? (
            <StyledTh>Prima Emitida</StyledTh>
          ) : (
            <StyledTh>Trámites</StyledTh>
          )}
          <StyledTh>Meta</StyledTh>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.rank}>
            <StyledTd>
              <StyledRankBadge data-top={String(row.rank <= 3)}>
                {row.rank}
              </StyledRankBadge>
            </StyledTd>
            <StyledTd>
              <StyledCua>{row.cua}</StyledCua>
            </StyledTd>
            <StyledTd>{row.nombre}</StyledTd>
            <StyledTd>
              {showPrima ? formatMXN(row.primaEmitida) : row.tramitesTotales}
            </StyledTd>
            <StyledTd>
              <StyledMetaIndicator
                data-ok={row.metaAlcanzada === null ? 'null' : String(row.metaAlcanzada)}
              >
                {row.metaAlcanzada === null ? '—' : row.metaAlcanzada ? '✓' : '✗'}
              </StyledMetaIndicator>
            </StyledTd>
          </tr>
        ))}
      </tbody>
    </StyledTable>
  );
};
