import { styled } from '@linaria/react';
import { differenceInDays, parseISO } from 'date-fns';
import { isDefined } from 'twenty-shared/utils';
import { useState } from 'react';
import { AlertBar } from '../components/AlertBar';
import { CargaBar } from '../components/CargaBar';
import { KPICard } from '../components/KPICard';
import { RechazosChart } from '../components/RechazosChart';
import { SemaforoTable } from '../components/SemaforoTable';
import { TramiteDetailPanel } from '../components/TramiteDetailPanel';
import { RAMO_COLORS, RAMOS } from '../constants/colors';
import type { DashboardData, Tramite } from '../types/dashboard.types';
import { ESTADOS_FINALES, getSemaforo } from '../utils/semaforo';

const StyledWrapper = styled.div`
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
`;

const StyledTabs = styled.div`
  display: flex;
  gap: 4px;
  padding: 10px 20px 0;
  background: #1a1d27;
  border-bottom: 1px solid #2a2d3a;
  flex-shrink: 0;
`;

const StyledTab = styled.button`
  background: none;
  border: none;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 600;
  color: #9c9a92;
  cursor: pointer;
  border-radius: 6px 6px 0 0;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;

  &:hover {
    color: #e8e6e1;
  }

  &[data-active='true'] {
    color: #e8e6e1;
    border-bottom-color: #1d9e75;
  }
`;

const StyledRamoDot = styled.span`
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 5px;
`;

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

const StyledAgentTable = styled.table`
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
`;
const StyledTd = styled.td`
  padding: 6px 8px;
  font-size: 12px;
  color: #e8e6e1;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
`;
const StyledBadge = styled.span`
  display: inline-flex;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
`;

const startOfMonth = (offset = 0) => {
  const d = new Date();
  d.setDate(1);
  d.setHours(0, 0, 0, 0);
  d.setMonth(d.getMonth() + offset);
  return d;
};

const pctBadge = (pct: number) => {
  if (pct > 15) return { bg: 'rgba(163,45,45,.25)', color: '#e05252' };
  if (pct > 5) return { bg: 'rgba(186,117,23,.25)', color: '#e6a020' };
  return { bg: 'rgba(29,158,117,.2)', color: '#22c78a' };
};

