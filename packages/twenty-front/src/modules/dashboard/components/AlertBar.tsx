import { styled } from '@linaria/react';
import { differenceInDays, parseISO } from 'date-fns';
import { isDefined } from 'twenty-shared/utils';
import type { Tramite } from '../types/dashboard.types';
import { ESTADOS_FINALES, getSemaforo } from '../utils/semaforo';

const StyledBar = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 20px;
  background: #1a1d27;
  border-bottom: 1px solid #2a2d3a;
  flex-shrink: 0;
  flex-wrap: wrap;
`;

const StyledPill = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;

  &[data-type='rojo'] {
    background: rgba(163, 45, 45, 0.2);
    color: #e05252;
    border: 1px solid rgba(163, 45, 45, 0.4);
  }
  &[data-type='amarillo'] {
    background: rgba(186, 117, 23, 0.2);
    color: #e6a020;
    border: 1px solid rgba(186, 117, 23, 0.4);
  }
  &[data-type='verde'] {
    background: rgba(29, 158, 117, 0.15);
    color: #22c78a;
    border: 1px solid rgba(29, 158, 117, 0.3);
  }
`;

const StyledSpacer = styled.div`
  margin-left: auto;
  font-size: 11px;
  color: #9c9a92;
`;

interface AlertBarProps {
  tramites: Tramite[];
}

export const AlertBar = ({ tramites }: AlertBarProps) => {
  const activos = tramites.filter(
    (t) => !ESTADOS_FINALES.includes(t.estatus ?? ''),
  );

  const vencidos = activos.filter(
    (t) => getSemaforo(t.fechaLimiteSla, t.estatus) === 'rojo',
  ).length;

  const proximos = activos.filter(
    (t) => getSemaforo(t.fechaLimiteSla, t.estatus) === 'amarillo',
  ).length;

  // SLA promedio: avg of (fechaLimiteSla - fechaIngreso) for closed this month
  const now = new Date();
  const startMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const cerradosMes = tramites.filter(
    (t) =>
      ESTADOS_FINALES.includes(t.estatus ?? '') &&
      isDefined(t.fechaIngreso) &&
      parseISO(t.fechaIngreso) >= startMonth &&
      isDefined(t.fechaLimiteSla),
  );

  let slaPromedio = '—';
  if (cerradosMes.length > 0) {
    const totalDias = cerradosMes.reduce((sum, t) => {
      const dias = differenceInDays(
        parseISO(t.fechaLimiteSla!),
        parseISO(t.fechaIngreso!),
      );
      return sum + Math.max(0, dias);
    }, 0);
    slaPromedio = (totalDias / cerradosMes.length).toFixed(1) + 'd';
  }

  return (
    <StyledBar>
      <StyledPill data-type={vencidos > 0 ? 'rojo' : 'verde'}>
        {vencidos > 0 ? '🔴' : '🟢'} {vencidos} vencidos
      </StyledPill>
      <StyledPill data-type={proximos > 0 ? 'amarillo' : 'verde'}>
        {proximos > 0 ? '🟡' : '🟢'} {proximos} próximos a vencer
      </StyledPill>
      <StyledPill data-type="verde">🟢 SLA prom. mes: {slaPromedio}</StyledPill>
      <StyledSpacer>
        {now.toLocaleDateString('es-MX', {
          weekday: 'short',
          day: 'numeric',
          month: 'long',
          year: 'numeric',
        })}
      </StyledSpacer>
    </StyledBar>
  );
};
