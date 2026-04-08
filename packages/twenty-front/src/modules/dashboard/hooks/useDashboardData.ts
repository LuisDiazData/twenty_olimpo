import { gql } from '@apollo/client';
import { useQuery } from '@apollo/client/react';
import { useEffect, useMemo } from 'react';
import type {
  AgentPerformance,
  AgenteCompliance,
  DashboardData,
  DashboardFilters,
  KpiSnapshot,
  Member,
  MotivoRechazo,
  Tramite,
} from '../types/dashboard.types';

// ─── GraphQL Queries ──────────────────────────────────────────────────────────

// Usa los nombres reales de campos del schema de Twenty CRM
const GET_TRAMITES = gql`
  query DashboardTramites {
    tramites(first: 500) {
      edges {
        node {
          id
          name
          folio
          folioGnp
          ramo
          estatus
          tipoTramite
          prioridad
          fechaIngreso
          fechaLimiteSla
          fechaResolucion
          agente {
            id
            name
          }
          analistaAsignado {
            id
            name {
              firstName
              lastName
            }
          }
        }
      }
    }
  }
`;

const GET_MOTIVOS_RECHAZO = gql`
  query DashboardMotivosRechazo {
    motivosRechazo(first: 200) {
      edges {
        node {
          id
          name
          ramo
          tipoTramite
          activo
        }
      }
    }
  }
`;

const GET_MEMBERS = gql`
  query DashboardMembers {
    workspaceMembers(first: 50) {
      edges {
        node {
          id
          name {
            firstName
            lastName
          }
        }
      }
    }
  }
`;

const GET_KPI_SNAPSHOTS = gql`
  query DashboardKpiSnapshots {
    kpiSnapshots(
      filter: { granularidad: { eq: "MENSUAL" }, entidadTipo: { eq: "Global" } }
      first: 20
      orderBy: { fechaCorte: DescNullsLast }
    ) {
      edges {
        node {
          id
          metricaNombre
          granularidad
          entidadTipo
          valor
          meta
          metaAlcanzada
          unidad
          fechaCorte
        }
      }
    }
  }
`;

// agentPerformanceMonthly aún no existe en Twenty (objeto pendiente de crear)
// errorPolicy: 'ignore' evita que rompa el dashboard
const GET_AGENT_PERFORMANCE = gql`
  query DashboardAgentPerformance {
    agentPerformanceMonthly(
      first: 20
      orderBy: { primaEmitida: DescNullsLast }
      filter: { esVigente: { eq: true } }
    ) {
      edges {
        node {
          id
          mesAnio
          tramitesTotales
          tramitesResueltos
          firstPassYield
          primaEmitida
          tasaCumplimientoSla
          bonoProyectado
          agente {
            id
            name
            claveAgente
          }
        }
      }
    }
  }
`;

const GET_AGENTES_COMPLIANCE = gql`
  query DashboardAgentes {
    agentes(first: 200, filter: { estatus: { eq: "ACTIVO" } }) {
      edges {
        node {
          id
          name
          claveAgente
          fechaVencimientoCedula
          estatus
          gerenteDesarrollo {
            id
            name {
              firstName
              lastName
            }
          }
        }
      }
    }
  }
`;

// ─── Helpers ─────────────────────────────────────────────────────────────────

const getPeriodoInicio = (periodo: DashboardFilters['periodo']): Date => {
  const now = new Date();
  if (periodo === 'mes') {
    return new Date(now.getFullYear(), now.getMonth(), 1);
  }
  if (periodo === 'trimestre') {
    return new Date(now.getFullYear(), now.getMonth() - 2, 1);
  }
  // anio
  return new Date(now.getFullYear(), 0, 1);
};

// ─── Hook ────────────────────────────────────────────────────────────────────

export const useDashboardData = (filters: DashboardFilters): DashboardData => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tramitesResult = useQuery<any>(GET_TRAMITES, {
    fetchPolicy: 'cache-and-network',
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const motivosResult = useQuery<any>(GET_MOTIVOS_RECHAZO, {
    fetchPolicy: 'cache-and-network',
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const membersResult = useQuery<any>(GET_MEMBERS, {
    fetchPolicy: 'cache-and-network',
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const kpiResult = useQuery<any>(GET_KPI_SNAPSHOTS, {
    fetchPolicy: 'cache-and-network',
    errorPolicy: 'ignore',
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const agentPerfResult = useQuery<any>(GET_AGENT_PERFORMANCE, {
    fetchPolicy: 'cache-and-network',
    errorPolicy: 'ignore',
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const agentesResult = useQuery<any>(GET_AGENTES_COMPLIANCE, {
    fetchPolicy: 'cache-and-network',
    errorPolicy: 'ignore',
  });

  // Auto-refresh every 60 seconds
  useEffect(() => {
    tramitesResult.startPolling(60_000);
    motivosResult.startPolling(60_000);
    return () => {
      tramitesResult.stopPolling();
      motivosResult.stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Raw data
  const allTramites: Tramite[] =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    tramitesResult.data?.tramites?.edges?.map((e: any) => e.node) ?? [];

  const motivosRechazo: MotivoRechazo[] =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    motivosResult.data?.motivosRechazo?.edges?.map((e: any) => e.node) ?? [];

  const members: Member[] =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    membersResult.data?.workspaceMembers?.edges?.map((e: any) => e.node) ?? [];

  const kpiSnapshots: KpiSnapshot[] =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    kpiResult.data?.kpiSnapshots?.edges?.map((e: any) => e.node) ?? [];

  const agentPerformance: AgentPerformance[] =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    agentPerfResult.data?.agentPerformanceMonthly?.edges?.map((e: any) => e.node) ?? [];

  const agentes: AgenteCompliance[] =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    agentesResult.data?.agentes?.edges?.map((e: any) => e.node) ?? [];

  // Aplicar filtros a tramites
  const periodoInicio = useMemo(() => getPeriodoInicio(filters.periodo), [filters.periodo]);

  const tramites = useMemo(() => {
    return allTramites
      .filter((t) => filters.ramo === 'todos' || t.ramo === filters.ramo)
      .filter(
        (t) =>
          !filters.gerenteId ||
          t.analistaAsignado?.id === filters.gerenteId,
      )
      .filter(
        (t) =>
          !t.fechaIngreso ||
          new Date(t.fechaIngreso) >= periodoInicio,
      );
  }, [allTramites, filters, periodoInicio]);

  const isLoading =
    (tramitesResult.loading && !tramitesResult.data) ||
    (membersResult.loading && !membersResult.data);

  const error =
    tramitesResult.error?.message ||
    motivosResult.error?.message ||
    membersResult.error?.message ||
    null;

  const refetch = () => {
    void tramitesResult.refetch();
    void motivosResult.refetch();
    void membersResult.refetch();
    void kpiResult.refetch();
    void agentPerfResult.refetch();
    void agentesResult.refetch();
  };

  return {
    tramites,
    motivosRechazo,
    members,
    kpiSnapshots,
    agentPerformance,
    agentes,
    filters,
    isLoading,
    error,
    refetch,
  };
};
