export type SemaforoColor = 'verde' | 'amarillo' | 'rojo' | 'gris';

// Estatus reales del objeto Tramite en Twenty CRM
export type TramiteEstado =
  | 'RECIBIDO'
  | 'EN_REVISION_DOC'
  | 'DOCUMENTACION_COMPLETA'
  | 'TURNADO_GNP'
  | 'EN_PROCESO_GNP'
  | 'DETENIDO'
  | 'RESUELTO'
  | 'CANCELADO';

export type TramiteRamo = 'VIDA' | 'GMM' | 'AUTOS' | 'PYMES' | 'DANOS';

export interface Agente {
  id: string;
  name: string;
}

export interface MemberName {
  firstName: string;
  lastName: string;
}

export interface AnalistaAsignado {
  id: string;
  name: MemberName;
}

export interface Tramite {
  id: string;
  name: string;
  folio: string | null;
  folioGnp: string | null;
  ramo: TramiteRamo | null;
  estatus: TramiteEstado | null;
  tipoTramite: string | null;
  prioridad: string | null;
  fechaIngreso: string | null;
  fechaLimiteSla: string | null;
  fechaResolucion: string | null;
  agente: Agente | null;
  analistaAsignado: AnalistaAsignado | null;
}

export interface MotivoRechazo {
  id: string;
  name: string;
  ramo: string | null;
  tipoTramite: string | null;
  activo: boolean | null;
}

export interface Member {
  id: string;
  name: MemberName;
}

export type PeriodFilter = 'mes' | 'trimestre' | 'anio';

export interface DashboardFilters {
  periodo: PeriodFilter;
  ramo: TramiteRamo | 'todos';
  gerenteId: string | null;
}

export interface KpiSnapshot {
  id: string;
  metricaNombre: string | null;
  granularidad: string | null;
  entidadTipo: string | null;
  valor: number | null;
  meta: number | null;
  metaAlcanzada: boolean | null;
  unidad: string | null;
  fechaCorte: string | null;
}

export interface AgentPerformance {
  id: string;
  mesAnio: string | null;
  tramitesTotales: number | null;
  tramitesResueltos: number | null;
  firstPassYield: number | null;
  primaEmitida: number | null;
  tasaCumplimientoSla: number | null;
  bonoProyectado: number | null;
  agente: { id: string; name: string; claveAgente: string | null } | null;
}

export interface AgenteCompliance {
  id: string;
  name: string;
  claveAgente: string | null;
  fechaVencimientoCedula: string | null;
  estatus: string | null;
  gerenteDesarrollo: { id: string; name: MemberName } | null;
}

export interface DashboardData {
  tramites: Tramite[];
  motivosRechazo: MotivoRechazo[];
  members: Member[];
  kpiSnapshots: KpiSnapshot[];
  agentPerformance: AgentPerformance[];
  agentes: AgenteCompliance[];
  filters: DashboardFilters;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}
