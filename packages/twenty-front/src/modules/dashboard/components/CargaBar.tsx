import { styled } from '@linaria/react';
import type { Member, Tramite } from '../types/dashboard.types';
import { ESTADOS_FINALES, getSemaforo } from '../utils/semaforo';

interface CargaBarProps {
  tramites: Tramite[];
  members: Member[];
  onSelectMember?: (member: Member) => void;
}

const StyledRow = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const StyledItem = styled.div`
  cursor: pointer;
  padding: 2px 0;

  &:hover .carga-label {
    color: #e8e6e1;
  }
`;

const StyledHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
`;

const StyledName = styled.span`
  font-size: 12px;
  color: #9c9a92;
  transition: color 0.1s;
`;

const StyledCount = styled.span`
  font-size: 11px;
  color: #9c9a92;
`;

const StyledBarTrack = styled.div`
  height: 8px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  overflow: hidden;
`;

const StyledBarFill = styled.div`
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
`;

const memberFullName = (m: Member) =>
  `${m.name.firstName} ${m.name.lastName}`.trim() || m.id;

export const CargaBar = ({
  tramites,
  members,
  onSelectMember,
}: CargaBarProps) => {
  const activos = tramites.filter(
    (t) => !ESTADOS_FINALES.includes(t.estatus ?? ''),
  );

  const stats = members.map((m) => {
    const misTramites = activos.filter(
      (t) => t.analistaAsignado?.id === m.id,
    );
    const vencidos = misTramites.filter(
      (t) => getSemaforo(t.fechaLimiteSla, t.estatus) === 'rojo',
    ).length;
    return { member: m, count: misTramites.length, vencidos };
  });

  const maxCount = Math.max(...stats.map((s) => s.count), 1);

  // Include all members, even those with 0 tramites
  const sorted = [...stats].sort((a, b) => b.count - a.count);

  const barColor = (n: number): string => {
    if (n > 15) return '#A32D2D';
    if (n > 9) return '#BA7517';
    return '#1D9E75';
  };

  if (sorted.length === 0) {
    return (
      <div style={{ color: '#9c9a92', textAlign: 'center', padding: '24px 0' }}>
        Sin especialistas
      </div>
    );
  }

  return (
    <StyledRow>
      {sorted.map(({ member, count, vencidos }) => (
        <StyledItem key={member.id} onClick={() => onSelectMember?.(member)}>
          <StyledHeader>
            <StyledName className="carga-label">
              {vencidos > 0 ? '⚠ ' : ''}
              {memberFullName(member)}
            </StyledName>
            <StyledCount>{count} trámites</StyledCount>
          </StyledHeader>
          <StyledBarTrack>
            <StyledBarFill
              style={{
                width: `${(count / maxCount) * 100}%`,
                backgroundColor: barColor(count),
              }}
            />
          </StyledBarTrack>
        </StyledItem>
      ))}
    </StyledRow>
  );
};
