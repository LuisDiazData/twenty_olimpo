import { styled } from '@linaria/react';
import { parseISO } from 'date-fns';
import { useState } from 'react';
import { isDefined } from 'twenty-shared/utils';
import { AlertBar } from '../components/AlertBar';
import { BarrasIngresoVsCierre } from '../components/BarrasIngresoVsCierre';
import { CargaBar } from '../components/CargaBar';
import { DonaRamo } from '../components/DonaRamo';
import { FunnelChart } from '../components/FunnelChart';
import { KPICard } from '../components/KPICard';
import { ProductividadRamoChart } from '../components/ProductividadRamoChart';
import { RankingAgentes } from '../components/RankingAgentes';
import { RechazosChart } from '../components/RechazosChart';

import { SemaforoTable } from '../components/SemaforoTable';
import { TendenciaLine } from '../components/TendenciaLine';
import { TramiteDetailPanel } from '../components/TramiteDetailPanel';
import { RAMOS } from '../constants/colors';
import type { DashboardData, Tramite } from '../types/dashboard.types';
import { ESTADOS_FINALES, getSemaforo } from '../utils/semaforo';

// ─── Styled components ────────────────────────────────────────────────────────

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

// ─── Helpers ──────────────────────────────────────────────────────────────────

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
    return { dir: 'sube' as const, label: `+${curr - prev} vs mes ant.` };
  }
  return { dir: 'baja' as const, label: `-${prev - curr} vs mes ant.` };
};

const formatMXN = (val: number) =>
  new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    maximumFractionDigits: 0,
  }).format(val);

// ─── Component ────────────────────────────────────────────────────────────────

