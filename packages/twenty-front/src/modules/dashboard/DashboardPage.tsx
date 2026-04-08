import { styled } from '@linaria/react';
import { useState } from 'react';
import { DashboardFiltersBar } from './components/DashboardFilters';
import { useDashboardData } from './hooks/useDashboardData';
import type { DashboardFilters } from './types/dashboard.types';
import { DirectoraView } from './views/DirectoraView';
import { EspecialistaView } from './views/EspecialistaView';
import { GerenteView } from './views/GerenteView';

type Vista = 'directora' | 'gerente' | 'especialista';

const VISTA_OPTIONS: { key: Vista; label: string; icon: string }[] = [
  { key: 'directora', label: 'Directora', icon: '📊' },
  { key: 'gerente', label: 'Gerente', icon: '👥' },
  { key: 'especialista', label: 'Especialista', icon: '👤' },
];

const DEFAULT_FILTERS: DashboardFilters = {
  periodo: 'mes',
  ramo: 'todos',
  gerenteId: null,
};

// ─── Styled components ────────────────────────────────────────────────────────

const StyledPage = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0f1117;
  color: #e8e6e1;
  font-family: Inter, system-ui, sans-serif;
  font-size: 13px;
  overflow: hidden;
`;

const StyledTopBar = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 20px;
  background: #1a1d27;
  border-bottom: 2px solid #2a2d3a;
  flex-shrink: 0;
  height: 44px;
`;

const StyledTitle = styled.span`
  font-size: 14px;
  font-weight: 700;
  color: #22c78a;
  margin-right: 16px;
`;

const StyledTabButton = styled.button`
  background: none;
  border: none;
  padding: 0 14px;
  height: 44px;
  font-size: 12px;
  font-weight: 600;
  color: #9c9a92;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;

  &:hover {
    color: #e8e6e1;
  }

  &[data-active='true'] {
    color: #e8e6e1;
    border-bottom-color: #1d9e75;
  }
`;

const StyledRefreshNote = styled.div`
  margin-left: auto;
  font-size: 10px;
  color: #5f5e5a;
`;

const StyledViewContainer = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
`;

// ─── Loading skeleton ─────────────────────────────────────────────────────────

const StyledSkeleton = styled.div`
  flex: 1;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const StyledSkeletonRow = styled.div`
  display: flex;
  gap: 12px;
`;

const StyledSkeletonBlock = styled.div`
  border-radius: 10px;
  background: linear-gradient(90deg, #1a1d27 25%, #22263a 50%, #1a1d27 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;

  @keyframes shimmer {
    0% {
      background-position: 200% 0;
    }
    100% {
      background-position: -200% 0;
    }
  }
`;

const SkeletonLoader = () => (
  <StyledSkeleton>
    <StyledSkeletonRow>
      {[1, 2, 3, 4].map((i) => (
        <StyledSkeletonBlock key={i} style={{ flex: 1, height: 88 }} />
      ))}
    </StyledSkeletonRow>
    <StyledSkeletonRow>
      {[1, 2, 3, 4].map((i) => (
        <StyledSkeletonBlock key={i} style={{ flex: 1, height: 88 }} />
      ))}
    </StyledSkeletonRow>
    <StyledSkeletonRow>
      <StyledSkeletonBlock style={{ width: '27%', height: 260 }} />
      <StyledSkeletonBlock style={{ flex: 1, height: 260 }} />
      <StyledSkeletonBlock style={{ width: '23%', height: 260 }} />
    </StyledSkeletonRow>
    <StyledSkeletonRow>
      <StyledSkeletonBlock style={{ width: '40%', height: 200 }} />
      <StyledSkeletonBlock style={{ flex: 1, height: 200 }} />
    </StyledSkeletonRow>
  </StyledSkeleton>
);

// ─── Error banner ─────────────────────────────────────────────────────────────

const StyledErrorBanner = styled.div`
  margin: 20px;
  padding: 14px 18px;
  background: rgba(163, 45, 45, 0.12);
  border: 1px solid rgba(163, 45, 45, 0.4);
  border-radius: 8px;
  color: #e05252;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 12px;
`;

const StyledRetryButton = styled.button`
  background: rgba(163, 45, 45, 0.25);
  border: 1px solid rgba(163, 45, 45, 0.4);
  color: #e05252;
  padding: 5px 12px;
  border-radius: 5px;
  font-size: 12px;
  cursor: pointer;
  margin-left: auto;

  &:hover {
    background: rgba(163, 45, 45, 0.35);
  }
`;

// ─── Main page ────────────────────────────────────────────────────────────────

export const DashboardPage = () => {
  const [vista, setVista] = useState<Vista>('directora');
  const [filters, setFilters] = useState<DashboardFilters>(DEFAULT_FILTERS);
  const data = useDashboardData(filters);

  return (
    <StyledPage>
      <StyledTopBar>
        <StyledTitle>Promotoría GNP</StyledTitle>
        {VISTA_OPTIONS.map(({ key, label, icon }) => (
          <StyledTabButton
            key={key}
            data-active={String(vista === key)}
            onClick={() => setVista(key)}
          >
            {icon} {label}
          </StyledTabButton>
        ))}
        <StyledRefreshNote>Actualiza cada 60s</StyledRefreshNote>
      </StyledTopBar>

      <DashboardFiltersBar
        filters={filters}
        onChange={setFilters}
        members={data.members}
      />

      <StyledViewContainer>
        {data.isLoading && <SkeletonLoader />}

        {!data.isLoading && data.error && (
          <StyledErrorBanner>
            ⚠ Error al cargar datos: {data.error}
            <StyledRetryButton onClick={data.refetch}>
              Reintentar
            </StyledRetryButton>
          </StyledErrorBanner>
        )}

        {!data.isLoading && !data.error && (
          <>
            {vista === 'directora' && <DirectoraView {...data} />}
            {vista === 'gerente' && <GerenteView {...data} />}
            {vista === 'especialista' && <EspecialistaView {...data} />}
          </>
        )}
      </StyledViewContainer>
    </StyledPage>
  );
};
