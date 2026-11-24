import type {
  Delivery,
  DeliveryStatus,
  IssueReason,
  NewDelivery,
  Place,
  Priority,
  RoutePlan,
  VehicleRoute,
} from "@/types/domain";
import type {
  BackendDepositoResponseDTO,
  BackendEntregaCreateDTO,
  BackendEntregaResponseDTO,
  BackendEntregaStatus,
  BackendRotaStatus,
  BackendRotaWithParadasResponseDTO,
  BackendVeiculoResponseDTO,
  DeliveryDTO,
  NewDeliveryDTO,
  PlaceDTO,
  RoutePlanDTO,
  TimeWindowDTO,
  VehicleRouteDTO,
} from "@/types/dto";

export const DEFAULT_DEMAND = 1;
export const DEFAULT_WINDOW_START = "08:00";
export const DEFAULT_WINDOW_END = "18:00";

const MINUTES_PER_DAY = 1440;

export function hhmmToMinutes(text: string): number {
  const match = /^(\d{1,2}):(\d{2})$/.exec(text.trim());
  if (!match) throw new Error(`Horário inválido: "${text}". Use HH:mm.`);
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  const valid = minutes <= 59 && (hours < 24 || (hours === 24 && minutes === 0));
  if (!valid) throw new Error(`Horário fora do intervalo 00:00 a 24:00: "${text}".`);
  return hours * 60 + minutes;
}

export function minutesToHHmm(totalMinutes: number): string {
  const clamped = Math.min(Math.max(Math.round(totalMinutes), 0), MINUTES_PER_DAY);
  const hours = Math.floor(clamped / 60);
  const minutes = clamped % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

/**
 * Lê hora HH:mm:
 * - Se vier com offset explícito (ex.: "2026-11-19T19:50:00-03:00"), mantém a hora local do texto.
 * - Se vier ISO naive do backend (UTC sem Z, ex.: "2026-11-24T16:00:00"), converte de UTC para o fuso local.
 */
export function wallClockHHmm(value: string): string {
  const trimmed = value.trim();
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?[+-]\d{2}:\d{2}$/.test(trimmed)) {
    return trimmed.slice(11, 16);
  }
  const naiveUtcMatch = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(Z)?$/.exec(trimmed);
  if (naiveUtcMatch) {
    const isoUtc = naiveUtcMatch[1] ? trimmed : `${trimmed}Z`;
    const date = new Date(isoUtc);
    if (!Number.isNaN(date.getTime())) {
      return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
    }
  }
  const timeMatch = /^(\d{2}:\d{2})(?::\d{2})?$/.exec(trimmed);
  return timeMatch ? timeMatch[1] : trimmed;
}

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
// Metadados seguros em observacoes (sem quebra por "|" ou "Cliente:")
// ---------------------------------------------------------------------------

interface ObservacoesMetaPayload {
  c?: string;
  p?: string;
  pr?: Priority;
  r?: IssueReason | null;
}

interface ParsedObservacoes {
  customerName: string;
  phone: string;
  priority: Priority;
  issueReason: IssueReason | null;
  notes: string;
}

const META_MARKER = "\n[JAS_META]:";
const VALID_PRIORITIES: Priority[] = ["low", "normal", "high"];
const VALID_REASONS: IssueReason[] = [
  "customer_absent",
  "address_not_found",
  "customer_refused",
  "operational",
  "other",
];

export function formatBackendObservacoes(meta: {
  customerName?: string;
  phone?: string;
  priority?: Priority;
  issueReason?: IssueReason | null;
  notes?: string;
}): string | null {
  const payload: ObservacoesMetaPayload = {};
  if (meta.customerName?.trim()) payload.c = meta.customerName.trim();
  if (meta.phone?.trim()) payload.p = meta.phone.trim();
  if (meta.priority && meta.priority !== "normal") payload.pr = meta.priority;
  if (meta.issueReason) payload.r = meta.issueReason;

  const cleanNotes = (meta.notes ?? "").trim();
  const hasMeta = Object.keys(payload).length > 0;

  if (!cleanNotes && !hasMeta) return null;
  if (!hasMeta) return cleanNotes;
  return `${cleanNotes}${META_MARKER}${JSON.stringify(payload)}`;
}

export function parseBackendObservacoes(
  raw: string | null,
  fallbackCustomer: string,
): ParsedObservacoes {
  if (!raw) {
    return {
      customerName: fallbackCustomer,
      phone: "",
      priority: "normal",
      issueReason: null,
      notes: "",
    };
  }

  const markerIdx = raw.lastIndexOf(META_MARKER);
  if (markerIdx !== -1) {
    const notesPart = raw.slice(0, markerIdx).trim();
    const jsonPart = raw.slice(markerIdx + META_MARKER.length).trim();
    try {
      const parsed = JSON.parse(jsonPart) as ObservacoesMetaPayload;
      const priority =
        parsed.pr && VALID_PRIORITIES.includes(parsed.pr) ? parsed.pr : "normal";
      const issueReason =
        parsed.r && VALID_REASONS.includes(parsed.r) ? parsed.r : null;
      return {
        customerName: parsed.c?.trim() || fallbackCustomer,
        phone: parsed.p?.trim() ?? "",
        priority,
        issueReason,
        notes: notesPart,
      };
    } catch {
      // fallback abaixo se JSON inválido
    }
  }

  return {
    customerName: fallbackCustomer,
    phone: "",
    priority: "normal",
    issueReason: null,
    notes: raw.trim(),
  };
}

// ---------------------------------------------------------------------------
// Entregas (Contrato legado/mock + Backend FastAPI real)
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

