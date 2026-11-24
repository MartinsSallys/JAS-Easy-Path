import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Delivery, NewDelivery, RoutePlan } from "@/types/domain";
import { deliveriesService } from "@/services/deliveriesService";
import { routesService } from "@/services/routeService";
import { useAppStore } from "./useAppStore";

const sampleDelivery: Delivery = {
  id: "del-1",
  orderCode: "#1001",
  customerName: "Ana Paula",
  phone: "71999990000",
  address: "Rua A, 10",
  lat: -13.37,
  lng: -39.07,
  windowStart: "18:00",
  windowEnd: "20:00",
  hasExplicitTimeWindow: true,
  priority: "normal",
  status: "waiting_departure",
  notes: "",
  issueReason: null,
  completedAt: null,
  history: [],
};

const sampleInput: NewDelivery = {
  orderCode: "#1002",
  customerName: "Carlos Lima",
  phone: "71988880000",
  address: "Rua B, 20",
  windowStart: "19:00",
  windowEnd: "20:30",
  priority: "normal",
  notes: "",
};

const sampleRoute: RoutePlan = {
  id: "route-1",
  status: "planned",
  origin: { name: "Loja", address: "Centro", lat: -13.37, lng: -39.07 },
  routes: [
    {
      vehicleId: "v-1",
      vehicleName: "Moto 01",
      capacity: 10,
      load: 1,
      stopIds: ["del-1"],
      distanceKm: 2.5,
      travelMin: 6,
      waitMin: 0,
      serviceMin: 8,
      durationMin: 14,
    },
  ],
  totalDistanceKm: 2.5,
  totalDurationMin: 14,
  isSimulation: false,
};

describe("useAppStore — regressão do fluxo de dados e erros", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useAppStore.setState({
      deliveries: [],
      route: null,
      initialized: false,
      loading: false,
      error: null,
      nowSimulated: "19:45",
    });
  });

  it("preserva entregas carregadas quando ainda não existe rota do dia (route === null)", async () => {
    vi.spyOn(deliveriesService, "list").mockResolvedValue([sampleDelivery]);
    vi.spyOn(routesService, "get").mockResolvedValue(null);

    await useAppStore.getState().refresh();

    const state = useAppStore.getState();
    expect(state.initialized).toBe(true);
    expect(state.deliveries).toEqual([sampleDelivery]);
    expect(state.route).toBeNull();
    expect(state.error).toBeNull();
  });

  it("rejeita addDelivery e grava erro no estado quando a API falha ao criar", async () => {
    vi.spyOn(deliveriesService, "create").mockRejectedValue(new Error("Endereço inválido"));

    await expect(useAppStore.getState().addDelivery(sampleInput)).rejects.toThrow(
      "Endereço inválido",
    );

    const state = useAppStore.getState();
    expect(state.error).toBe("Endereço inválido");
    expect(state.deliveries).toHaveLength(0);
    expect(state.loading).toBe(false);
  });

  it("substitui a entrega na lista ao salvar edição", async () => {
    const updated: Delivery = { ...sampleDelivery, customerName: "Ana Paula Editada" };
    const updateSpy = vi.spyOn(deliveriesService, "update").mockResolvedValue(updated);
    vi.spyOn(deliveriesService, "list").mockResolvedValue([updated]);
    vi.spyOn(routesService, "get").mockResolvedValue(null);
    useAppStore.setState({ deliveries: [sampleDelivery], initialized: true });

    await useAppStore.getState().updateDelivery("del-1", sampleInput);

    expect(updateSpy).toHaveBeenCalledWith("del-1", sampleInput);
    expect(useAppStore.getState().deliveries).toEqual([updated]);
    expect(useAppStore.getState().error).toBeNull();
  });

  it("não falha o cadastro quando create salva mas o reload subsequente falha", async () => {
    const created: Delivery = { ...sampleDelivery, id: "del-2", orderCode: "#1002" };
    vi.spyOn(deliveriesService, "create").mockResolvedValue(created);
    vi.spyOn(deliveriesService, "list").mockRejectedValue(new Error("Timeout ao listar"));
    vi.spyOn(routesService, "get").mockResolvedValue(sampleRoute);

    await expect(useAppStore.getState().addDelivery(sampleInput)).resolves.toBeUndefined();

    const state = useAppStore.getState();
    expect(state.deliveries).toEqual([created]);
    expect(state.error).toContain("Alteração salva");
  });
});