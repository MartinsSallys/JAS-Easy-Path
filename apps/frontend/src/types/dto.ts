import type { DeliveryStatus, IssueReason, Priority } from "./domain";

/**
 * DTOs = o formato EXATO do JSON que trafega na API (snake_case).
 * Contrato proposto em docs/api.md. Convenções (a confirmar com o back, issues #6, #7 e #8):
 *  - IDs: número inteiro (o motor usa inteiros). O front converte para texto no mappers.ts.
 *  - Coordenadas: objeto { latitude, longitude }, sempre com nomes, nunca lista de dois números.
 *  - Horário do dia: minutos desde 00:00 (0 a 1440; 1440 = 24:00, fim do dia).
 *  - Duração: minutos decorridos, em campos terminados em _min. Distância: metros inteiros.
 *  - Se o back mudar um nome ou unidade, só este arquivo e o mappers.ts mudam.
 */

/** Ponto geográfico. Nomes alinhados ao motor (location.latitude / location.longitude). */
export interface LocationDTO {
  latitude: number;
  longitude: number;
}

/** Janela de entrega em minutos desde 00:00. Ex.: 19:00 a 19:30 = { start: 1140, end: 1170 }. */
export interface TimeWindowDTO {
  start: number;
  end: number; 
}

/** "ok" = tem coordenadas; "pending" = ainda geocodificando; "failed" = não achou o endereço. */
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

export type UnassignedReason = "time_window" | "capacity" | "geocoding_failed" | "other";

export interface UnassignedDTO {
  delivery_id: number;
  reason: UnassignedReason;
}

/** "manual" = distâncias/tempos de uma matriz informada à mão (estimativa); "road_network" = por ruas. */
export type MatrixSource = "manual" | "road_network";

/** "solved" = todas as entregas atendidas; "partial" = há entregas em unassigned. */
export type SolutionStatus = "solved" | "partial";

/** O plano do dia. GET /routes/today e POST /routes/today/optimize devolvem este formato. */
export interface RoutePlanDTO {
  id: number;
  status: "planned" | "running" | "finished";
  solution_status: SolutionStatus;
  origin: PlaceDTO; 
  routes: VehicleRouteDTO[]; 
  unassigned: UnassignedDTO[];
  matrix_source: MatrixSource;
}

export interface ErrorDetailDTO {
  field: string;
  code: string;
  message: string;
  index: number | null; 
}

/** Corpo de erro (HTTP 422): entrada inválida ou "no_feasible_solution". */
export interface ApiErrorDTO {
  error: {
    code: string;
    message: string;
    details: ErrorDetailDTO[];
  };
}