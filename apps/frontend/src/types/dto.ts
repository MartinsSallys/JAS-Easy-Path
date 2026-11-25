import type { DeliveryStatus, IssueReason, Priority } from "./domain";

export interface LocationDTO {
  latitude: number;
  longitude: number;
}

export interface TimeWindowDTO {
  start: number;
  end: number;
}

export type GeocodingStatus = "ok" | "pending" | "failed";

export interface HistoryEntryDTO {
  at: string;
  text: string;
}

export interface DeliveryDTO {
  id: number;
  order_code: string;
  customer_name: string;
  phone: string | null;
  address: string;
  location: LocationDTO | null;
  geocoding_status: GeocodingStatus;
  geocoding_message: string | null;
  demand: number;
  time_window: TimeWindowDTO;
  has_explicit_time_window: boolean;
  priority: Priority;
  status: DeliveryStatus;
  notes: string | null;
  issue_reason: IssueReason | null;
  completed_at: string | null;
  history: HistoryEntryDTO[];
}

export interface NewDeliveryDTO {
  order_code: string | null;
  customer_name: string;
  phone: string | null;
  address: string;
  demand: number;
  time_window: TimeWindowDTO | null;
  priority: Priority;
  notes: string | null;
}

export interface PlaceDTO {
  name: string;
  address: string;
  location: LocationDTO;
}

export interface VehicleDTO {
  id: number;
  name: string;
  capacity: number;
}

export interface RouteStopDTO {
  delivery_id: number;
  arrival_minute_of_day: number;
  departure_minute_of_day: number;
}

export interface VehicleRouteDTO {
  vehicle: VehicleDTO;
  stops: RouteStopDTO[];
  load: number;
  distance_m: number;
  travel_min: number;
  wait_min: number;
  service_min: number;
  total_min: number;
}

export type MatrixSource = "manual" | "road_network";

export interface RoutePlanDTO {
  id: number;
  status: "planned" | "running" | "finished";
  origin: PlaceDTO;
  routes: VehicleRouteDTO[];
  matrix_source: MatrixSource;
}

export type ApiErrorCode =
  | "validation_error"
  | "no_feasible_solution"
  | "solver_timeout";

export interface ErrorDetailDTO {
  field: string;
  code: string;
  message: string;
  index: number | null;
}

export interface ApiErrorDTO {
  error: {
    code: ApiErrorCode | string;
    message: string;
    details: ErrorDetailDTO[];
  };
}

// ---------------------------------------------------------------------------
// Schemas reais do backend FastAPI (/api/v1)
// ---------------------------------------------------------------------------

export type BackendEntregaStatus =
  | "PENDENTE"
  | "ATRIBUIDA"
  | "EM_ROTA"
  | "ENTREGUE"
  | "FALHA"
  | "CANCELADA";

export type BackendRotaStatus =
  | "RASCUNHO"
  | "OTIMIZADA"
  | "EM_ANDAMENTO"
  | "CONCLUIDA"
  | "CANCELADA";

export type BackendParadaStatus =
  | "PENDENTE"
  | "EM_ANDAMENTO"
  | "CONCLUIDA"
  | "FALHA"
  | "PULADA";

export interface BackendEntregaCreateDTO {
  pedido_id: string;
  endereco: string;
  latitude: number;
  longitude: number;
  demanda: number;
  janela_inicio: string | null;
  janela_fim: string | null;
  observacoes: string | null;
}

export interface BackendEntregaUpdateDTO {
  pedido_id?: string;
  endereco?: string;
  latitude?: number;
  longitude?: number;
  demanda?: number;
  janela_inicio?: string | null;
  janela_fim?: string | null;
  observacoes?: string | null;
  status?: BackendEntregaStatus;
}

export interface BackendEntregaResponseDTO {
  id: number;
  pedido_id: string;
  endereco: string;
  latitude: number;
  longitude: number;
  demanda: number;
  janela_inicio: string | null;
  janela_fim: string | null;
  observacoes: string | null;
  status: BackendEntregaStatus;
  created_at: string;
  updated_at: string;
  rota_id: number | null;
  parada_ordem: number | null;
}

export interface BackendDepositoResponseDTO {
  id: number;
  nome: string;
  endereco: string;
  latitude: number;
  longitude: number;
  ativo: boolean;
  created_at: string;
}

export interface BackendVeiculoResponseDTO {
  id: number;
  placa: string;
  capacidade: number;
  tipo: "MOTO" | "CARRO" | "CAMINHAO" | "VAN";
  ativo: boolean;
  created_at: string;
}

export interface BackendParadaResponseDTO {
  id: number;
  rota_id: number;
  entrega_id: number | null;
  deposito_id: number | null;
  ordem: number;
  endereco: string;
  latitude: number;
  longitude: number;
  demanda: number;
  janela_inicio: string | null;
  janela_fim: string | null;
  tempo_servico_min: number;
  chegada_prevista: string | null;
  saida_prevista: string | null;
  observacoes: string | null;
  status: BackendParadaStatus;
}

export interface BackendRotaResponseDTO {
  id: number;
  nome: string;
  data: string;
  deposito_id: number;
  veiculo_id: number | null;
  status: BackendRotaStatus;
  distancia_total_km: number | null;
  tempo_total_min: number | null;
  created_at: string;
  updated_at: string;
  otimizada_em: string | null;
}

export interface BackendRotaWithParadasResponseDTO extends BackendRotaResponseDTO {
  paradas: BackendParadaResponseDTO[];
}

export interface BackendGeocodeResultDTO {
  latitude: number;
  longitude: number;
  display_name: string;
  confidence: number;
  address_components: Record<string, unknown>;
}

export interface BackendGeocodeResponseDTO {
  results: BackendGeocodeResultDTO[];
  ambiguous: boolean;
}