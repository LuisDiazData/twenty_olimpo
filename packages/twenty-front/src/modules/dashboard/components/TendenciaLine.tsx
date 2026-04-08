import { ResponsiveLine } from '@nivo/line';
import { styled } from '@linaria/react';
import { format, parseISO, startOfMonth, subMonths, differenceInDays } from 'date-fns';
import { NIVO_THEME } from '../constants/colors';
import type { Tramite } from '../types/dashboard.types';
import { ESTADOS_FINALES } from '../utils/semaforo';

interface TendenciaLineProps {
  tramites: Tramite[];
  meses?: number;
}

const StyledContainer = styled.div`
  height: 200px;
`;

const StyledEmpty = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #9c9a92;
  font-size: 12px;
`;

export const TendenciaLine = ({ tramites, meses = 6 }: TendenciaLineProps) => {
  const now = new Date();

  const monthlyData = Array.from({ length: meses }, (_, i) => {
    const monthStart = startOfMonth(subMonths(now, meses - 1 - i));
    const monthEnd = startOfMonth(subMonths(now, meses - 2 - i));
    const label = format(monthStart, 'MMM yy');

    const cerrados = tramites.filter((t) => {
      if (!ESTADOS_FINALES.includes(t.estatus ?? '')) return false;
      if (!t.fechaIngreso || !t.fechaLimiteSla) return false;
      const entrada = parseISO(t.fechaIngreso);
      return entrada >= monthStart && entrada < monthEnd;
    });

    if (cerrados.length === 0) return { x: label, y: null };

    const avgDias =
      cerrados.reduce((sum, t) => {
        const dias = differenceInDays(
          parseISO(t.fechaLimiteSla!),
          parseISO(t.fechaIngreso!),
        );
        return sum + Math.max(0, dias);
      }, 0) / cerrados.length;

    return { x: label, y: Math.round(avgDias * 10) / 10 };
  });

  const hasData = monthlyData.some((d) => d.y !== null);

  if (!hasData) {
    return (
      <StyledEmpty>Sin datos de resolución disponibles</StyledEmpty>
    );
  }

  // Determine trend color: last vs second-to-last non-null
  const nonNull = monthlyData.filter((d) => d.y !== null);
  let lineColor = '#1D9E75'; // verde = mejora (dias bajos)
  if (nonNull.length >= 2) {
    const last = nonNull[nonNull.length - 1].y as number;
    const prev = nonNull[nonNull.length - 2].y as number;
    lineColor = last <= prev ? '#1D9E75' : '#A32D2D';
  }

  const lineData = [
    {
      id: 'Días prom.',
      color: lineColor,
      data: monthlyData.map((d) => ({ x: d.x, y: d.y })),
    },
  ];

  return (
    <StyledContainer>
      <ResponsiveLine
        data={lineData}
        colors={[lineColor]}
        margin={{ top: 10, right: 16, bottom: 30, left: 36 }}
        xScale={{ type: 'point' }}
        yScale={{ type: 'linear', min: 0, max: 'auto' }}
        axisBottom={{
          tickSize: 0,
          tickPadding: 6,
        }}
        axisLeft={{
          tickSize: 0,
          tickPadding: 6,
          tickValues: 4,
        }}
        enableGridX={false}
        gridYValues={4}
        pointSize={6}
        pointColor={lineColor}
        pointBorderWidth={2}
        pointBorderColor={{ from: 'serieColor' }}
        enableArea
        areaOpacity={0.08}
        useMesh
        tooltip={({ point }) => (
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
            <strong>{point.data.xFormatted}</strong>: {point.data.yFormatted} días
          </div>
        )}
        theme={NIVO_THEME as Parameters<typeof ResponsiveLine>[0]['theme']}
      />
    </StyledContainer>
  );
};