export const DirectoraView = ({
  tramites,
  motivosRechazo,
  members,
  kpiSnapshots,
  agentPerformance,
  agentes,
  filters,
}: DashboardData) => {
  const [detalle, setDetalle] = useState<Tramite | null>(null);

  const now = startOfMonth(0);
  const prevMonth = startOfMonth(-1);

  // ── Métricas básicas ──────────────────────────────────────────────────────
  const activos = tramites.filter(
    (t) => !ESTADOS_FINALES.includes(t.estatus ?? ''),
  );
  const thisMes = tramites.filter(
    (t) => isDefined(t.fechaIngreso) && parseISO(t.fechaIngreso) >= now,
  );
  const lastMes = tramites.filter(
    (t) =>
      isDefined(t.fechaIngreso) &&
      parseISO(t.fechaIngreso) >= prevMonth &&
      parseISO(t.fechaIngreso) < now,
  );
  const cerradosMes = tramites.filter(
    (t) =>
      ESTADOS_FINALES.includes(t.estatus ?? '') &&
      t.fechaIngreso &&
      parseISO(t.fechaIngreso) >= now,
  );
  const cerradosPrev = tramites.filter(
    (t) =>
      ESTADOS_FINALES.includes(t.estatus ?? '') &&
      isDefined(t.fechaIngreso) &&
      parseISO(t.fechaIngreso) >= prevMonth &&
      parseISO(t.fechaIngreso) < now,
  );
  // "Cancelado" equivale a rechazado/no resuelto en el flujo de la promotoría
  const rechazadosMes = tramites.filter(
    (t) =>
      t.estatus === 'CANCELADO' &&
      t.fechaIngreso &&
      parseISO(t.fechaIngreso) >= now,
  );
  const rechazadosPrev = tramites.filter(
    (t) =>
      t.estatus === 'CANCELADO' &&
      isDefined(t.fechaIngreso) &&
      parseISO(t.fechaIngreso) >= prevMonth &&
      parseISO(t.fechaIngreso) < now,
  );
  const activosPrev = tramites.filter(
    (t) =>
      !ESTADOS_FINALES.includes(t.estatus ?? '') &&
      isDefined(t.fechaIngreso) &&
      parseISO(t.fechaIngreso) >= prevMonth &&
      parseISO(t.fechaIngreso) < now,
  );

  const trendActivos = calcTrend(activos.length, activosPrev.length);
  const trendIngreso = calcTrend(thisMes.length, lastMes.length);
  const trendCerrados = calcTrend(cerradosMes.length, cerradosPrev.length);
  const trendRechazados = calcTrend(rechazadosMes.length, rechazadosPrev.length, true);

  // ── SLA por ramo table (existente) ────────────────────────────────────────
  const slaVencidosTotal = activos.filter(
    (t) => getSemaforo(t.fechaLimiteSla, t.estatus) === 'rojo',
  ).length;

  const slaRamo = RAMOS.map((ramo) => {
    const act = activos.filter((t) => t.ramo === ramo);
    const venc = act.filter(
      (t) => getSemaforo(t.fechaLimiteSla, t.estatus) === 'rojo',
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

  // ── Nuevas métricas estratégicas ──────────────────────────────────────────

  // SLA Global %
  const slaGlobalKpi = kpiSnapshots.find(
    (k) => k.metricaNombre === 'SLA_Compliance_Global',
  );
  const slaGlobalVal = slaGlobalKpi?.valor
    ?? (activos.length
      ? Math.round(((activos.length - slaVencidosTotal) / activos.length) * 100)
      : 100);
  const slaGlobalColor =
    slaGlobalVal >= 95 ? 'verde' : slaGlobalVal >= 85 ? 'amarillo' : 'rojo';

  // Prima Emitida Total
  const primaTotal = agentPerformance.reduce(
    (s, a) => s + (a.primaEmitida ?? 0),
    0,
  );

  // First Pass Yield %
  const fpyKpi = kpiSnapshots.find((k) => k.metricaNombre === 'First_Pass_Yield');
  const fpyVal = fpyKpi?.valor
    ?? (cerradosMes.length
      ? Math.round(
          ((cerradosMes.length - rechazadosMes.length) / cerradosMes.length) *
            100,
        )
      : 100);
  const fpyColor = fpyVal >= 80 ? 'verde' : fpyVal >= 60 ? 'amarillo' : 'rojo';

  // Alertas de Cédula (vencen en 60 días)
  const hoy = new Date();
  const limite60 = new Date(hoy.getTime() + 60 * 24 * 60 * 60 * 1000);
  const alertasCedula = agentes.filter((a) => {
    if (!a.fechaVencimientoCedula) return false;
    const vence = parseISO(a.fechaVencimientoCedula);
    return vence <= limite60;
  }).length;

  const periodLabel =
    filters.periodo === 'mes'
      ? 'Este mes'
      : filters.periodo === 'trimestre'
        ? 'Último trimestre'
        : 'Este año';

  return (
    <>
      <AlertBar tramites={tramites} />
      <StyledContent>

        {/* ── KPI Row 1: Métricas operativas ────────────────────────────── */}
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

        {/* ── KPI Row 2: Métricas estratégicas ──────────────────────────── */}
        <StyledKPIRow>
          <KPICard
            label="SLA Global"
            value={`${slaGlobalVal}%`}
            sublabel="Meta: 95%"
            color={slaGlobalColor}
          />
          <KPICard
            label="Prima Emitida"
            value={primaTotal > 0 ? formatMXN(primaTotal) : '—'}
            sublabel={periodLabel}
            color="azul"
          />
          <KPICard
            label="First Pass Yield"
            value={`${fpyVal}%`}
            sublabel="Sin rechazo en 1er intento"
            color={fpyColor}
          />
          <KPICard
            label="Alertas de Cédula"
            value={alertasCedula}
            sublabel="Vencen en 60 días"
            color={alertasCedula > 0 ? 'rojo' : 'verde'}
          />
        </StyledKPIRow>

        {/* ── Row 3: Dona + Barras + SLA por ramo ──────────────────────── */}
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
                    <StyledSlaTr key={r.ramo} data-color={slaColor(r.vencidos)}>
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

        {/* ── Row 4: Embudo operacional + Productividad por ramo ────────── */}
        <StyledRow>
          <StyledCard style={{ flex: '0 0 44%' }}>
            <StyledCardTitle>Embudo de Operación</StyledCardTitle>
            <FunnelChart tramites={tramites} />
          </StyledCard>

          <StyledCard style={{ flex: 1 }}>
            <StyledCardTitle>Productividad por Ramo</StyledCardTitle>
            <ProductividadRamoChart tramites={tramites} />
          </StyledCard>
        </StyledRow>

        {/* ── Row 5: Rechazos + Tendencia resolución ────────────────────── */}
        <StyledRow>
          <StyledCard style={{ width: '40%' }}>
            <StyledCardTitle>Top razones de rechazo GNP</StyledCardTitle>
            <RechazosChart razonesRechazo={motivosRechazo} />
          </StyledCard>

          <StyledCard style={{ flex: 1 }}>
            <StyledCardTitle>
              Tiempo promedio de resolución (días) — últimos 6 meses
            </StyledCardTitle>
            <TendenciaLine tramites={tramites} meses={6} />
          </StyledCard>
        </StyledRow>

        {/* ── Row 6: Ranking agentes + Semáforo urgentes ────────────────── */}
        <StyledRow>
          <StyledCard style={{ flex: '0 0 40%' }}>
            <StyledCardTitle>Top 5 Agentes — {periodLabel}</StyledCardTitle>
            <RankingAgentes
              agentPerformance={agentPerformance}
              kpiSnapshots={kpiSnapshots}
              tramites={tramites}
            />
          </StyledCard>

          <StyledCard style={{ flex: 1 }}>
            <StyledCardTitle>Trámites urgentes (vencidos + próximos)</StyledCardTitle>
            <SemaforoTable
              tramites={activos.filter((t) =>
                ['rojo', 'amarillo'].includes(
                  getSemaforo(t.fechaLimiteSla, t.estatus),
                ),
              )}
              columns={[
                'folio',
                'agente',
                'ramo',
                'estatus',
                'analistaAsignado',
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
