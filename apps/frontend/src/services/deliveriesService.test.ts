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
  observacoes: "Cliente: Ana Paula | Telefone: 71999990000",
  status: "PENDENTE",
  created_at: "2026-11-23T08:00:00",
  updated_at: "2026-11-23T08:00:00",
  rota_id: null,
  parada_ordem: null,
};

describe("httpDeliveriesService — contrato real FastAPI (/api/v1/entregas)", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("geocodifica endereço e envia POST /entregas em snake_case com demanda 1 e janela 08:00-18:00", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            results: [
              {
                latitude: -13.37,
                longitude: -39.07,
                display_name: "Rua A, 10 - Valença",
                confidence: 0.95,
                address_components: {},
              },
            ],
            ambiguous: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(mockBackendEntrega), {
          status: 201,
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
              "Cliente: Ana Paula | Telefone: 71999990000 | Motivo: customer_absent | Portão fechado",
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
    expect(String(putBody.observacoes)).toContain("Motivo: customer_absent");
    expect(updated.status).toBe("issue");
    expect(updated.issueReason).toBe("customer_absent");
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