export const GerenteView = ({
  tramites,
  razones,
  members,
}: DashboardData) => {
  const [ramo, setRamo] = useState<string>('VIDA');
  const [detalle, setDetalle] = useState<Tramite | null>(null);

  const filtered = tramites.filter((t) => t.ramo === ramo);
  const activos = filtered.filter(
    (t) => !ESTADOS_FINALES.includes(t.estadoTramite ?? ''),
  );
  const proximos48 = activos.filter(
    (t) => getSemaforo(t.fechaLimiteSla, t.estadoTramite) === 'amarillo',
  );
  const vencidos = activos.filter(
    (t) => getSemaforo(t.fechaLimiteSla, t.estadoTramite) === 'rojo',
  );
  const urgentes = [...vencidos, ...proximos48];

  const now = startOfMonth(0);
  const rechMes = filtered.filter(
    (t) =>
      t.resultadoGnp === 'RECHAZADO' &&
      isDefined(t.fechaEntrada) &&
      parseISO(t.fechaEntrada) >= now,
  );

  const cerrados = filtered.filter((t) =>
    ESTADOS_FINALES.includes(t.estadoTramite ?? ''),
  );
  const avgDias =
    cerrados.length > 0
      ? (
          cerrados.reduce((sum, t) => {
            if (!t.fechaEntrada || !t.fechaLimiteSla) return sum;
            return (
              sum +
              Math.max(
                0,
                differenceInDays(
                  parseISO(t.fechaLimiteSla),
                  parseISO(t.fechaEntrada),
                ),
              )
            );
          }, 0) / cerrados.length
        ).toFixed(1) + 'd'
      : '—';

  // Agentes con rechazos en este ramo
  const agenteStats: Record<
    string,
    { name: string; total: number; rechazados: number }
  > = {};
  filtered.forEach((t) => {
    const id = t.agenteTitular?.id ?? '?';
    const nm = t.agenteTitular?.name ?? 'Desconocido';
    if (!isDefined(agenteStats[id])) agenteStats[id] = { name: nm, total: 0, rechazados: 0 };
    agenteStats[id].total++;
    if (t.resultadoGnp === 'RECHAZADO') agenteStats[id].rechazados++;
  });
  const agenteList = Object.values(agenteStats)
    .filter((a) => a.rechazados > 0)
    .sort((a, b) => b.rechazados - a.rechazados);

  return (
    <StyledWrapper>
      <StyledTabs>
        {RAMOS.map((r) => (
          <StyledTab
            key={r}
            data-active={String(r === ramo)}
            onClick={() => setRamo(r)}
          >
            <StyledRamoDot
              style={{ backgroundColor: RAMO_COLORS[r] }}
            />
            {r}
          </StyledTab>
        ))}
      </StyledTabs>

      <AlertBar tramites={filtered} />

      <StyledContent>
        <StyledKPIRow>
          <KPICard label={`Activos — ${ramo}`} value={activos.length} />
          <KPICard
            label="Vencen próximas 48 hrs"
            value={proximos48.length}
            color={proximos48.length > 3 ? 'rojo' : proximos48.length > 0 ? 'amarillo' : 'default'}
          />
          <KPICard
            label="Rechazados GNP este mes"
            value={rechMes.length}
            color={rechMes.length > 0 ? 'rojo' : 'default'}
          />
          <KPICard label="Tiempo prom. resolución" value={avgDias} />
        </StyledKPIRow>

        <StyledRow>
          <StyledCard style={{ width: '42%' }}>
            <StyledCardTitle>Carga por especialista</StyledCardTitle>
            <CargaBar tramites={activos} members={members} />
          </StyledCard>

          <StyledCard style={{ flex: 1 }}>
            <StyledCardTitle>
              Urgentes (vencidos + próximas 48 hrs) — {urgentes.length}
            </StyledCardTitle>
            <SemaforoTable
              tramites={urgentes}
              columns={[
                'folio',
                'agenteTitular',
                'tipoTramite',
                'especialistaAsignado',
                'fechaLimiteSla',
              ]}
              onRowClick={setDetalle}
            />
          </StyledCard>
        </StyledRow>

        <StyledRow>
          <StyledCard style={{ width: '45%' }}>
            <StyledCardTitle>Top razones de rechazo — {ramo}</StyledCardTitle>
            <RechazosChart razonesRechazo={razones} filterRamo={ramo} />
          </StyledCard>

          <StyledCard style={{ flex: 1 }}>
            <StyledCardTitle>
              Agentes con más rechazos GNP — {ramo}
            </StyledCardTitle>
            {agenteList.length === 0 ? (
              <div
                style={{ color: '#9c9a92', textAlign: 'center', padding: 16 }}
              >
                Sin rechazos en este ramo
              </div>
            ) : (
              <StyledAgentTable>
                <thead>
                  <tr>
                    <StyledTh>Agente</StyledTh>
                    <StyledTh>Trámites</StyledTh>
                    <StyledTh>Rechazados</StyledTh>
                    <StyledTh>% rechazo</StyledTh>
                  </tr>
                </thead>
                <tbody>
                  {agenteList.map((a) => {
                    const pct = a.total
                      ? Math.round((a.rechazados / a.total) * 100)
                      : 0;
                    const badge = pctBadge(pct);
                    return (
                      <tr key={a.name}>
                        <StyledTd>{a.name}</StyledTd>
                        <StyledTd>{a.total}</StyledTd>
                        <StyledTd>{a.rechazados}</StyledTd>
                        <StyledTd>
                          <StyledBadge
                            style={{
                              background: badge.bg,
                              color: badge.color,
                            }}
                          >
                            {pct}%
                          </StyledBadge>
                        </StyledTd>
                      </tr>
                    );
                  })}
                </tbody>
              </StyledAgentTable>
            )}
          </StyledCard>
        </StyledRow>
      </StyledContent>

      <TramiteDetailPanel
        tramite={detalle}
        onClose={() => setDetalle(null)}
      />
    </StyledWrapper>
  );
};
