import { ResponsiveBar } from '@nivo/bar';
import { styled } from '@linaria/react';
import type { Tramite } from '../types/dashboard.types';
import { RAMOS } from '../constants/colors';
import { getSemaforo } from '../utils/semaforo';

interface ProductividadRamoChartProps {
  tramites: Tramite[];
}

const StyledWrapper = styled.div`
  height: 200px;
`;

const StyledLegend = styled.div`
  display: flex;
  gap: 16px;
  margin-top: 8px;
`;

const StyledLegendItem = styled.div`
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  color: #9c9a92;
`;

const StyledDot = styled.div`
  width: 8px;
  height: 8px;
  border-radius: 2px;
`;

const NIVO_THEME = {
  background: 'transparent',
  axis: {
    ticks: {
      text: { fill: '#9c9a92', fontSize: 10 },
    },
    legend: {
      text: { fill: '#9c9a92', fontSize: 10 },
    },
  },
  grid: {
    line: { stroke: '#2a2d3a', strokeWidth: 1 },
  },
  tooltip: {
    container: {
      background: '#1a1d27',
      border: '1px solid #2a2d3a',
      borderRadius: 6,
      color: '#e8e6e1',
      fontSize: 12,
    },
  },
};

export const ProductividadRamoChart = ({ tramites }: ProductividadRamoChartProps) => {
  const data = RAMOS.map((ramo) => {
    const del_ramo = tramites.filter((t) => t.ramo === ramo);
    return {
      ramo,
      Volumen: del_ramo.length,
      'SLA Vencidos': del_ramo.filter(
        (t) => getSemaforo(t.fechaLimiteSla, t.estatus) === 'rojo',
      ).length,
    };
  }).filter((d) => d.Volumen > 0);

  if (data.length === 0) {
    return (
      <div style={{ color: '#5f5e5a', textAlign: 'center', padding: '24px 0', fontSize: 12 }}>
        Sin datos en el período
      </div>
    );
  }

  return (
    <>
      <StyledWrapper>
        <ResponsiveBar
          data={data}
          keys={['Volumen', 'SLA Vencidos']}
          indexBy="ramo"
          groupMode="grouped"
          margin={{ top: 10, right: 10, bottom: 30, left: 30 }}
          padding={0.3}
          colors={['#185FA5', '#A32D2D']}
          theme={NIVO_THEME}
          borderRadius={3}
          axisBottom={{
            tickSize: 0,
            tickPadding: 6,
          }}
          axisLeft={{
            tickSize: 0,
            tickPadding: 6,
          }}
          enableLabel={false}
          animate={false}
          isInteractive
        />
      </StyledWrapper>
      <StyledLegend>
        <StyledLegendItem>
          <StyledDot style={{ background: '#185FA5' }} />
          Volumen
        </StyledLegendItem>
        <StyledLegendItem>
          <StyledDot style={{ background: '#A32D2D' }} />
          SLA Vencidos
        </StyledLegendItem>
      </StyledLegend>
    </>
  );
};
