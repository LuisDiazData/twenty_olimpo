import { styled } from '@linaria/react';

type CardColor = 'default' | 'rojo' | 'amarillo' | 'verde' | 'azul';
type Tendencia = 'sube' | 'baja' | 'igual';

interface KPICardProps {
  label: string;
  value: number | string;
  sublabel?: string;
  color?: CardColor;
  tendencia?: Tendencia;
  tendenciaLabel?: string;
  lowerIsBetter?: boolean;
}

const StyledCard = styled.div`
  background: #1a1d27;
  border: 1px solid #2a2d3a;
  border-radius: 10px;
  padding: 18px 20px 14px;
  position: relative;
  flex: 1;
  min-width: 120px;

  &[data-color='rojo'] {
    border-color: rgba(163, 45, 45, 0.5);
    background: rgba(163, 45, 45, 0.08);
  }
  &[data-color='amarillo'] {
    border-color: rgba(186, 117, 23, 0.4);
    background: rgba(186, 117, 23, 0.06);
  }
  &[data-color='verde'] {
    border-color: rgba(29, 158, 117, 0.4);
    background: rgba(29, 158, 117, 0.06);
  }
  &[data-color='azul'] {
    border-color: rgba(24, 95, 165, 0.4);
    background: rgba(24, 95, 165, 0.06);
  }
`;

const StyledValue = styled.div`
  font-size: 36px;
  font-weight: 700;
  line-height: 1;
  color: #e8e6e1;
  margin-bottom: 6px;
`;

const StyledLabel = styled.div`
  font-size: 11px;
  color: #9c9a92;
  line-height: 1.4;
`;

const StyledSublabel = styled.div`
  font-size: 11px;
  color: #9c9a92;
  margin-top: 2px;
`;

const StyledTendencia = styled.div`
  position: absolute;
  top: 14px;
  right: 14px;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;

  &[data-positive='true'] {
    color: #22c78a;
  }
  &[data-positive='false'] {
    color: #e05252;
  }
  &[data-neutral='true'] {
    color: #9c9a92;
  }
`;

const StyledTendenciaLabel = styled.span`
  font-size: 10px;
  font-weight: 400;
  color: #9c9a92;
`;

export const KPICard = ({
  label,
  value,
  sublabel,
  color = 'default',
  tendencia,
  tendenciaLabel,
  lowerIsBetter = false,
}: KPICardProps) => {
  const isPositive =
    tendencia === 'igual'
      ? null
      : tendencia === 'sube'
        ? !lowerIsBetter
        : lowerIsBetter; // baja

  const arrow = tendencia === 'sube' ? '▲' : tendencia === 'baja' ? '▼' : '—';

  return (
    <StyledCard data-color={color}>
      {tendencia && tendencia !== 'igual' && (
        <StyledTendencia
          data-positive={String(isPositive)}
          data-neutral="false"
        >
          {arrow}
          {tendenciaLabel && (
            <StyledTendenciaLabel>{tendenciaLabel}</StyledTendenciaLabel>
          )}
        </StyledTendencia>
      )}
      {tendencia === 'igual' && (
        <StyledTendencia data-positive="false" data-neutral="true">
          —
        </StyledTendencia>
      )}
      <StyledValue>{value}</StyledValue>
      <StyledLabel>{label}</StyledLabel>
      {sublabel && <StyledSublabel>{sublabel}</StyledSublabel>}
    </StyledCard>
  );
};
