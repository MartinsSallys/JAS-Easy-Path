export type DeliveryStatus = "waiting_departure" | "in_progress" | "completed" | "issue";
export type IssueReason =
  | "customer_absent"
  | "address_not_found"
  | "customer_refused"
  | "operational"
  | "other";
export type Priority = "low" | "normal" | "high";

export interface HistoryEntry {
  at: string;
  text: string;
}

export interface Delivery {
  id: string;
  orderCode: string;
  customerName: string;
  phone: string;
  address: string;
  lat: number;
  lng: number;
  windowStart: string;
  windowEnd: string;
  /**
   * false = a entrega herdou o expediente da loja; true = janela informada no cadastro.
   * Opcional: o backend real grava janela vazia como o expediente, sem flag para
   * distinguir — a integração pode não conseguir preencher este campo.
   */
  hasExplicitTimeWindow?: boolean;
  priority: Priority;
  status: DeliveryStatus;
  notes: string;
  issueReason: IssueReason | null;
  completedAt: string | null;
  history: HistoryEntry[];
}

/** O que o usuário preenche ao cadastrar. Coordenadas e status vêm do sistema. */
export interface NewDelivery {
  orderCode: string;
  customerName: string;
  phone: string;
  address: string;
  windowStart: string;
  windowEnd: string;
  priority: Priority;
  notes: string;
}

export interface Place {
  name: string;
  address: string;
  lat: number;
  lng: number;
}

/** Rota atribuída a um veículo específico dentro do plano do dia. */
export interface VehicleRoute {
  vehicleId: string;
  vehicleName: string;
  capacity: number; 
  load: number; 
  stopIds: string[];
  distanceKm: number;
  durationMin: number;
  travelMin: number;
  waitMin: number;
  serviceMin: number;
}

export interface RoutePlan {
  id: string;
  origin: Place;
  routes: VehicleRoute[];
  totalDistanceKm: number;
  totalDurationMin: number;
  status: "planned" | "running" | "finished";
  isSimulation: boolean;
}