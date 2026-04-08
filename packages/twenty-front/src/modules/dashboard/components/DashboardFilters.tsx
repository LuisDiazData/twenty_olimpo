import { styled } from '@linaria/react';
import type { DashboardFilters, Member, TramiteRamo } from '../types/dashboard.types';

interface DashboardFiltersProps {
  filters: DashboardFilters;
  onChange: (f: DashboardFilters) => void;
  members: Member[];
}

const StyledBar = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 20px;
  height: 40px;
  background: #141720;
  border-bottom: 1px solid #2a2d3a;
  flex-shrink: 0;
`;

const StyledLabel = styled.span`
  font-size: 11px;
  color: #5f5e5a;
  font-weight: 500;
`;

const StyledSelect = styled.select`
  background: #1a1d27;
  border: 1px solid #2a2d3a;
  border-radius: 6px;
  color: #c8c5bf;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 28px 4px 10px;
  height: 28px;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239c9a92' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;

  &:hover {
    border-color: #3a3d4a;
    color: #e8e6e1;
  }

  &:focus {
    outline: none;
    border-color: #1d9e75;
  }

  option {
    background: #1a1d27;
    color: #e8e6e1;
  }
`;

const StyledSeparator = styled.div`
  width: 1px;
  height: 18px;
  background: #2a2d3a;
  margin: 0 4px;
`;

const RAMO_OPTIONS: { value: TramiteRamo | 'todos'; label: string }[] = [
  { value: 'todos', label: 'Todos los ramos' },
  { value: 'VIDA', label: 'Vida' },
  { value: 'GMM', label: 'GMM' },
  { value: 'AUTOS', label: 'Autos' },
  { value: 'PYME', label: 'PyMES' },
  { value: 'DANOS', label: 'Daños' },
];

export const DashboardFiltersBar = ({
  filters,
  onChange,
  members,
}: DashboardFiltersProps) => {
  return (
    <StyledBar>
      <StyledLabel>Período:</StyledLabel>
      <StyledSelect
        value={filters.periodo}
        onChange={(e) =>
          onChange({
            ...filters,
            periodo: e.target.value as DashboardFilters['periodo'],
          })
        }
      >
        <option value="mes">Mes actual</option>
        <option value="trimestre">Último trimestre</option>
        <option value="anio">Este año</option>
      </StyledSelect>

      <StyledSeparator />

      <StyledLabel>Ramo:</StyledLabel>
      <StyledSelect
        value={filters.ramo}
        onChange={(e) =>
          onChange({
            ...filters,
            ramo: e.target.value as DashboardFilters['ramo'],
          })
        }
      >
        {RAMO_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </StyledSelect>

      <StyledSeparator />

      <StyledLabel>Gerente:</StyledLabel>
      <StyledSelect
        value={filters.gerenteId ?? ''}
        onChange={(e) =>
          onChange({
            ...filters,
            gerenteId: e.target.value || null,
          })
        }
      >
        <option value="">Todos los gerentes</option>
        {members.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name.firstName} {m.name.lastName}
          </option>
        ))}
      </StyledSelect>
    </StyledBar>
  );
};
