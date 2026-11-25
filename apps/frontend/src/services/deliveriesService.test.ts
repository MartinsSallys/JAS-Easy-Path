import { afterEach, describe, expect, it, vi } from "vitest";
import type { BackendEntregaResponseDTO } from "@/types/dto";
import { httpDeliveriesService } from "./deliveriesService";

const mockBackendEntrega: BackendEntregaResponseDTO = {
  id: 1,
  pedido_id: "#1001",
  endereco: "Rua A, 10",
  latitude: -13.37,
  longitude: -39.07,
  demanda: 1,
  janela_inicio: "08:00:00",
  janela_fim: "18:00:00",
  observacoes: '\n[JAS_META]:{"c":"Ana Paula","p":"71999990000"}',
  status: "PENDENTE",
  created_at: "2026-11-23T08:00:00",
  updated_at: "2026-11-23T08:00:00",
  rota_id: null,
  parada_ordem: null,
};

describe("httpDeliveriesService — contrato de escrita em /deliveries/{id}", () => {
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
    expect(init?.method).toBe("PUT");

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

    const created = await httpDeliveriesService.create({
      orderCode: "#1001",
      customerName: "Ana Paula",
      phone: "71999990000",
      address: "Rua A, 10",
      windowStart: "",
      windowEnd: "",
      priority: "normal",
      notes: "",
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(String(fetchMock.mock.calls[0][0])).toContain("/geocoding/forward");
    expect(String(fetchMock.mock.calls[1][0])).toContain("/entregas");

    const createBody = JSON.parse(String(fetchMock.mock.calls[1][1]?.body)) as Record<
      string,
      unknown
    >;
    expect(createBody).toMatchObject({
      pedido_id: "#1001",
      endereco: "Rua A, 10",
      latitude: -13.37,
      longitude: -39.07,
      demanda: 1,
      janela_inicio: "08:00",
      janela_fim: "18:00",
    });
    expect(created.customerName).toBe("Ana Paula");
  });

  it("atualiza status para FALHA via PUT /entregas/{id} preservando cliente e motivo", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(mockBackendEntrega), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ...mockBackendEntrega,
            status: "FALHA",
            observacoes:
              'Portão fechado\n[JAS_META]:{"c":"Ana Paula","p":"71999990000","r":"customer_absent"}',
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );

    const updated = await httpDeliveriesService.reportIssue(
      "1",
      "customer_absent",
      "Portão fechado",
      "14:20",
    );

    const [putUrl, putInit] = fetchMock.mock.calls[1];
    expect(String(putUrl)).toContain("/entregas/1");
    expect(putInit?.method).toBe("PUT");

    const putBody = JSON.parse(String(putInit?.body)) as Record<string, unknown>;
    expect(putBody.status).toBe("FALHA");
    expect(String(putBody.observacoes)).toContain('"r":"customer_absent"');
    expect(String(putBody.observacoes)).toContain('"c":"Ana Paula"');
    expect(updated.status).toBe("issue");
    expect(updated.issueReason).toBe("customer_absent");
    expect(updated.customerName).toBe("Ana Paula");
  });

  it("atualiza status para ENTREGUE via PUT /entregas/{id}", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(mockBackendEntrega), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...mockBackendEntrega, status: "ENTREGUE" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    const updated = await httpDeliveriesService.complete("1", "14:25");

    const [, putInit] = fetchMock.mock.calls[1];
    const putBody = JSON.parse(String(putInit?.body)) as Record<string, unknown>;
    expect(putBody.status).toBe("ENTREGUE");
    expect(updated.status).toBe("completed");
  });
});