import { styled } from '@linaria/react';
import { differenceInDays, parseISO } from 'date-fns';
import { useState } from 'react';
import { isDefined } from 'twenty-shared/utils';
import { AlertBar } from '../components/AlertBar';
import { KPICard } from '../components/KPICard';
import { SemaforoTable } from '../components/SemaforoTable';
import { TramiteDetailPanel } from '../components/TramiteDetailPanel';
import type { DashboardData, Member, Tramite } from '../types/dashboard.types';
import { ESTADOS_FINALES, getSemaforo } from '../utils/semaforo';

const StyledWrapper = styled.div`
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
`;

const StyledSelectorBar = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  background: #1a1d27;
  border-bottom: 1px solid #2a2d3a;
  flex-shrink: 0;
`;

const StyledSelectorLabel = styled.span`
  font-size: 12px;
  color: #9c9a92;
`;

const StyledSelect = styled.select`
  background: #0f1117;
  border: 1px solid #2a2d3a;
  color: #e8e6e1;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  min-width: 200px;
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

const StyledSummaryRow = styled.div`
  display: flex;
  gap: 32px;
  padding: 8px 0;
`;

const StyledSummaryItem = styled.div``;

const StyledSummaryNum = styled.div`
  font-size: 30px;
  font-weight: 700;
  color: #e8e6e1;
  line-height: 1;
`;

const StyledSummaryLabel = styled.div`
  font-size: 11px;
  color: #9c9a92;
  margin-top: 2px;
`;

const memberFullName = (m: Member) =>
  `${m.name.firstName} ${m.name.lastName}`.trim() || m.id;

const startOfMonth = () => {
  const d = new Date();
  d.setDate(1);
  d.setHours(0, 0, 0, 0);
  return d;
};

export const EspecialistaView = ({
  tramites,
  members,
}: DashboardData) => {
  const [selectedId, setSelectedId] = useState<string>(
    members[0]?.id ?? '',
  );
  const [detalle, setDetalle] = useState<Tramite | null>(null);

  const selectedMember = members.find((m) => m.id === selectedId) ?? null;
  const mis = tramites.filter(
    (t) => t.especialistaAsignado?.id === selectedId,
  );
  const activos = mis.filter(
    (t) => !ESTADOS_FINALES.includes(t.estadoTramite ?? ''),
  );

  // Vencen hoy
  const vencenHoy = activos.filter((t) => {
    if (!t.fechaLimiteSla) return false;
    const limite = new Date(t.fechaLimiteSla);
    const hoy = new Date();
    return (
      getSemaforo(t.fechaLimiteSla, t.estadoTramite) === 'rojo' &&
      limite.toDateString() === hoy.toDateString()
    );
  });

  const enRevision = activos.filter((t) => t.estadoTramite === 'EN_REVISION');
  const listosGnp = activos.filter(
    (t) => t.estadoTramite === 'LISTO_PARA_GNP',
  );

  const now = startOfMonth();
  const cerradosMes = mis.filter(
    (t) =>
      ESTADOS_FINALES.includes(t.estadoTramite ?? '') &&
      isDefined(t.fechaEntrada) &&
      parseISO(t.fechaEntrada) >= now,
  );
  const rechMes = mis.filter(
    (t) =>
      t.resultadoGnp === 'RECHAZADO' &&
      isDefined(t.fechaEntrada) &&
      parseISO(t.fechaEntrada) >= now,
  );

  const avgDias =
    cerradosMes.length > 0
      ? (
          cerradosMes.reduce((sum, t) => {
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
          }, 0) / cerradosMes.length
        ).toFixed(1) + 'd'
      : '—';

  return (
    <StyledWrapper>
      <StyledSelectorBar>
        <StyledSelectorLabel>Especialista:</StyledSelectorLabel>
        <StyledSelect
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
        >
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {memberFullName(m)}
            </option>
          ))}
        </StyledSelect>
        {selectedMember && (
          <span style={{ fontSize: 11, color: '#9c9a92' }}>
            {activos.length} trámites activos
          </span>
        )}
      </StyledSelectorBar>

      <AlertBar tramites={mis} />

      <StyledContent>
        <StyledKPIRow>
          <KPICard label="Mis trámites activos" value={activos.length} />
          <KPICard
            label="Vencen hoy"
            value={vencenHoy.length}
            color={vencenHoy.length > 0 ? 'rojo' : 'default'}
          />
          <KPICard label="En revisión" value={enRevision.length} color="azul" />
          <KPICard
            label="Listos para enviar a GNP"
            value={listosGnp.length}
            color="verde"
          />
        </StyledKPIRow>

        <StyledCard>
          <StyledCardTitle>
            Mis trámites activos — {activos.length} en total
          </StyledCardTitle>
          <SemaforoTable
            tramites={activos}
            columns={[
              'folio',
              'agenteTitular',
              'tipoTramite',
              'ramo',
              'estadoTramite',
              'fechaLimiteSla',
            ]}
            onRowClick={setDetalle}
          />
        </StyledCard>

        <StyledCard>
          <StyledCardTitle>Mi resumen — mes actual</StyledCardTitle>
          <StyledSummaryRow>
            <StyledSummaryItem>
              <StyledSummaryNum>{cerradosMes.length}</StyledSummaryNum>
              <StyledSummaryLabel>Cerrados este mes</StyledSummaryLabel>
            </StyledSummaryItem>
            <StyledSummaryItem>
              <StyledSummaryNum>{avgDias}</StyledSummaryNum>
              <StyledSummaryLabel>Prom. días resolución</StyledSummaryLabel>
            </StyledSummaryItem>
            <StyledSummaryItem>
              <StyledSummaryNum
                style={{ color: rechMes.length > 0 ? '#e05252' : '#e8e6e1' }}
              >
                {rechMes.length}
              </StyledSummaryNum>
              <StyledSummaryLabel>Rechazados GNP</StyledSummaryLabel>
            </StyledSummaryItem>
          </StyledSummaryRow>
        </StyledCard>
      </StyledContent>

      <TramiteDetailPanel
        tramite={detalle}
        onClose={() => setDetalle(null)}
      />
    </StyledWrapper>
  );
};
