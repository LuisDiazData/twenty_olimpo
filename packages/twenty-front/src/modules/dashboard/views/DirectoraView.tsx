import { styled } from '@linaria/react';
import { parseISO } from 'date-fns';
import { useState } from 'react';
import { isDefined } from 'twenty-shared/utils';
import { AlertBar } from '../components/AlertBar';
import { BarrasIngresoVsCierre } from '../components/BarrasIngresoVsCierre';
import { CargaBar } from '../components/CargaBar';
import { DonaRamo } from '../components/DonaRamo';
import { KPICard } from '../components/KPICard';
import { RechazosChart } from '../components/RechazosChart';
import { SemaforoTable } from '../components/SemaforoTable';
import { TendenciaLine } from '../components/TendenciaLine';
import { TramiteDetailPanel } from '../components/TramiteDetailPanel';
import { RAMOS } from '../constants/colors';
import type { DashboardData, Tramite } from '../types/dashboard.types';
import { ESTADOS_FINALES, getSemaforo } from '../utils/semaforo';

const StyledContent = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const StyledKPIRow = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
`;

const StyledRow = styled.div`
  display: flex;
  gap: 12px;
  align-items: stretch;
`;

const StyledCard = styled.div`
  background: #1a1d27;
  border: 1px solid #2a2d3a;
  border-radius: 10px;
  padding: 16px;
`;

const StyledCardTitle = styled.div`
  font-size: 10px;
  font-weight: 600;
  color: #9c9a92;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 12px;
`;

const StyledSlaTable = styled.table`
  width: 100%;
  border-collapse: collapse;
`;

const StyledSlaTh = styled.th`
  font-size: 10px;
  color: #9c9a92;
  font-weight: 600;
  text-align: left;
  padding: 4px 8px;
  border-bottom: 1px solid #2a2d3a;
  text-transform: uppercase;
`;

const StyledSlaTd = styled.td`
  padding: 6px 8px;
  font-size: 12px;
`;

const StyledSlaTr = styled.tr`
  &[data-color='verde'] td {
    background: rgba(29, 158, 117, 0.07);
  }
  &[data-color='amarillo'] td {
    background: rgba(186, 117, 23, 0.08);
  }
  &[data-color='rojo'] td {
    background: rgba(163, 45, 45, 0.1);
  }
