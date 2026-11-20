import type { Delivery, RoutePlan } from "@/types/domain";

/** Entregas na ordem da rota (a rota guarda só os ids). */
export function orderedStops(deliveries: Delivery[], route: RoutePlan | null): Delivery[] {
  if (!route) return [];
  const byId = new Map(deliveries.map((d) => [d.id, d]));
  return route.stopIds.map((id) => byId.get(id)).filter((d): d is Delivery => d !== undefined);
}

/** "Pendente de entrega" = ainda precisa ser visitada. */
export const needsVisit = (d: Delivery) => d.status === "waiting_departure" || d.status === "in_progress";