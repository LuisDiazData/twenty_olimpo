import { ResponsivePie } from '@nivo/pie';
import { styled } from '@linaria/react';
import { NIVO_THEME, RAMO_COLORS, RAMOS } from '../constants/colors';
import type { Tramite } from '../types/dashboard.types';
import { ESTADOS_FINALES } from '../utils/semaforo';

interface DonaRamoProps {
  tramites: Tramite[];
}

const StyledContainer = styled.div`
  height: 220px;
  position: relative;
`;

const StyledCenter = styled.div`
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
`;

const StyledCenterNum = styled.div`
  font-size: 26px;
  font-weight: 700;
  color: #e8e6e1;
  line-height: 1;
`;

const StyledCenterLabel = styled.div`
  font-size: 10px;
  color: #9c9a92;
  margin-top: 2px;
`;

const StyledLegend = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  margin-top: 8px;
`;

const StyledLegendItem = styled.div`
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: #9c9a92;
`;

const StyledDot = styled.span`
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
`;

export const DonaRamo = ({ tramites }: DonaRamoProps) => {
  const activos = tramites.filter(
    (t) => !ESTADOS_FINALES.includes(t.estadoTramite ?? ''),
  );

  const data = RAMOS.map((ramo) => ({
    id: ramo,
    label: ramo,
    value: activos.filter((t) => t.ramo === ramo).length,
    color: RAMO_COLORS[ramo],
  })).filter((d) => d.value > 0);

  const total = activos.length;

  if (data.length === 0) {
    return (
      <div style={{ color: '#9c9a92', textAlign: 'center', padding: '40px 0' }}>
        Sin trámites activos
      </div>
    );
  }

  return (
    <>
      <StyledContainer>
        <ResponsivePie
          data={data}
          colors={({ data: d }) => (d as { color: string }).color}
          innerRadius={0.62}
          padAngle={1.5}
          cornerRadius={2}
          enableArcLabels={false}
          enableArcLinkLabels={false}
          isInteractive
          tooltip={({ datum }) => (
            <div
              style={{
                background: '#1a1d27',
                border: '1px solid #2a2d3a',
                padding: '6px 10px',
                borderRadius: 4,
                fontSize: 11,
                color: '#e8e6e1',
              }}
            >
              <strong style={{ color: datum.color }}>{datum.id}</strong>:{' '}
              {datum.value} (
              {total > 0 ? ((datum.value / total) * 100).toFixed(0) : 0}%)
            </div>
          )}
          theme={NIVO_THEME as Parameters<typeof ResponsivePie>[0]['theme']}
          margin={{ top: 10, right: 10, bottom: 10, left: 10 }}
        />
        <StyledCenter>
          <StyledCenterNum>{total}</StyledCenterNum>
          <StyledCenterLabel>activos</StyledCenterLabel>
        </StyledCenter>
      </StyledContainer>
      <StyledLegend>
        {data.map((d) => (
          <StyledLegendItem key={d.id}>
            <StyledDot style={{ backgroundColor: d.color }} />
            {d.label}: {d.value} (
            {total > 0 ? ((d.value / total) * 100).toFixed(0) : 0}%)
          </StyledLegendItem>
        ))}
      </StyledLegend>
    </>
  );
};
