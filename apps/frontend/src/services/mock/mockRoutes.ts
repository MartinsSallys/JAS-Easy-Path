import type { Delivery } from "@/types/domain";
import { nearestNeighborOrder } from "@/utils/geo";
import type { RoutesService } from "../routeService";
import { loadDb, recalcRoute, saveDb, wait } from "./mockDb";

export const mockRoutesService: RoutesService = {
  async get() {
    await wait();
    return loadDb().route;
  },

  /** SIMULAÇÃO: mantém as entregas já concluídas e reordena só as que faltam em cada veículo. */
  async optimize() {
    await wait(600);
    const db = loadDb();
    const byId = new Map(db.deliveries.map((d) => [d.id, d]));

    const optimizedRoutes = db.route.routes.map((vehicleRoute) => {
      const stops = vehicleRoute.stopIds
        .map((id) => byId.get(id))
        .filter((d): d is Delivery => d !== undefined);

      const done = stops.filter((d) => d.status === "completed");
      const todo = stops.filter((d) => d.status !== "completed");
      const start = done.length > 0 ? done[done.length - 1] : db.route.origin;
      const reordered = [...done, ...nearestNeighborOrder(start, todo)];

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