import type { Delivery, NewDelivery, RoutePlan } from "@/types/domain";
import { issueLabel } from "@/utils/format";
import { currentHHmm } from "@/utils/time";
import type { DeliveriesService } from "../deliveriesService";
import { DEFAULT_WINDOW_END, DEFAULT_WINDOW_START } from "../mappers";
import { fakeGeocode } from "./fakeGeocode";
import { loadDb, recalcRoute, resetDb, saveDb, wait, type MockDb } from "./mockDb";

function build(input: NewDelivery, db: MockDb, position: number): Delivery {
  return {
    id: crypto.randomUUID(),
    ...input,
    orderCode: input.orderCode || `#${1001 + db.deliveries.length + position}`,
    windowStart: input.windowStart.trim() || DEFAULT_WINDOW_START,
    windowEnd: input.windowEnd.trim() || DEFAULT_WINDOW_END,
    ...fakeGeocode(input.address, db.route.origin),
    status: "waiting_departure",
    issueReason: null,
    completedAt: null,
    history: [{ at: currentHHmm(), text: "Pedido cadastrado" }],
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
    saveDb({
      ...db,
      deliveries: [...db.deliveries, created],
    });
    return created;
  },

  async createMany(inputs) {
    await wait();
    const db = loadDb();
    const created = inputs.map((input, index) => build(input, db, index));
    saveDb({
      ...db,
      deliveries: [...db.deliveries, ...created],
    });
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