`;

const startOfMonth = (offset = 0) => {
  const d = new Date();
  d.setDate(1);
  d.setHours(0, 0, 0, 0);
  d.setMonth(d.getMonth() + offset);
  return d;
};

const calcTrend = (curr: number, prev: number, lowerIsBetter = false) => {
  if (curr === prev) return { dir: 'igual' as const, label: '= vs mes ant.' };
  if (curr > prev) {
    return {
      dir: 'sube' as const,
      label: `+${curr - prev} vs mes ant.`,
    };
  }
  return {
    dir: 'baja' as const,
    label: `-${prev - curr} vs mes ant.`,
  };
};

export const DirectoraView = ({
  tramites,
  razones,
  members,
}: DashboardData) => {
  const [detalle, setDetalle] = useState<Tramite | null>(null);

  const now = startOfMonth(0);
  const prevMonth = startOfMonth(-1);
  const nextMonth = startOfMonth(1);

  const activos = tramites.filter(
    (t) => !ESTADOS_FINALES.includes(t.estadoTramite ?? ''),
  );
  const thisMes = tramites.filter(
    (t) => isDefined(t.fechaEntrada) && parseISO(t.fechaEntrada) >= now,
  );
  const lastMes = tramites.filter(
    (t) =>
      isDefined(t.fechaEntrada) &&
      parseISO(t.fechaEntrada) >= prevMonth &&
      parseISO(t.fechaEntrada) < now,
  );
  const cerradosMes = tramites.filter(
    (t) =>
      ESTADOS_FINALES.includes(t.estadoTramite ?? '') &&
      t.fechaEntrada &&
      parseISO(t.fechaEntrada) >= now,
  );
  const cerradosPrev = tramites.filter(
    (t) =>
      ESTADOS_FINALES.includes(t.estadoTramite ?? '') &&
      isDefined(t.fechaEntrada) &&
      parseISO(t.fechaEntrada) >= prevMonth &&
      parseISO(t.fechaEntrada) < now,
  );
  const rechazadosMes = tramites.filter(
    (t) =>
      t.resultadoGnp === 'RECHAZADO' &&
      t.fechaEntrada &&
      parseISO(t.fechaEntrada) >= now,
  );
  const rechazadosPrev = tramites.filter(
    (t) =>
      t.resultadoGnp === 'RECHAZADO' &&
      isDefined(t.fechaEntrada) &&
      parseISO(t.fechaEntrada) >= prevMonth &&
      parseISO(t.fechaEntrada) < now,
  );

  const activosPrev = tramites.filter(
    (t) =>
      !ESTADOS_FINALES.includes(t.estadoTramite ?? '') &&
      isDefined(t.fechaEntrada) &&
      parseISO(t.fechaEntrada) >= prevMonth &&
      parseISO(t.fechaEntrada) < now,
  );

  const trendActivos = calcTrend(activos.length, activosPrev.length);
  const trendIngreso = calcTrend(thisMes.length, lastMes.length);
  const trendCerrados = calcTrend(cerradosMes.length, cerradosPrev.length);
  const trendRechazados = calcTrend(
    rechazadosMes.length,
    rechazadosPrev.length,
    true,
  );

  // SLA por ramo table
  const slaRamo = RAMOS.map((ramo) => {
    const act = activos.filter((t) => t.ramo === ramo);
    const venc = act.filter(
      (t) => getSemaforo(t.fechaLimiteSla, t.estadoTramite) === 'rojo',
    ).length;
    return {
      ramo,
      activos: act.length,
      vencidos: venc,
      pct: act.length ? Math.round((venc / act.length) * 100) : 0,
    };
  }).filter((r) => r.activos > 0);

  const slaColor = (v: number): 'verde' | 'amarillo' | 'rojo' =>
    v === 0 ? 'verde' : v <= 3 ? 'amarillo' : 'rojo';

  return (
    <>
      <AlertBar tramites={tramites} />
      <StyledContent>
        <StyledKPIRow>
          <KPICard
            label="Trámites activos"
            value={activos.length}
            tendencia={trendActivos.dir}
            tendenciaLabel={trendActivos.label}
          />
          <KPICard
            label="Ingresaron este mes"
            value={thisMes.length}
            tendencia={trendIngreso.dir}
            tendenciaLabel={trendIngreso.label}
          />
          <KPICard
            label="Cerrados este mes"
            value={cerradosMes.length}
            tendencia={trendCerrados.dir}
            tendenciaLabel={trendCerrados.label}
          />
          <KPICard
            label="Rechazados GNP este mes"
            value={rechazadosMes.length}
            color={rechazadosMes.length > 0 ? 'rojo' : 'default'}
            tendencia={trendRechazados.dir}
            tendenciaLabel={trendRechazados.label}
            lowerIsBetter
          />
        </StyledKPIRow>

        <StyledRow>
          <StyledCard style={{ width: '27%' }}>
            <StyledCardTitle>Activos por ramo</StyledCardTitle>
            <DonaRamo tramites={tramites} />
          </StyledCard>

          <StyledCard style={{ flex: 1 }}>
            <StyledCardTitle>Ingreso vs Cierre — últimos 6 meses</StyledCardTitle>
            <BarrasIngresoVsCierre tramites={tramites} meses={6} />
          </StyledCard>

          <StyledCard style={{ width: '23%' }}>
            <StyledCardTitle>SLA por ramo</StyledCardTitle>
            {slaRamo.length === 0 ? (
              <div style={{ color: '#9c9a92', textAlign: 'center', padding: 16 }}>
                Sin activos
              </div>
            ) : (
              <StyledSlaTable>
                <thead>
                  <tr>
                    <StyledSlaTh>Ramo</StyledSlaTh>
                    <StyledSlaTh>Act.</StyledSlaTh>
                    <StyledSlaTh>Venc.</StyledSlaTh>
                    <StyledSlaTh>%</StyledSlaTh>
                  </tr>
                </thead>
                <tbody>
                  {slaRamo.map((r) => (
                    <StyledSlaTr
                      key={r.ramo}
                      data-color={slaColor(r.vencidos)}
                    >
                      <StyledSlaTd>{r.ramo}</StyledSlaTd>
                      <StyledSlaTd>{r.activos}</StyledSlaTd>
                      <StyledSlaTd>{r.vencidos}</StyledSlaTd>
                      <StyledSlaTd>{r.pct}%</StyledSlaTd>
                    </StyledSlaTr>
                  ))}
                </tbody>
              </StyledSlaTable>
            )}
          </StyledCard>
        </StyledRow>

        <StyledRow>
          <StyledCard style={{ width: '40%' }}>
            <StyledCardTitle>Top razones de rechazo GNP</StyledCardTitle>
            <RechazosChart razonesRechazo={razones} />
          </StyledCard>

          <StyledCard style={{ flex: 1 }}>
            <StyledCardTitle>
              Tiempo promedio de resolución (días) — últimos 6 meses
            </StyledCardTitle>
            <TendenciaLine tramites={tramites} meses={6} />
          </StyledCard>
        </StyledRow>

        <StyledRow>
          <StyledCard style={{ flex: 1 }}>
            <StyledCardTitle>Trámites urgentes (vencidos + próximos)</StyledCardTitle>
            <SemaforoTable
              tramites={activos.filter((t) =>
                ['rojo', 'amarillo'].includes(
                  getSemaforo(t.fechaLimiteSla, t.estadoTramite),
                ),
              )}
              columns={[
                'folio',
                'agenteTitular',
                'ramo',
                'estadoTramite',
                'especialistaAsignado',
                'fechaLimiteSla',
              ]}
              onRowClick={setDetalle}
            />
          </StyledCard>
        </StyledRow>
      </StyledContent>

      <TramiteDetailPanel tramite={detalle} onClose={() => setDetalle(null)} />
    </>
  );
};
