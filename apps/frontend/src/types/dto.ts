import type { DeliveryStatus, IssueReason, Priority } from "./domain";

/**
 * DTOs = o formato EXATO do JSON que trafega na API (snake_case).
 * Contrato alinhado em docs/api.md (issues #5, #6, #7 e #8):
 *  - IDs: número inteiro no motor/API. O front converte para string em mappers.ts.
 *  - Coordenadas: objeto { latitude, longitude }.
 *  - Horário do dia: minutos desde 00:00 (0 a 1440; 1440 = 24:00, fim do dia).
 *  - Duração: minutos decorridos (_min). Distância: metros inteiros (_m).
 *  - Capacidade/Demanda no MVP: medida em quantidade de pedidos (cada entrega = 1 unidade).
 *  - Regra de otimização: todas as entregas são obrigatórias (sem solução parcial).
 */

export interface LocationDTO {
  latitude: number;
  longitude: number;
}

/** Janela de entrega em minutos desde 00:00. Ex.: 19:00 a 19:30 = { start: 1140, end: 1170 }. */
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

/** "manual" = matriz informada à mão (estimativa); "road_network" = distâncias/tempos reais por ruas. */
export type MatrixSource = "manual" | "road_network";

/**
 * O plano do dia. GET /routes/today e POST /routes/today/optimize devolvem este formato
 * apenas quando TODAS as entregas válidas do dia foram atendidas.
 */
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

/**
 * Corpo de erro (HTTP 422):
 * - "validation_error": dados inválidos
 * - "no_feasible_solution": impossível atender todas as entregas com os veículos/janelas atuais
 * - "solver_timeout": motor não encontrou solução viável dentro do tempo limite
 */
export interface ApiErrorDTO {
  error: {
    code: ApiErrorCode | string;
    message: string;
    details: ErrorDetailDTO[];
  };
}