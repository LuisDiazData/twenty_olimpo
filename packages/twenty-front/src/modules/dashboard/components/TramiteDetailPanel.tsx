import { styled } from '@linaria/react';
import { format, parseISO } from 'date-fns';
import { ESTADO_LABEL, RAMO_COLORS, TIPO_LABEL } from '../constants/colors';
import type { Tramite } from '../types/dashboard.types';
import { SEMAFORO_HEX, SEMAFORO_LABEL, getSemaforo } from '../utils/semaforo';

interface TramiteDetailPanelProps {
  tramite: Tramite | null;
  onClose: () => void;
}

const StyledOverlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 200;
  display: flex;
  justify-content: flex-end;
`;

const StyledPanel = styled.div`
  width: 380px;
  background: #1a1d27;
  border-left: 1px solid #2a2d3a;
  height: 100%;
  overflow-y: auto;
  padding: 24px 20px;
`;

const StyledHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
`;

const StyledTitle = styled.h2`
  font-size: 16px;
  font-weight: 700;
  color: #e8e6e1;
  margin: 0;
  font-family: monospace;
`;

const StyledClose = styled.button`
  background: none;
  border: none;
  color: #9c9a92;
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;

  &:hover {
    color: #e8e6e1;
  }
`;

const StyledBadgeRow = styled.div`
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 20px;
`;

const StyledBadge = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
`;

const StyledDivider = styled.div`
  height: 1px;
  background: #2a2d3a;
  margin: 16px 0;
`;

const StyledField = styled.div`
  margin-bottom: 12px;
`;

const StyledFieldLabel = styled.div`
  font-size: 10px;
  color: #9c9a92;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 2px;
`;

const StyledFieldValue = styled.div`
  font-size: 13px;
  color: #e8e6e1;
`;

const StyledLink = styled.a`
  font-size: 12px;
  color: #378add;
  text-decoration: none;
  display: inline-block;
  margin-top: 12px;

  &:hover {
    text-decoration: underline;
  }
