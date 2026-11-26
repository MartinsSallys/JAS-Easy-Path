import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Delivery, NewDelivery, RoutePlan } from "@/types/domain";
import type { MockDb } from "./mockDb";
import { mockDeliveriesService } from "./mockDeliveries";

const STORAGE_KEY = "jas-mock-db-v2";

const store = new Map<string, string>();

vi.stubGlobal("localStorage", {
  getItem: (key: string) => store.get(key) ?? null,
  setItem: (key: string, value: string) => void store.set(key, value),
  removeItem: (key: string) => void store.delete(key),
  clear: () => store.clear(),
});

const route: RoutePlan = {
  id: "rota-hoje",
  origin: { name: "Loja", address: "Centro", lat: -12.9714, lng: -38.5014 },
  routes: [],
  totalDistanceKm: 0,
  totalDurationMin: 0,
  status: "planned",
  isSimulation: false,
};

const baseDelivery: Delivery = {
  id: "del-1",
  orderCode: "#1001",
  customerName: "Ana Paula",
  phone: "",
  address: "Rua A, 10",
  lat: -12.97,
  lng: -38.5,
  windowStart: "18:00",
  windowEnd: "20:00",
  hasExplicitTimeWindow: true,
  priority: "normal",
  status: "waiting_departure",
  notes: "",
  issueReason: null,
  completedAt: null,
  history: [{ at: "18:00", text: "Pedido cadastrado" }],
};

const input: NewDelivery = {
  orderCode: "#1001",
  customerName: "Ana Paula",
  phone: "",
  address: "Rua B, 20 - Corrigido",
  windowStart: "18:00",
  windowEnd: "20:00",
  priority: "normal",
  notes: "",
};

function seedDb(deliveries: Delivery[]) {
  const db: MockDb = { deliveries, route };
  store.set(STORAGE_KEY, JSON.stringify(db));
}

describe("mockDeliveriesService.update — regra de edição por status", () => {
  beforeEach(() => {
    store.clear();
  });

  it("rejeita edição de entrega concluída", async () => {
    seedDb([{ ...baseDelivery, status: "completed", completedAt: "19:30" }]);

    await expect(mockDeliveriesService.update("del-1", input)).rejects.toThrow(
      "Só é possível editar entregas aguardando",
    );
  });

  it("rejeita edição de pendência que não seja de endereço", async () => {
    seedDb([{ ...baseDelivery, status: "issue", issueReason: "customer_absent" }]);

    await expect(mockDeliveriesService.update("del-1", input)).rejects.toThrow(
      "Só é possível editar entregas aguardando",
    );
  });

  it("corrige endereço de pendência 'endereço não localizado' e volta para aguardando", async () => {
    seedDb([{ ...baseDelivery, status: "issue", issueReason: "address_not_found" }]);

    const updated = await mockDeliveriesService.update("del-1", input);

    expect(updated.address).toBe("Rua B, 20 - Corrigido");
    expect(updated.status).toBe("waiting_departure");
    expect(updated.issueReason).toBeNull();
    expect(updated.history.at(-1)?.text).toBe("Pedido editado");
  });

  it("rejeita edição de entrega já vinculada a uma rota", async () => {
    const linkedRoute: RoutePlan = {
      ...route,
      routes: [
        {
          vehicleId: "v1",
          vehicleName: "Moto 01",
          capacity: 12,
          load: 1,
          stopIds: ["del-1"],
          distanceKm: 0,
          durationMin: 0,
          travelMin: 0,
          waitMin: 0,
          serviceMin: 0,
        },
      ],
    };
    const db: MockDb = { deliveries: [{ ...baseDelivery }], route: linkedRoute };
    store.set(STORAGE_KEY, JSON.stringify(db));

    await expect(mockDeliveriesService.update("del-1", input)).rejects.toThrow(
      "Só é possível editar entregas aguardando",
    );
  });
});

describe("mockDeliveriesService.remove — regra de exclusão por vínculo", () => {
  const linkedRoute: RoutePlan = {
    ...route,
    routes: [
      {
        vehicleId: "v1",
        vehicleName: "Moto 01",
        capacity: 12,
        load: 1,
        stopIds: ["del-1"],
        distanceKm: 0,
        durationMin: 0,
        travelMin: 0,
        waitMin: 0,
        serviceMin: 0,
      },
    ],
  };

  beforeEach(() => {
    store.clear();
  });

  it("remove entrega sem vínculo de rota", async () => {
    seedDb([{ ...baseDelivery }]);

    await mockDeliveriesService.remove("del-1");

    const db = JSON.parse(store.get(STORAGE_KEY)!) as MockDb;
    expect(db.deliveries).toHaveLength(0);
  });

  it("remove entrega vinculada e tira a parada da rota", async () => {
    const db: MockDb = { deliveries: [{ ...baseDelivery }], route: linkedRoute };
    store.set(STORAGE_KEY, JSON.stringify(db));

    await mockDeliveriesService.remove("del-1");

    const persisted = JSON.parse(store.get(STORAGE_KEY)!) as MockDb;
    expect(persisted.deliveries).toHaveLength(0);
    expect(persisted.route.routes[0].stopIds).not.toContain("del-1");
  });

  it("rejeita exclusão de entrega concluída ou em andamento", async () => {
    seedDb([{ ...baseDelivery, status: "completed", completedAt: "19:30" }]);

    await expect(mockDeliveriesService.remove("del-1")).rejects.toThrow(
      "não pode ser excluída",
    );

    const persisted = JSON.parse(store.get(STORAGE_KEY)!) as MockDb;
    expect(persisted.deliveries).toHaveLength(1);
  });

  it("rejeita exclusão de entrega com pendência (FALHA)", async () => {
    // Mesma regra do backend: ocorrência registrada é histórico operacional
    seedDb([{ ...baseDelivery, status: "issue", issueReason: "customer_absent" }]);

    await expect(mockDeliveriesService.remove("del-1")).rejects.toThrow(
      "não pode ser excluída",
    );

    const persisted = JSON.parse(store.get(STORAGE_KEY)!) as MockDb;
    expect(persisted.deliveries).toHaveLength(1);
    expect(persisted.deliveries[0].status).toBe("issue");
  });
});
