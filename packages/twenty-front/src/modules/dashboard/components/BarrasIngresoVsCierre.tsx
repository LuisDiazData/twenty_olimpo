import { styled } from '@linaria/react';
import { format, parseISO, startOfMonth, subMonths } from 'date-fns';
import type { Tramite } from '../types/dashboard.types';
import { ESTADOS_FINALES } from '../utils/semaforo';

interface BarrasIngresoVsCierreProps {
  tramites: Tramite[];
  meses?: number;
}

const StyledContainer = styled.div`
  display: flex;
  flex-direction: column;
  height: 200px;
  gap: 8px;
`;

const StyledBarsArea = styled.div`
  flex: 1;
  display: flex;
  align-items: flex-end;
  gap: 4px;
`;

const StyledGroup = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  height: 100%;
  justify-content: flex-end;
`;

const StyledBarsRow = styled.div`
  display: flex;
  gap: 2px;
  align-items: flex-end;
  width: 100%;
`;

const StyledBar = styled.div`
  flex: 1;
  border-radius: 3px 3px 0 0;
  min-height: 2px;
  transition: opacity 0.1s;

  &:hover {
    opacity: 0.85;
  }
`;

const StyledLabel = styled.div`
  font-size: 10px;
  color: #9c9a92;
  text-align: center;
  white-space: nowrap;
`;

const StyledLegend = styled.div`
  display: flex;
  gap: 14px;
  padding-top: 4px;
`;

const StyledLegendItem = styled.div`
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: #9c9a92;
`;

const StyledLegendDot = styled.span`
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
`;

export const BarrasIngresoVsCierre = ({
  tramites,
  meses = 6,
}: BarrasIngresoVsCierreProps) => {
  const now = new Date();

  const data = Array.from({ length: meses }, (_, i) => {
    const monthStart = startOfMonth(subMonths(now, meses - 1 - i));
    const monthEnd = startOfMonth(subMonths(now, meses - 2 - i));
    const label = format(monthStart, 'MMM');

    const ingresados = tramites.filter((t) => {
      if (!t.fechaIngreso) return false;
      const d = parseISO(t.fechaIngreso);
      return d >= monthStart && d < monthEnd;
    }).length;

    const cerrados = tramites.filter((t) => {
      if (!ESTADOS_FINALES.includes(t.estatus ?? '')) return false;
      if (!t.fechaIngreso) return false;
      const d = parseISO(t.fechaIngreso);
      return d >= monthStart && d < monthEnd;
    }).length;

    return { label, ingresados, cerrados };
  });

  const maxVal = Math.max(...data.flatMap((d) => [d.ingresados, d.cerrados]), 1);

  return (
    <StyledContainer>
      <StyledBarsArea>
        {data.map((d) => (
          <StyledGroup key={d.label}>
            <StyledBarsRow>
              <StyledBar
                title={`Ingresados: ${d.ingresados}`}
                style={{
                  height: `${(d.ingresados / maxVal) * 140}px`,
                  backgroundColor: '#1D9E75',
                }}
              />
              <StyledBar
                title={`Cerrados: ${d.cerrados}`}
                style={{
                  height: `${(d.cerrados / maxVal) * 140}px`,
                  backgroundColor: '#185FA5',
                }}
              />
            </StyledBarsRow>
            <StyledLabel>{d.label}</StyledLabel>
          </StyledGroup>
        ))}
      </StyledBarsArea>
      <StyledLegend>
        <StyledLegendItem>
          <StyledLegendDot style={{ backgroundColor: '#1D9E75' }} />
          Ingresados
        </StyledLegendItem>
        <StyledLegendItem>
          <StyledLegendDot style={{ backgroundColor: '#185FA5' }} />
          Cerrados
        </StyledLegendItem>
      </StyledLegend>
    </StyledContainer>
  );
};