`;

const formatDate = (d: string | null) => {
  if (!d) return '—';
  try {
    return format(parseISO(d), "dd 'de' MMMM 'de' yyyy");
  } catch {
    return d;
  }
};

const memberFullName = (
  m: { name: { firstName: string; lastName: string } } | null,
) => {
  if (!m) return '—';
  return `${m.name.firstName} ${m.name.lastName}`.trim() || '—';
};

const estadoColor: Record<string, { bg: string; color: string }> = {
  PENDIENTE: { bg: 'rgba(156,154,146,.15)', color: '#9c9a92' },
  EN_REVISION: { bg: 'rgba(24,95,165,.2)', color: '#5fa8e8' },
  LISTO_PARA_GNP: { bg: 'rgba(186,117,23,.2)', color: '#e6a020' },
  ENVIADO_A_GNP: { bg: 'rgba(24,95,165,.2)', color: '#5fa8e8' },
  APROBADO_GNP: { bg: 'rgba(29,158,117,.2)', color: '#22c78a' },
  RECHAZADO_GNP: { bg: 'rgba(163,45,45,.2)', color: '#e05252' },
  CERRADO: { bg: 'rgba(156,154,146,.15)', color: '#9c9a92' },
};

export const TramiteDetailPanel = ({
  tramite,
  onClose,
}: TramiteDetailPanelProps) => {
  if (!tramite) return null;

  const sem = getSemaforo(tramite.fechaLimiteSla, tramite.estadoTramite);
  const estilo = estadoColor[tramite.estadoTramite ?? ''] ?? {
    bg: 'rgba(156,154,146,.15)',
    color: '#9c9a92',
  };

  return (
    <StyledOverlay onClick={onClose}>
      <StyledPanel onClick={(e) => e.stopPropagation()}>
        <StyledHeader>
          <StyledTitle>{tramite.folioInterno ?? tramite.name}</StyledTitle>
          <StyledClose onClick={onClose}>✕</StyledClose>
        </StyledHeader>

        <StyledBadgeRow>
          <StyledBadge
            style={{ background: estilo.bg, color: estilo.color }}
          >
            {ESTADO_LABEL[tramite.estadoTramite ?? ''] ?? tramite.estadoTramite ?? '—'}
          </StyledBadge>
          <StyledBadge
            style={{
              background:
                sem === 'rojo'
                  ? 'rgba(163,45,45,.25)'
                  : sem === 'amarillo'
                    ? 'rgba(186,117,23,.25)'
                    : 'rgba(29,158,117,.2)',
              color: SEMAFORO_HEX[sem],
            }}
          >
            {SEMAFORO_LABEL[sem]}
          </StyledBadge>
        </StyledBadgeRow>

        <StyledField>
          <StyledFieldLabel>Ramo</StyledFieldLabel>
          <StyledFieldValue>
            {tramite.ramo && (
              <span
                style={{
                  display: 'inline-block',
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  backgroundColor: RAMO_COLORS[tramite.ramo],
                  marginRight: 6,
                }}
              />
            )}
            {tramite.ramo ?? '—'}
          </StyledFieldValue>
        </StyledField>

        <StyledField>
          <StyledFieldLabel>Tipo de trámite</StyledFieldLabel>
          <StyledFieldValue>
            {TIPO_LABEL[tramite.tipoTramite ?? ''] ?? tramite.tipoTramite ?? '—'}
          </StyledFieldValue>
        </StyledField>

        <StyledDivider />

        <StyledField>
          <StyledFieldLabel>Agente titular</StyledFieldLabel>
          <StyledFieldValue>
            {tramite.agenteTitular?.name ?? '—'}
          </StyledFieldValue>
        </StyledField>

        <StyledField>
          <StyledFieldLabel>Especialista asignado</StyledFieldLabel>
          <StyledFieldValue>
            {memberFullName(tramite.especialistaAsignado)}
          </StyledFieldValue>
        </StyledField>

        <StyledField>
          <StyledFieldLabel>Asegurado</StyledFieldLabel>
          <StyledFieldValue>
            {tramite.nombreAsegurado ?? '—'}
          </StyledFieldValue>
        </StyledField>

        <StyledDivider />

        <StyledField>
          <StyledFieldLabel>No. póliza GNP</StyledFieldLabel>
          <StyledFieldValue>
            {tramite.numPolizaGnp || '—'}
          </StyledFieldValue>
        </StyledField>

        <StyledField>
          <StyledFieldLabel>Resultado GNP</StyledFieldLabel>
          <StyledFieldValue>
            {tramite.resultadoGnp ?? '—'}
          </StyledFieldValue>
        </StyledField>

        <StyledDivider />

        <StyledField>
          <StyledFieldLabel>Fecha de entrada</StyledFieldLabel>
          <StyledFieldValue>
            {formatDate(tramite.fechaEntrada)}
          </StyledFieldValue>
        </StyledField>

        <StyledField>
          <StyledFieldLabel>Fecha límite SLA</StyledFieldLabel>
          <StyledFieldValue>
            {formatDate(tramite.fechaLimiteSla)}
          </StyledFieldValue>
        </StyledField>

        {tramite.notasAnalista && (
          <>
            <StyledDivider />
            <StyledField>
              <StyledFieldLabel>Notas del analista</StyledFieldLabel>
              <StyledFieldValue
                style={{ color: '#9c9a92', lineHeight: 1.5, fontSize: 12 }}
              >
                {tramite.notasAnalista}
              </StyledFieldValue>
            </StyledField>
          </>
        )}

        <StyledLink
          href={`/object/tramite/${tramite.id}`}
          onClick={(e) => e.stopPropagation()}
        >
          Ver registro completo en Twenty →
        </StyledLink>
      </StyledPanel>
    </StyledOverlay>
  );
};
