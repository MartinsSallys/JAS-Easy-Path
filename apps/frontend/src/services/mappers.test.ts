import { describe, expect, it } from "vitest";
import {
  DEFAULT_WINDOW_END,
  DEFAULT_WINDOW_START,
  toBackendEntregaCreateDTO,
  toDeliveryFromBackend,
  toNewDeliveryDTO,
  toRoutePlan,
  toRoutePlanFromBackend,
} from "./mappers";
import type { RoutePlanDTO } from "@/types/dto";

describe("mappers", () => {
  it("mapeia janela vazia para time_window: null e demand: 1 no DTO padrão", () => {
    const dto = toNewDeliveryDTO({
      orderCode: "#201",
      customerName: "Mariana",
      phone: "",
      address: "Rua A, 10",
      windowStart: "",
      windowEnd: "",
      priority: "normal",
      notes: "",
    });

    expect(dto.demand).toBe(1);
    expect(dto.time_window).toBeNull();
  });

  it("aplica expediente padrão 08:00-18:00 e demanda 1 ao criar entrega para o backend FastAPI", () => {
    const payload = toBackendEntregaCreateDTO(
      {
        orderCode: "#205",
        customerName: "Carlos Lima",
        phone: "(71) 98888-0000",
        address: "Rua da Praia, 50",
        windowStart: "",
        windowEnd: "",
        priority: "high",
        notes: "Portão verde",
      },
      { latitude: -13.371, longitude: -39.072 },
    );

    expect(payload.demanda).toBe(1);
    expect(payload.janela_inicio).toBe(DEFAULT_WINDOW_START);
    expect(payload.janela_fim).toBe(DEFAULT_WINDOW_END);
    expect(payload.observacoes).toContain("Cliente: Carlos Lima");
    expect(payload.observacoes).toContain("Prioridade: high");

    const mappedBack = toDeliveryFromBackend({
      id: 7,
      pedido_id: payload.pedido_id,
      endereco: payload.endereco,
      latitude: payload.latitude,
      longitude: payload.longitude,
      demanda: payload.demanda,
      janela_inicio: payload.janela_inicio,
      janela_fim: payload.janela_fim,
      observacoes: payload.observacoes,
      status: "PENDENTE",
      created_at: "2026-11-23T09:00:00",
      updated_at: "2026-11-23T09:00:00",
      rota_id: null,
      parada_ordem: null,
    });

    expect(mappedBack.customerName).toBe("Carlos Lima");
    expect(mappedBack.priority).toBe("high");
    expect(mappedBack.notes).toBe("Portão verde");
    expect(mappedBack.windowStart).toBe("08:00");
    expect(mappedBack.windowEnd).toBe("18:00");
  });

  it("filtra paradas de depósito (entrega_id null) ao mapear rota do backend FastAPI", () => {
    const plan = toRoutePlanFromBackend(
      {
        id: 3,
        nome: "Rota 2026-11-23",
        data: "2026-11-23",
        deposito_id: 1,
        veiculo_id: 2,
        status: "OTIMIZADA",
        distancia_total_km: 6.4,
        tempo_total_min: 28,
        created_at: "2026-11-23T08:00:00",
        updated_at: "2026-11-23T08:05:00",
        otimizada_em: "2026-11-23T08:05:00",
        paradas: [
          {
            id: 1,
            rota_id: 3,
            entrega_id: null,
            deposito_id: 1,
            ordem: 0,
            endereco: "Depósito Central",
            latitude: -13.37,
            longitude: -39.07,
            demanda: 0,
            janela_inicio: null,
            janela_fim: null,
            tempo_servico_min: 0,
            chegada_prevista: null,
            saida_prevista: "08:00:00",
            observacoes: null,
            status: "PENDENTE",
          },
          {
            id: 2,
            rota_id: 3,
            entrega_id: 15,
            deposito_id: null,
            ordem: 1,
            endereco: "Rua B, 20",
            latitude: -13.38,
            longitude: -39.08,
            demanda: 1,
            janela_inicio: "08:00:00",
            janela_fim: "18:00:00",
            tempo_servico_min: 8,
            chegada_prevista: "08:10:00",
            saida_prevista: "08:18:00",
            observacoes: null,
            status: "PENDENTE",
          },
        ],
      },
      {
        id: 1,
        nome: "Depósito Central",
        endereco: "Praça da Matriz, 1",
        latitude: -13.37,
        longitude: -39.07,
        ativo: true,
        created_at: "2026-11-20T08:00:00",
      },
      {
        id: 2,
        placa: "ABC-1234",
        capacidade: 10,
        tipo: "MOTO",
        ativo: true,
        created_at: "2026-11-20T08:00:00",
      },
    );

    expect(plan.routes).toHaveLength(1);
    expect(plan.routes[0].stopIds).toEqual(["15"]);
    expect(plan.routes[0].vehicleName).toBe("MOTO (ABC-1234)");
    expect(plan.origin.name).toBe("Depósito Central");
  });

  it("mapeia plano com múltiplos veículos corretamente", () => {
    const dto: RoutePlanDTO = {
      id: 1,
      status: "planned",
      origin: { name: "Loja", address: "Centro", location: { latitude: -13.37, longitude: -39.07 } },
      matrix_source: "road_network",
      routes: [
        {
          vehicle: { id: 1, name: "Moto 1", capacity: 10 },
          stops: [{ delivery_id: 10, arrival_minute_of_day: 1140, departure_minute_of_day: 1148 }],
          load: 1,
          distance_m: 3450,
          travel_min: 10,
          wait_min: 0,
          service_min: 8,
          total_min: 18,
        },
        {
          vehicle: { id: 2, name: "Carro 1", capacity: 20 },
          stops: [{ delivery_id: 11, arrival_minute_of_day: 1150, departure_minute_of_day: 1158 }],
          load: 1,
          distance_m: 5000,
          travel_min: 15,
          wait_min: 0,
          service_min: 8,
          total_min: 23,
        },
      ],
    };

    const plan = toRoutePlan(dto);
    expect(plan.routes).toHaveLength(2);
    expect(plan.routes[0].vehicleName).toBe("Moto 1");
    expect(plan.routes[0].distanceKm).toBe(3.5);
    expect(plan.routes[1].vehicleName).toBe("Carro 1");
    expect(plan.totalDistanceKm).toBe(8.5);
    expect(plan.totalDurationMin).toBe(41);
  });
});