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

export interface RoutePlan {
  id: string;
  driverName: string;
  origin: Place;
  stopIds: string[]; // ids das entregas, NA ORDEM de visita
  distanceKm: number;
  durationMin: number;
  status: "planned" | "running" | "finished";
  isSimulation: boolean;
}