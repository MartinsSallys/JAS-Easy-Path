import { describe, expect, it } from "vitest";
import { toDeliveryInput, toNewDeliveryDTO, toRoutePlan } from "./mappers";
import type { Delivery } from "@/types/domain";
import type { RoutePlanDTO } from "@/types/dto";

const baseDelivery: Delivery = {
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
  notes: "Deixar na portaria",
  issueReason: null,
  completedAt: null,
  history: [],
};

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

  it("devolve janela vazia ao editar entrega que herdou o expediente", () => {
    const input = toDeliveryInput({
      ...baseDelivery,
      windowStart: "08:00",
      windowEnd: "22:00",
      hasExplicitTimeWindow: false,
    });

    expect(input.windowStart).toBe("");
    expect(input.windowEnd).toBe("");
  });

  it("remove a nota de geocodificação anexada pela API ao editar", () => {
    const input = toDeliveryInput({
      ...baseDelivery,
      notes: "Deixar na portaria | Geocodificação: endereço sem coordenadas.",
    });

    expect(input.notes).toBe("Deixar na portaria");
    expect(input.windowStart).toBe("18:00");
    expect(input.windowEnd).toBe("20:00");
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