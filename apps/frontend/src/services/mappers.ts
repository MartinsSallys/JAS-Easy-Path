import type { Delivery, NewDelivery, Place, RoutePlan, VehicleRoute } from "@/types/domain";
import type {
  DeliveryDTO,
  NewDeliveryDTO,
  PlaceDTO,
  RoutePlanDTO,
  TimeWindowDTO,
  VehicleRouteDTO,
} from "@/types/dto";

/**
 * Traduz API -> front (domain.ts) e o caminho inverso.
 * TODA conversão de formato fica aqui: ids, horários, coordenadas, demanda, unidades, rotas.
 */

/** Demanda enviada por entrega no MVP: cada pedido conta como 1 unidade de capacidade do veículo. */
export const DEFAULT_DEMAND = 1;

const MINUTES_PER_DAY = 1440;

// ---------------------------------------------------------------------------
// Horários
// ---------------------------------------------------------------------------

/** "19:30" -> 1170. Aceita "24:00" (1440 = fim do dia). Lança erro se o texto for inválido. */
export function hhmmToMinutes(text: string): number {
  const match = /^(\d{1,2}):(\d{2})$/.exec(text.trim());
  if (!match) throw new Error(`Horário inválido: "${text}". Use HH:mm.`);
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  const valid = minutes <= 59 && (hours < 24 || (hours === 24 && minutes === 0));
  if (!valid) throw new Error(`Horário fora do intervalo 00:00 a 24:00: "${text}".`);
  return hours * 60 + minutes;
}

/** 1170 -> "19:30". 1440 -> "24:00". */
export function minutesToHHmm(totalMinutes: number): string {
  const clamped = Math.min(Math.max(Math.round(totalMinutes), 0), MINUTES_PER_DAY);
  const hours = Math.floor(clamped / 60);
  const minutes = clamped % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

/**
 * "2026-11-19T19:50:00-03:00" -> "19:50".
 * Lê a hora do próprio texto, sem converter fuso: o front mostra a hora de parede enviada pela API.
 * Se o texto não for ISO (ex.: já "19:50"), devolve como veio.
 */
export function wallClockHHmm(value: string): string {
  const match = /^\d{4}-\d{2}-\d{2}T(\d{2}:\d{2})/.exec(value);
  return match ? match[1] : value;
}

/**
 * Janela do formulário/CSV (texto) -> janela da API (minutos).
 * Os dois vazios = sem janela própria (a API usa o expediente) -> null.
 */
export function toTimeWindowDTO(windowStart: string, windowEnd: string): TimeWindowDTO | null {
  const start = windowStart.trim();
  const end = windowEnd.trim();
  if (start === "" && end === "") return null;
  if (start === "" || end === "") {
    throw new Error("Informe o início e o fim da janela, ou deixe os dois em branco.");
  }
  return { start: hhmmToMinutes(start), end: hhmmToMinutes(end) };
}

// ---------------------------------------------------------------------------
// Entregas
// ---------------------------------------------------------------------------

function toPlace(dto: PlaceDTO): Place {
  return {
    name: dto.name,
    address: dto.address,
    lat: dto.location.latitude,
    lng: dto.location.longitude,
  };
}

export function toDelivery(dto: DeliveryDTO): Delivery {
  const unlocated = dto.location === null;
  const geocodingFailed = unlocated && dto.geocoding_status !== "pending";
  const notYetDelivered = dto.status === "waiting_departure" || dto.status === "in_progress";

  const geocodingNote = geocodingFailed
    ? `Geocodificação: ${dto.geocoding_message ?? "endereço sem coordenadas."}`
    : unlocated
      ? "Geocodificação pendente."
      : "";
  const notes = [dto.notes ?? "", geocodingNote].filter((part) => part !== "").join(" | ");

  return {
    id: String(dto.id),
    orderCode: dto.order_code,
    customerName: dto.customer_name,
    phone: dto.phone ?? "",
    address: dto.address,
    lat: dto.location?.latitude ?? 0,
    lng: dto.location?.longitude ?? 0,
    windowStart: minutesToHHmm(dto.time_window.start),
    windowEnd: minutesToHHmm(dto.time_window.end),
    priority: dto.priority,
    status: geocodingFailed && notYetDelivered ? "issue" : dto.status,
    notes,
    issueReason: geocodingFailed && notYetDelivered ? "address_not_found" : dto.issue_reason,
    completedAt: dto.completed_at === null ? null : wallClockHHmm(dto.completed_at),
    history: dto.history.map((entry) => ({ at: wallClockHHmm(entry.at), text: entry.text })),
  };
}

export function toNewDeliveryDTO(input: NewDelivery): NewDeliveryDTO {
  return {
    order_code: input.orderCode || null,
    customer_name: input.customerName,
    phone: input.phone || null,
    address: input.address,
    demand: DEFAULT_DEMAND,
    time_window: toTimeWindowDTO(input.windowStart, input.windowEnd),
    priority: input.priority,
    notes: input.notes || null,
  };
}

// ---------------------------------------------------------------------------
// Rota (suporte a múltiplos veículos)
// ---------------------------------------------------------------------------

function toVehicleRoute(dto: VehicleRouteDTO): VehicleRoute {
  return {
    vehicleId: String(dto.vehicle.id),
    vehicleName: dto.vehicle.name,
    capacity: dto.vehicle.capacity,
    load: dto.load,
    stopIds: dto.stops.map((stop) => String(stop.delivery_id)),
    distanceKm: Math.round(dto.distance_m / 100) / 10,
    durationMin: dto.total_min,
    travelMin: dto.travel_min,
    waitMin: dto.wait_min,
    serviceMin: dto.service_min,
  };
}

export function toRoutePlan(dto: RoutePlanDTO): RoutePlan {
  const routes = dto.routes.map(toVehicleRoute);
  const totalDistanceKm =
    Math.round(routes.reduce((sum, route) => sum + route.distanceKm, 0) * 10) / 10;
  const totalDurationMin = routes.reduce((sum, route) => sum + route.durationMin, 0);

  return {
    id: String(dto.id),
    origin: toPlace(dto.origin),
    routes,
    totalDistanceKm,
    totalDurationMin,
    status: dto.status,
    isSimulation: dto.matrix_source === "manual",
  };
}