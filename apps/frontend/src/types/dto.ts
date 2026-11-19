import type { DeliveryStatus, IssueReason, Priority } from "./domain";

export interface DeliveryDTO {
  id: string;
  order_code: string;
  customer_name: string;
  phone: string | null;
  address: string;
  lat: number;
  lng: number;
  window_start: string;
  window_end: string;
  priority: Priority;
  status: DeliveryStatus;
  notes: string | null;
  issue_reason: IssueReason | null;
  completed_at: string | null;
  history: { at: string; text: string }[];
}

export interface NewDeliveryDTO {
  order_code: string | null;
  customer_name: string;
  phone: string | null;
  address: string;
  window_start: string;
  window_end: string;
  priority: Priority;
  notes: string | null;
}

export interface PlaceDTO {
  name: string;
  address: string;
  lat: number;
  lng: number;
}

export interface RoutePlanDTO {
  id: string;
  driver_name: string;
  origin: PlaceDTO;
  stop_ids: string[];
  distance_km: number;
  duration_min: number;
  status: "planned" | "running" | "finished";
  is_simulation: boolean;
}