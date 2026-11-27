import { beforeEach, describe, expect, it, vi } from "vitest";

// Força o serviço mock mesmo quando o .env.local aponta para a API real —
// o cenário fictício não pode depender do backend de pé.
vi.mock("@/services/config", () => ({
  USE_MOCK: true,
  API_URL: "http://test.local",
}));

import type { MockDb } from "@/services/mock/mockDb";
import { saveDb } from "@/services/mock/mockDb";
import type { NewDelivery } from "@/types/domain";
import { computeKpis } from "@/utils/kpis";
import { useAppStore } from "./useAppStore";

/**
 * Fluxo completo do dia com dados fictícios (issue #11), dirigido pelo store
 * sobre o serviço mock real (localStorage stubado): cadastro de 15 entregas,
 * pendência de endereço não localizado com correção, geração da rota,
 * baixas do entregador e o resumo diário (computeKpis).
 */

const store = new Map<string, string>();

vi.stubGlobal("localStorage", {
  getItem: (key: string) => store.get(key) ?? null,
  setItem: (key: string, value: string) => void store.set(key, value),
  removeItem: (key: string) => void store.delete(key),
  clear: () => store.clear(),
});

const TOTAL_ENTREGAS = 15;
const TOTAL_CONCLUIDAS = 12;
const TOTAL_PENDENCIAS = 2;
const TOTAL_AGUARDANDO = TOTAL_ENTREGAS - TOTAL_CONCLUIDAS - TOTAL_PENDENCIAS;

const dbInicial: MockDb = {
  deliveries: [],
  route: {
    id: "rota-hoje",
    origin: {
      name: "Loja Fictícia (demo)",
      address: "Rua das Palmeiras, 100 - Centro",
      lat: -12.9714,
      lng: -38.5014,
    },
    routes: [
      {
        vehicleId: "v1",
        vehicleName: "Moto 01 (demo)",
        capacity: 20,
        load: 0,
        stopIds: [],
        distanceKm: 0,
        durationMin: 0,
        travelMin: 0,
        waitMin: 0,
        serviceMin: 0,
      },
    ],
    totalDistanceKm: 0,
    totalDurationMin: 0,
    status: "planned",
    isSimulation: false,
  },
};

function entregaInput(idx: number): NewDelivery {
  return {
    orderCode: `#${2000 + idx}`,
    customerName: `Cliente Fictício ${String(idx).padStart(2, "0")}`,
    phone: `(71) 98888-${String(2000 + idx).padStart(4, "0")}`,
    address: `Rua Fictícia ${idx}, ${100 + idx} - Salvador`,
    windowStart: "18:00",
    windowEnd: "20:00",
    priority: "normal",
    notes: "",
  };
}

describe("fluxo completo do dia — cadastro, rota, baixas e resumo (issue #11)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    store.clear();
    saveDb(dbInicial);
    useAppStore.setState({
      deliveries: [],
      route: null,
      initialized: false,
      loading: false,
      error: null,
      nowSimulated: "19:45",
    });
  });

  it("percorre cadastro -> correção de endereço -> rota -> baixas -> resumo", async () => {
    const s = () => useAppStore.getState();

    // 1. Cadastro: 15 entregas fictícias de uma vez (importação em lote).
    await s().refresh();
    await s().importDeliveries(
      Array.from({ length: TOTAL_ENTREGAS }, (_, i) => entregaInput(i + 1)),
    );

    expect(s().error).toBeNull();
    expect(s().deliveries).toHaveLength(TOTAL_ENTREGAS);
    expect(s().deliveries.every((d) => d.status === "waiting_departure")).toBe(true);
    // Geocodificação fictícia: toda entrega ganha coordenadas perto da loja.
    expect(s().deliveries.every((d) => d.lat !== 0 && d.lng !== 0)).toBe(true);

    // 2. Caso inválido: uma entrega é sinalizada como endereço não localizado.
    const [problematica] = s().deliveries;
    await s().reportIssue(
      problematica.id,
      "address_not_found",
      "Entregador não localizou o endereço",
      "18:30",
    );
    expect(s().deliveries[0].status).toBe("issue");
    expect(s().deliveries[0].issueReason).toBe("address_not_found");

    // Correção: editar o endereço devolve a entrega à fila de espera.
    await s().updateDelivery(problematica.id, {
      ...entregaInput(1),
      address: "Rua Corrigida, 50 - Salvador",
    });
    const corrigida = s().deliveries[0];
    expect(corrigida.status).toBe("waiting_departure");
    expect(corrigida.issueReason).toBeNull();
    expect(corrigida.address).toBe("Rua Corrigida, 50 - Salvador");

    // 3. Geração da rota: todas as 15 entram no plano do único veículo.
    await s().suggestSequence();
    const route = s().route;
    expect(s().error).toBeNull();
    expect(route).not.toBeNull();
    expect(route!.routes[0].stopIds).toHaveLength(TOTAL_ENTREGAS);
    expect(route!.routes[0].stopIds).toContain(corrigida.id);
    expect(route!.totalDistanceKm).toBeGreaterThan(0);
    expect(route!.totalDurationMin).toBeGreaterThan(0);

    // 4. Baixas do entregador: 12 concluídas e 2 pendências; 1 fica aguardando.
    const ids = route!.routes[0].stopIds;
    for (const id of ids.slice(0, TOTAL_CONCLUIDAS)) {
      await s().completeDelivery(id, "19:30");
    }
    await s().reportIssue(
      ids[TOTAL_CONCLUIDAS],
      "customer_absent",
      "Cliente ausente",
      "19:45",
    );
    await s().reportIssue(
      ids[TOTAL_CONCLUIDAS + 1],
      "operational",
      "Veículo quebrou",
      "19:50",
    );

    // 5. Resumo diário às 21:00: contagens e totais batem com o cenário.
    const kpis = computeKpis(s().deliveries, "21:00");
    expect(kpis.total).toBe(TOTAL_ENTREGAS);
    expect(kpis.completed).toBe(TOTAL_CONCLUIDAS);
    expect(kpis.issues).toBe(TOTAL_PENDENCIAS);
    expect(kpis.waiting).toBe(TOTAL_AGUARDANDO);
    expect(kpis.completionRate).toBe(
      Math.round((TOTAL_CONCLUIDAS / TOTAL_ENTREGAS) * 100),
    );
    // Janela 18:00-20:00 já passou: pendências e a aguardando contam como atrasadas.
    expect(kpis.late).toBe(TOTAL_PENDENCIAS + TOTAL_AGUARDANDO);

    // Pendências carregam o motivo que aparece no detalhe do resumo.
    const pendencias = s().deliveries.filter((d) => d.status === "issue");
    expect(new Set(pendencias.map((d) => d.issueReason))).toEqual(
      new Set(["customer_absent", "operational"]),
    );
    // O mock simula latência de rede (~250ms por chamada); o fluxo faz ~20 chamadas.
  }, 20000);
});
