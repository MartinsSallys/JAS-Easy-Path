import type { Delivery, RoutePlan, VehicleRoute } from "@/types/domain";

/** Entregas na ordem da rota de um veículo específico (a rota guarda só os ids). */
export function orderedStops(
  deliveries: Delivery[],
  route: VehicleRoute | null | undefined,
): Delivery[] {
  if (!route) return [];
  const byId = new Map(deliveries.map((d) => [d.id, d]));
  return route.stopIds.map((id) => byId.get(id)).filter((d): d is Delivery => d !== undefined);
}

/** Atalho para pegar a rota ativa pelo vehicleId selecionado (ou a primeira disponível). */
export function selectVehicleRoute(
  plan: RoutePlan | null,
  vehicleId?: string | null,
): VehicleRoute | null {
  if (!plan || plan.routes.length === 0) return null;
  if (vehicleId) {
    return plan.routes.find((r) => r.vehicleId === vehicleId) ?? plan.routes[0];
  }
  return plan.routes[0];
}

/** "Pendente de entrega" = ainda precisa ser visitada. */
export const needsVisit = (d: Delivery) =>
  d.status === "waiting_departure" || d.status === "in_progress";