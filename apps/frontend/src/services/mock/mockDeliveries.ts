import type { Delivery, NewDelivery, RoutePlan } from "@/types/domain";
import { issueLabel } from "@/utils/format";
import { currentHHmm } from "@/utils/time";
import type { DeliveriesService } from "../deliveriesService";
import { fakeGeocode } from "./fakeGeocode";
import { loadDb, recalcRoute, resetDb, saveDb, wait, type MockDb } from "./mockDb";

function build(input: NewDelivery, db: MockDb, position: number): Delivery {
  return {
    id: crypto.randomUUID(),
    ...input,
    orderCode: input.orderCode || `#${1001 + db.deliveries.length + position}`,
    ...fakeGeocode(input.address, db.route.origin),
    status: "waiting_departure",
    issueReason: null,
    completedAt: null,
    history: [{ at: currentHHmm(), text: "Pedido cadastrado" }],
  };
}

function appendStopsToFirstVehicle(route: RoutePlan, newIds: string[]): RoutePlan {
  if (route.routes.length === 0) return route;
  const [first, ...rest] = route.routes;
  return {
    ...route,
    routes: [{ ...first, stopIds: [...first.stopIds, ...newIds] }, ...rest],
  };
}

function removeStopFromVehicles(route: RoutePlan, targetId: string): RoutePlan {
  return {
    ...route,
    routes: route.routes.map((r) => ({
      ...r,
      stopIds: r.stopIds.filter((stopId) => stopId !== targetId),
    })),
  };
}

function change(id: string, update: (d: Delivery) => Delivery): Delivery {
  const db = loadDb();
  const current = db.deliveries.find((d) => d.id === id);
  if (!current) throw new Error("Entrega não encontrada.");
  const updated = update(current);
  saveDb({ ...db, deliveries: db.deliveries.map((d) => (d.id === id ? updated : d)) });
  return updated;
}

export const mockDeliveriesService: DeliveriesService = {
  async list() {
    await wait();
    return loadDb().deliveries;
  },

  async create(input) {
    await wait();
    const db = loadDb();
    const created = build(input, db, 0);
    saveDb(
      recalcRoute({
        deliveries: [...db.deliveries, created],
        route: appendStopsToFirstVehicle(db.route, [created.id]),
      }),
    );
    return created;
  },

  async createMany(inputs) {
    await wait();
    const db = loadDb();
    const created = inputs.map((input, index) => build(input, db, index));
    saveDb(
      recalcRoute({
        deliveries: [...db.deliveries, ...created],
        route: appendStopsToFirstVehicle(
          db.route,
          created.map((d) => d.id),
        ),
      }),
    );
    return created;
  },

  async remove(id) {
    await wait();
    const db = loadDb();
    saveDb(
      recalcRoute({
        deliveries: db.deliveries.filter((d) => d.id !== id),
        route: removeStopFromVehicles(db.route, id),
      }),
    );
  },

  async complete(id, at) {
    await wait();
    return change(id, (d) => ({
      ...d,
      status: "completed",
      completedAt: at,
      issueReason: null,
      history: [...d.history, { at, text: "Entrega concluída" }],
    }));
  },

  async reportIssue(id, reason, note, at) {
    await wait();
    return change(id, (d) => ({
      ...d,
      status: "issue",
      issueReason: reason,
      notes: note || d.notes,
      history: [...d.history, { at, text: `Pendência: ${issueLabel[reason]}` }],
    }));
  },

  async resetDemo() {
    await wait();
    resetDb();
  },
};