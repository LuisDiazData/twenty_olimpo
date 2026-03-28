import { styled } from '@linaria/react';
import type { RazonRechazo } from '../types/dashboard.types';

interface RechazosChartProps {
  razonesRechazo: RazonRechazo[];
  filterRamo?: string;
}

const StyledList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

const StyledItem = styled.div``;

const StyledItemHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 3px;
`;

const StyledCategory = styled.span`
  font-size: 12px;
  color: #e8e6e1;
`;

const StyledMeta = styled.span`
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
`;

// Coral gradient by position
const BAR_COLORS = [
  '#D85A30',
  '#C4502B',
  '#B04626',
  '#9C3C21',
  '#88321C',
  '#743218',
  '#602813',
];

export const RechazosChart = ({
  razonesRechazo,
  filterRamo,
}: RechazosChartProps) => {
  const filtered = filterRamo
    ? razonesRechazo.filter((r) => r.tramite?.ramo === filterRamo)
    : razonesRechazo;

  // Aggregate by categoria
  const agg: Record<string, number> = {};
  filtered.forEach((r) => {
    const key = r.categoria ?? r.name;
    agg[key] = (agg[key] ?? 0) + (r.frecuencia ?? 1);
  });

  const items = Object.entries(agg)
    .map(([cat, cnt]) => ({ cat, cnt }))
    .sort((a, b) => b.cnt - a.cnt)
    .slice(0, 7);

  const total = items.reduce((s, i) => s + i.cnt, 0);

  if (items.length === 0) {
    return (
      <div style={{ color: '#9c9a92', textAlign: 'center', padding: '24px 0' }}>
        Sin rechazos registrados
      </div>
    );
  }

  return (
    <StyledList>
      {items.map(({ cat, cnt }, idx) => (
        <StyledItem key={cat}>
          <StyledItemHeader>
            <StyledCategory>
              {cat.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())}
            </StyledCategory>
            <StyledMeta>
              {cnt} ({total > 0 ? ((cnt / total) * 100).toFixed(0) : 0}%)
            </StyledMeta>
          </StyledItemHeader>
          <StyledBarTrack>
            <StyledBarFill
              style={{
                width: `${total > 0 ? (cnt / total) * 100 : 0}%`,
                backgroundColor: BAR_COLORS[idx % BAR_COLORS.length],
              }}
            />
          </StyledBarTrack>
        </StyledItem>
      ))}
    </StyledList>
  );
};