const BACKEND_TO_FRONT_STATUS: Record<BackendEntregaStatus, DeliveryStatus> = {
  PENDENTE: "waiting_departure",
  ATRIBUIDA: "waiting_departure",
  EM_ROTA: "in_progress",
  ENTREGUE: "completed",
  FALHA: "issue",
  CANCELADA: "issue",
};

const BACKEND_STATUS_LABEL: Record<BackendEntregaStatus, string> = {
  PENDENTE: "Aguardando saída",
  ATRIBUIDA: "Atribuída à rota",
  EM_ROTA: "Em rota",
  ENTREGUE: "Entrega concluída",
  FALHA: "Pendência registrada",
  CANCELADA: "Entrega cancelada",
};

export function toDeliveryFromBackend(dto: BackendEntregaResponseDTO): Delivery {
  const parsed = parseBackendObservacoes(dto.observacoes, `Pedido ${dto.pedido_id}`);
  const status = BACKEND_TO_FRONT_STATUS[dto.status];
  const windowStart = dto.janela_inicio ? wallClockHHmm(dto.janela_inicio) : DEFAULT_WINDOW_START;
  const windowEnd = dto.janela_fim ? wallClockHHmm(dto.janela_fim) : DEFAULT_WINDOW_END;

  const history = [{ at: wallClockHHmm(dto.created_at), text: "Pedido cadastrado" }];
  if (dto.updated_at && dto.updated_at !== dto.created_at) {
    history.push({
      at: wallClockHHmm(dto.updated_at),
      text: BACKEND_STATUS_LABEL[dto.status],
    });
  }

  return {
    id: String(dto.id),
    orderCode: dto.pedido_id,
    customerName: parsed.customerName,
    phone: parsed.phone,
    address: dto.endereco,
    lat: dto.latitude,
    lng: dto.longitude,
    windowStart,
    windowEnd,
    priority: parsed.priority,
    status,
    notes: parsed.notes,
    issueReason: status === "issue" ? (parsed.issueReason ?? "other") : null,
    completedAt: status === "completed" ? wallClockHHmm(dto.updated_at) : null,
    history,
  };
}

export function toBackendEntregaCreateDTO(
  input: NewDelivery,
  coords: { latitude: number; longitude: number },
  fallbackIndex = 1,
): BackendEntregaCreateDTO {
  const startRaw = input.windowStart.trim();
  const endRaw = input.windowEnd.trim();
  if ((startRaw === "") !== (endRaw === "")) {
    throw new Error("Informe o início e o fim da janela, ou deixe os dois em branco.");
  }

  const orderCode =
    input.orderCode.trim() || `#${Date.now().toString().slice(-4)}-${fallbackIndex}`;

  return {
    pedido_id: orderCode,
    endereco: input.address.trim(),
    latitude: coords.latitude,
    longitude: coords.longitude,
    demanda: DEFAULT_DEMAND,
    janela_inicio: startRaw === "" ? DEFAULT_WINDOW_START : startRaw,
    janela_fim: endRaw === "" ? DEFAULT_WINDOW_END : endRaw,
    observacoes: formatBackendObservacoes({
      customerName: input.customerName,
      phone: input.phone,
      priority: input.priority,
      notes: input.notes,
    }),
  };
}

// ---------------------------------------------------------------------------
// Rota (Contrato legado/mock + Backend FastAPI real)
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

const BACKEND_ROTA_STATUS: Record<BackendRotaStatus, RoutePlan["status"]> = {
  RASCUNHO: "planned",
  OTIMIZADA: "planned",
  EM_ANDAMENTO: "running",
  CONCLUIDA: "finished",
  CANCELADA: "finished",
};

export function toRoutePlanFromBackend(
  rota: BackendRotaWithParadasResponseDTO,
  deposito: BackendDepositoResponseDTO,
  veiculo: BackendVeiculoResponseDTO | null,
): RoutePlan {
  const deliveryStops = [...rota.paradas]
    .filter((p) => p.entrega_id !== null)
    .sort((a, b) => a.ordem - b.ordem);

  const stopIds = deliveryStops.map((p) => String(p.entrega_id));
  const load = deliveryStops.reduce((sum, p) => sum + (p.demanda || DEFAULT_DEMAND), 0);
  const serviceMin = deliveryStops.reduce((sum, p) => sum + (p.tempo_servico_min || 8), 0);
  const distanceKm = Math.round((rota.distancia_total_km ?? 0) * 10) / 10;
  const durationMin = rota.tempo_total_min ?? serviceMin;
  const travelMin = Math.max(durationMin - serviceMin, 0);

  const vehicleRoute: VehicleRoute = {
    vehicleId: veiculo ? String(veiculo.id) : String(rota.veiculo_id ?? 1),
    vehicleName: veiculo ? `${veiculo.tipo} (${veiculo.placa})` : "Veículo padrão",
    capacity: veiculo ? veiculo.capacidade : Math.max(load, 10),
    load,
    stopIds,
    distanceKm,
    durationMin,
    travelMin,
    waitMin: 0,
    serviceMin,
  };

  return {
    id: String(rota.id),
    origin: {
      name: deposito.nome,
      address: deposito.endereco,
      lat: deposito.latitude,
      lng: deposito.longitude,
    },
    routes: stopIds.length > 0 || rota.status === "OTIMIZADA" ? [vehicleRoute] : [],
    totalDistanceKm: distanceKm,
    totalDurationMin: durationMin,
    status: BACKEND_ROTA_STATUS[rota.status],
    isSimulation: false,
  };
}