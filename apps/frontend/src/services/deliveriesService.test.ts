import { afterEach, describe, expect, it, vi } from "vitest";
import type { DeliveryDTO } from "@/types/dto";
import { httpDeliveriesService } from "./deliveriesService";

const mockDeliveryDto: DeliveryDTO = {
  id: 1,
  order_code: "#1001",
  customer_name: "Ana Paula",
  phone: "71999990000",
  address: "Rua A, 10",
  location: { latitude: -13.37, longitude: -39.07 },
  geocoding_status: "ok",
  geocoding_message: null,
  time_window: { start: 1080, end: 1200 },
  has_explicit_time_window: true,
  demand: 1,
  priority: "normal",
  status: "issue",
  notes: "Portão fechado",
  issue_reason: "customer_absent",
  completed_at: null,
  history: [],
};

describe("httpDeliveriesService — contrato PATCH /deliveries/{id}", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("serializa os campos editáveis em snake_case ao atualizar entrega", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockDeliveryDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await httpDeliveriesService.update("del-1", {
      orderCode: "#1001",
      customerName: "Ana Paula",
      phone: "71999990000",
      address: "Rua A, 10",
      windowStart: "18:00",
      windowEnd: "20:00",
      priority: "high",
      notes: "Portão azul",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/deliveries/del-1");
    expect(init?.method).toBe("PATCH");

    const parsedBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(parsedBody).toEqual({
      order_code: "#1001",
      customer_name: "Ana Paula",
      phone: "71999990000",
      address: "Rua A, 10",
      demand: 1,
      time_window: { start: 1080, end: 1200 },
      priority: "high",
      notes: "Portão azul",
    });
    expect(parsedBody).not.toHaveProperty("customerName");
  });

  it("serializa issue_reason e updated_at em snake_case ao registrar pendência", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockDeliveryDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await httpDeliveriesService.reportIssue("del-1", "customer_absent", "Portão fechado", "19:40");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/deliveries/del-1");
    expect(init?.method).toBe("PATCH");

    const parsedBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(parsedBody).toEqual({
      status: "issue",
      issue_reason: "customer_absent",
      notes: "Portão fechado",
      updated_at: "19:40",
    });
    expect(parsedBody).not.toHaveProperty("issueReason");
  });

  it("serializa completed_at em snake_case ao concluir entrega", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ ...mockDeliveryDto, status: "completed", completed_at: "19:45" }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await httpDeliveriesService.complete("del-1", "19:45");

    const [, init] = fetchMock.mock.calls[0];
    const parsedBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(parsedBody).toEqual({
      status: "completed",
      completed_at: "19:45",
    });
    expect(parsedBody).not.toHaveProperty("completedAt");
  });
});