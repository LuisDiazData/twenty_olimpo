import { styled } from '@linaria/react';
import type { Tramite, TramiteEstado } from '../types/dashboard.types';

interface FunnelChartProps {
  tramites: Tramite[];
}

interface FunnelStage {
  key: TramiteEstado;
  label: string;
  color: string;
}

const STAGES: FunnelStage[] = [
  { key: 'RECIBIDO',               label: 'Recibido',          color: '#185FA5' },
  { key: 'EN_REVISION_DOC',        label: 'En Revisión',       color: '#2879C0' },
  { key: 'DOCUMENTACION_COMPLETA', label: 'Doc. Completa',     color: '#1B9E75' },
  { key: 'TURNADO_GNP',            label: 'Turnado GNP',       color: '#378ADD' },
  { key: 'EN_PROCESO_GNP',         label: 'En GNP',            color: '#1D9E75' },
  { key: 'RESUELTO',               label: 'Resuelto',          color: '#22C78A' },
];

const StyledWrapper = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0;
`;

const StyledRow = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
`;

const StyledStageLabel = styled.span`
  font-size: 11px;
  color: #9c9a92;
  width: 112px;
  flex-shrink: 0;
  text-align: right;
`;

const StyledBarTrack = styled.div`
  flex: 1;
  height: 22px;
  background: #1a1d27;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
`;

interface BarFillProps {
  pct: number;
  color: string;
}

const StyledBarFill = styled.div<BarFillProps>`
  height: 100%;
  width: ${({ pct }) => pct}%;
  background: ${({ color }) => color};
  border-radius: 4px;
  transition: width 0.4s ease;
  display: flex;
  align-items: center;
  padding-left: 8px;
  min-width: ${({ pct }) => (pct > 0 ? '2px' : '0')};
`;

const StyledCount = styled.span`
  font-size: 11px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  white-space: nowrap;
`;

const StyledPct = styled.span`
  font-size: 10px;
  color: #9c9a92;
  width: 36px;
  text-align: right;
  flex-shrink: 0;
`;

const StyledEmptyMsg = styled.div`
  color: #5f5e5a;
  font-size: 12px;
  text-align: center;
  padding: 24px 0;
`;

export const FunnelChart = ({ tramites }: FunnelChartProps) => {
  const counts = STAGES.map((s) => ({
    ...s,
    count: tramites.filter((t) => t.estatus === s.key).length,
  }));

  const maxCount = Math.max(...counts.map((c) => c.count), 1);

  if (tramites.length === 0) {
    return <StyledEmptyMsg>Sin trámites en el período</StyledEmptyMsg>;
  }

  return (
    <StyledWrapper>
      {counts.map(({ key, label, color, count }) => {
        const pct = Math.round((count / maxCount) * 100);
        const pctOfTotal = tramites.length
          ? Math.round((count / tramites.length) * 100)
          : 0;
        return (
          <StyledRow key={key}>
            <StyledStageLabel>{label}</StyledStageLabel>
            <StyledBarTrack>
              <StyledBarFill pct={pct} color={color}>
                {count > 0 && <StyledCount>{count}</StyledCount>}
              </StyledBarFill>
            </StyledBarTrack>
            <StyledPct>{pctOfTotal}%</StyledPct>
          </StyledRow>
        );
      })}
    </StyledWrapper>
  );
};
