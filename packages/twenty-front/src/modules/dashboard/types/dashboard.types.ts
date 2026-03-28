export type SemaforoColor = 'verde' | 'amarillo' | 'rojo' | 'gris';

export type TramiteEstado =
  | 'PENDIENTE'
  | 'EN_REVISION'
  | 'LISTO_PARA_GNP'
  | 'ENVIADO_A_GNP'
  | 'APROBADO_GNP'
  | 'RECHAZADO_GNP'
  | 'CERRADO';

export type TramiteRamo = 'VIDA' | 'GMM' | 'AUTOS' | 'PYME' | 'DANOS';

export interface AgenteTitular {
  id: string;
  name: string;
}

export interface MemberName {
  firstName: string;
  lastName: string;
}

export interface EspecialistaAsignado {
  id: string;
  name: MemberName;
}

export interface Tramite {
  id: string;
  name: string;
  ramo: TramiteRamo | null;
  estadoTramite: TramiteEstado | null;
  fechaEntrada: string | null;
  fechaLimiteSla: string | null;
  resultadoGnp: string | null;
  tipoTramite: string | null;
  fueraDeSla: boolean | null;
  notasAnalista: string | null;
  folioInterno: string | null;
  numPolizaGnp: string | null;
  nombreAsegurado: string | null;
  agenteTitular: AgenteTitular | null;
  especialistaAsignado: EspecialistaAsignado | null;
}

export interface RazonRechazo {
  id: string;
  name: string;
  categoria: string | null;
  descripcion: string | null;
  frecuencia: number | null;
  tramite: { id: string; ramo: string | null } | null;
}

export interface Member {
  id: string;
  name: MemberName;
}

export interface DashboardData {
  tramites: Tramite[];
  razones: RazonRechazo[];
  members: Member[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}
