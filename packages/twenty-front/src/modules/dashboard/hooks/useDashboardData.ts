import { gql } from '@apollo/client';
import { useQuery } from '@apollo/client/react';
import { useEffect } from 'react';
import type {
  DashboardData,
  Member,
  RazonRechazo,
  Tramite,
} from '../types/dashboard.types';

// ─── GraphQL Queries ──────────────────────────────────────────────────────────

const GET_TRAMITES = gql`
  query DashboardTramites {
    tramites(first: 500) {
      edges {
        node {
          id
          name
          ramo
          estadoTramite
          fechaEntrada
          fechaLimiteSla
          resultadoGnp
          tipoTramite
          fueraDeSla
          notasAnalista
          folioInterno
          numPolizaGnp
          nombreAsegurado
          agenteTitular {
            id
            name
          }
          especialistaAsignado {
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

const GET_RAZONES = gql`
  query DashboardRazones {
    razonesRechazo(first: 200) {
      edges {
        node {
          id
          name
          categoria
          descripcion
          frecuencia
          tramite {
            id
            ramo
          }
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

// ─── Hook ────────────────────────────────────────────────────────────────────

export const useDashboardData = (): DashboardData => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tramitesResult = useQuery<any>(GET_TRAMITES, {
    fetchPolicy: 'cache-and-network',
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const razonesResult = useQuery<any>(GET_RAZONES, {
    fetchPolicy: 'cache-and-network',
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const membersResult = useQuery<any>(GET_MEMBERS, {
    fetchPolicy: 'cache-and-network',
  });

  // Auto-refresh every 60 seconds
  useEffect(() => {
    tramitesResult.startPolling(60_000);
    razonesResult.startPolling(60_000);
    return () => {
      tramitesResult.stopPolling();
      razonesResult.stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tramites: Tramite[] =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    tramitesResult.data?.tramites?.edges?.map((e: any) => e.node) ?? [];

  const razones: RazonRechazo[] =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    razonesResult.data?.razonesRechazo?.edges?.map((e: any) => e.node) ?? [];

  const members: Member[] =
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    membersResult.data?.workspaceMembers?.edges?.map((e: any) => e.node) ?? [];

  const isLoading =
    (tramitesResult.loading && !tramitesResult.data) ||
    (membersResult.loading && !membersResult.data);

  const error =
    tramitesResult.error?.message ||
    razonesResult.error?.message ||
    membersResult.error?.message ||
    null;

  const refetch = () => {
    void tramitesResult.refetch();
    void razonesResult.refetch();
    void membersResult.refetch();
  };

  return { tramites, razones, members, isLoading, error, refetch };
};
