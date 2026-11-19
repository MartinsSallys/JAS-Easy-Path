import type { Delivery, NewDelivery, RoutePlan } from "@/types/domain";
import type { DeliveryDTO, NewDeliveryDTO, RoutePlanDTO } from "@/types/dto";

export function toDelivery(dto: DeliveryDTO): Delivery {
  return {
    id: dto.id,
    orderCode: dto.order_code,
    customerName: dto.customer_name,
    phone: dto.phone ?? "",
    address: dto.address,
    lat: dto.lat,
    lng: dto.lng,
    windowStart: dto.window_start,
    windowEnd: dto.window_end,
    priority: dto.priority,
    status: dto.status,
    notes: dto.notes ?? "",
    issueReason: dto.issue_reason,
    completedAt: dto.completed_at,
    history: dto.history,
  };
}

export function toNewDeliveryDTO(input: NewDelivery): NewDeliveryDTO {
  return {
    order_code: input.orderCode || null,
    customer_name: input.customerName,
    phone: input.phone || null,
    address: input.address,
    window_start: input.windowStart,
    window_end: input.windowEnd,
    priority: input.priority,
    notes: input.notes || null,
  };
}

export function toRoutePlan(dto: RoutePlanDTO): RoutePlan {
  return {
    id: dto.id,
    driverName: dto.driver_name,
    origin: dto.origin,
    stopIds: dto.stop_ids,
    distanceKm: dto.distance_km,
    durationMin: dto.duration_min,
    status: dto.status,
    isSimulation: dto.is_simulation,
  };
}