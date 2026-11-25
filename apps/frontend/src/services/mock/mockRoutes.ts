import type { Delivery } from "@/types/domain";
import { nearestNeighborOrder } from "@/utils/geo";
import { HttpError } from "../http";
import type { RoutesService } from "../routeService";
import { loadDb, recalcRoute, saveDb, wait } from "./mockDb";

export const mockRoutesService: RoutesService = {
  async get() {
    await wait();
    return loadDb().route;
  },

  /** SIMULAÇÃO: preserva concluídas/pendências e reordena apenas entregas elegíveis. */
  async optimize() {
    await wait(300);
    const db = loadDb();
    const byId = new Map(db.deliveries.map((d) => [d.id, d]));

    const elegiveis = db.deliveries.filter(
      (d) => d.status === "waiting_departure" || d.status === "in_progress",
    );
    if (elegiveis.length === 0) {
      throw new HttpError(
        422,
        "Não há entregas pendentes elegíveis para otimizar. Entregas já concluídas ou com falha não entram em nova rota.",
      );
    }

    const assignedIds = new Set(db.route.routes.flatMap((vr) => vr.stopIds));
    const unassignedEligible = elegiveis.filter((d) => !assignedIds.has(d.id));

    const optimizedRoutes = db.route.routes.map((vehicleRoute, idx) => {
      const currentStops = vehicleRoute.stopIds
        .map((id) => byId.get(id))
        .filter((d): d is Delivery => d !== undefined);

        const preserved = currentStops.filter(
        (d) => d.status === "completed" || d.status === "issue",
      );
      const vehicleEligible = [
        ...currentStops.filter(
          (d) => d.status === "waiting_departure" || d.status === "in_progress",
        ),
        ...(idx === 0 ? unassignedEligible : []),
      ];

      const start =
        preserved.length > 0 ? preserved[preserved.length - 1] : db.route.origin;
      const reordered = [...preserved, ...nearestNeighborOrder(start, vehicleEligible)];

      return {
        ...vehicleRoute,
        stopIds: reordered.map((d) => d.id),
      };
    });

    const next = recalcRoute({
      ...db,
      route: { ...db.route, routes: optimizedRoutes, isSimulation: true },
    });
    saveDb(next);
    return next.route;
  },

  async share() {
    await wait();
    const { route } = loadDb();
    // No modo demo o link só funciona NESTE navegador (os dados estão no localStorage).
    return `${window.location.origin}/entregador?rota=${route.id}`;
  },
};