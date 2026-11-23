import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Delivery, RoutePlan } from "@/types/domain";
import { useAppStore } from "@/store/useAppStore";
import DriverPage from "./DriverPage";

vi.mock("@/store/useAppStore", () => ({
  useAppStore: vi.fn(),
}));

type MockStoreState = {
  deliveries: Delivery[];
  route: RoutePlan | null;
  initialized: boolean;
  loading: boolean;
  error: string | null;
  nowSimulated: string;
  refresh: () => Promise<void>;
  clearError: () => void;
  completeDelivery: () => Promise<void>;
  reportIssue: () => Promise<void>;
};

let currentState: MockStoreState;

const setMockState = (patch: Partial<MockStoreState>) => {
  currentState = { ...currentState, ...patch };
};

const renderDriver = () =>
  renderToStaticMarkup(
    <MemoryRouter>
      <DriverPage />
    </MemoryRouter>,
  );

const completedDelivery: Delivery = {
  id: "del-1",
  orderCode: "#1001",
  customerName: "Ana Paula",
  phone: "71999990000",
  address: "Rua A, 10",
  lat: -13.37,
  lng: -39.07,
  windowStart: "18:00",
  windowEnd: "20:00",
  priority: "normal",
  status: "completed",
  notes: "",
  issueReason: null,
  completedAt: "19:30",
  history: [],
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

describe("DriverPage — estados distintos da tela do entregador", () => {
  beforeEach(() => {
    currentState = {
      deliveries: [],
      route: null,
      initialized: false,
      loading: false,
      error: null,
      nowSimulated: "19:45",
      refresh: vi.fn(),
      clearError: vi.fn(),
      completeDelivery: vi.fn(),
      reportIssue: vi.fn(),
    };
    vi.mocked(useAppStore).mockImplementation((selector) =>
      selector(currentState as never),
    );
  });

  it("exibe carregamento inicial sem afirmar que as paradas foram finalizadas", () => {
    setMockState({ loading: true, initialized: false });
    const html = renderDriver();
    expect(html).toContain("Carregando rota do dia...");
    expect(html).not.toContain("Todas as paradas finalizadas!");
  });

  it("exibe estado de ausência de rota quando initialized=true e route=null", () => {
    setMockState({ loading: false, initialized: true, route: null });
    const html = renderDriver();
    expect(html).toContain("Nenhuma rota disponível");
    expect(html).not.toContain("Todas as paradas finalizadas!");
  });

  it("exibe erro do store com opção de tentar novamente", () => {
    setMockState({
      loading: false,
      initialized: true,
      error: "Falha ao registrar entrega",
    });
    const html = renderDriver();
    expect(html).toContain("Falha ao registrar entrega");
    expect(html).toContain("Tentar novamente");
  });

  it("exibe conclusão apenas quando há rota com paradas e todas foram concluídas", () => {
    setMockState({
      loading: false,
      initialized: true,
      deliveries: [completedDelivery],
      route: sampleRoute,
    });
    const html = renderDriver();
    expect(html).toContain("Todas as paradas finalizadas!");
  });
});