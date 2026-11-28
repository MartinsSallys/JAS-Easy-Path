import type { Delivery, NewDelivery, RoutePlan } from "@/types/domain";
import { isDeliveryEditable } from "@/utils/delivery";
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
    hasExplicitTimeWindow: input.windowStart.trim() !== "" || input.windowEnd.trim() !== "",
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

/** No mock o vínculo com rota (`routeId`) é derivado das paradas do plano do dia. */
function routeIdOf(deliveryId: string, db: MockDb): string | null {
  const linked = db.route.routes.some((r) => r.stopIds.includes(deliveryId));
  return linked ? db.route.id : null;
}

function change(id: string, update: (d: Delivery, db: MockDb) => Delivery): Delivery {
  const db = loadDb();
  const current = db.deliveries.find((d) => d.id === id);
  if (!current) throw new Error("Entrega não encontrada.");
  const updated = update(current, db);
  saveDb({ ...db, deliveries: db.deliveries.map((d) => (d.id === id ? updated : d)) });
  return updated;
}

export const mockDeliveriesService: DeliveriesService = {
  async list() {
    await wait();
    const db = loadDb();
    return db.deliveries.map((d) => ({ ...d, routeId: routeIdOf(d.id, db) }));
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

  async update(id, input) {
    await wait();
    const origin = loadDb().route.origin;
    const updated = change(id, (d, db) => {
      if (!isDeliveryEditable({ ...d, routeId: routeIdOf(d.id, db) })) {
        throw new Error(
          "Só é possível editar entregas aguardando — a rota já otimizada não é recalculada.",
        );
      }
      const fixingAddressIssue =
        d.status === "issue" && d.issueReason === "address_not_found";
      return {
        ...d,
        ...input,
        orderCode: input.orderCode || d.orderCode,
        hasExplicitTimeWindow:
          input.windowStart.trim() !== "" || input.windowEnd.trim() !== "",
        ...(input.address !== d.address ? fakeGeocode(input.address, origin) : {}),
        status: fixingAddressIssue ? "waiting_departure" : d.status,
        issueReason: fixingAddressIssue ? null : d.issueReason,
        history: [...d.history, { at: currentHHmm(), text: "Pedido editado" }],
      };
    });
    saveDb(recalcRoute(loadDb()));
    return updated;
  },

  async remove(id) {
    await wait();
    const db = loadDb();
    const target = db.deliveries.find((d) => d.id === id);
    // Mesma regra do DELETE /entregas/{id} (issue #32): só estados
    // operacionais em curso são bloqueados. Entrega com pendência pode
    // ser cancelada — o backend preserva o motivo e registra a transição
    // FALHA -> CANCELADA; aqui o registro some da lista, como na API.
    if (target?.status === "in_progress" || target?.status === "completed") {
      throw new Error(
        "Entrega em andamento ou concluída não pode ser excluída — faz parte do histórico da rota.",
      );
    }
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