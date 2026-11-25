import { afterEach, describe, expect, it, vi } from "vitest";
import type { BackendEntregaResponseDTO, BackendGeocodeResponseDTO } from "@/types/dto";
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

const mockGeocode: BackendGeocodeResponseDTO = {
  results: [
    {
      latitude: -13.5,
      longitude: -39.1,
      display_name: "Rua B, 20",
      confidence: 1,
      address_components: {},
    },
  ],
  ambiguous: false,
};

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const baseInput = {
  orderCode: "#1001",
  customerName: "Ana Paula",
  phone: "71999990000",
  address: "Rua A, 10",
  windowStart: "09:00",
  windowEnd: "10:00",
  priority: "high" as const,
  notes: "Portão azul",
};

describe("httpDeliveriesService — contrato de escrita em /entregas/{id}", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("atualiza cadastro via PUT /entregas/{id} reutilizando coordenadas quando o endereço não muda", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(mockBackendEntrega))
      .mockResolvedValueOnce(jsonResponse({ ...mockBackendEntrega, janela_inicio: "09:00:00", janela_fim: "10:00:00" }));

    const updated = await httpDeliveriesService.update("1", baseInput);

    // GET /entregas/1 + PUT /entregas/1 — sem geocodificação, pois o endereço não mudou
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [getUrl] = fetchMock.mock.calls[0];
    const [putUrl, putInit] = fetchMock.mock.calls[1];
    expect(String(getUrl)).toContain("/entregas/1");
    expect(String(putUrl)).toContain("/entregas/1");
    expect(putInit?.method).toBe("PUT");

    const putBody = JSON.parse(String(putInit?.body)) as Record<string, unknown>;
    expect(putBody).toMatchObject({
      pedido_id: "#1001",
      endereco: "Rua A, 10",
      latitude: -13.37,
      longitude: -39.07,
      demanda: 1,
      janela_inicio: "09:00",
      janela_fim: "10:00",
    });
    expect(String(putBody.observacoes)).toContain('"c":"Ana Paula"');
    expect(String(putBody.observacoes)).toContain('"pr":"high"');
    expect(String(putBody.observacoes)).toContain("Portão azul");
    expect(updated.windowStart).toBe("09:00");
    expect(updated.hasExplicitTimeWindow).toBe(true);
  });

  it("re-geocodifica ao alterar o endereço e envia as novas coordenadas", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(mockBackendEntrega))
      .mockResolvedValueOnce(jsonResponse(mockGeocode))
      .mockResolvedValueOnce(
        jsonResponse({ ...mockBackendEntrega, endereco: "Rua B, 20", latitude: -13.5, longitude: -39.1 }),
      );

    await httpDeliveriesService.update("1", { ...baseInput, address: "Rua B, 20" });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(String(fetchMock.mock.calls[1][0])).toContain("/geocoding/forward");

    const [, putInit] = fetchMock.mock.calls[2];
    const putBody = JSON.parse(String(putInit?.body)) as Record<string, unknown>;
    expect(putBody.endereco).toBe("Rua B, 20");
    expect(putBody.latitude).toBe(-13.5);
    expect(putBody.longitude).toBe(-39.1);
  });

  it("envia janela null para voltar a herdar o expediente", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ ...mockBackendEntrega, janela_inicio: "09:00:00", janela_fim: "10:00:00" }))
      .mockResolvedValueOnce(jsonResponse(mockBackendEntrega));

    await httpDeliveriesService.update("1", { ...baseInput, windowStart: "", windowEnd: "" });

    const [, putInit] = fetchMock.mock.calls[1];
    const putBody = JSON.parse(String(putInit?.body)) as Record<string, unknown>;
    expect(putBody.janela_inicio).toBeNull();
    expect(putBody.janela_fim).toBeNull();
  });

  it("bloqueia edição de entrega vinculada a uma rota (rota_id)", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ ...mockBackendEntrega, rota_id: 7 }));

    await expect(httpDeliveriesService.update("1", baseInput)).rejects.toThrow(
      "já vinculada a uma rota",
    );
    // Somente o GET de validação — nenhum PUT disparado
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("bloqueia edição de entrega entregue mesmo sem vínculo de rota", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ ...mockBackendEntrega, status: "ENTREGUE" }));

    await expect(httpDeliveriesService.update("1", baseInput)).rejects.toThrow(
      "aguardando saída",
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("corrige pendência de endereço e devolve a entrega para PENDENTE", async () => {
    const falhaEndereco: BackendEntregaResponseDTO = {
      ...mockBackendEntrega,
      status: "FALHA",
      observacoes: '\n[JAS_META]:{"c":"Ana Paula","p":"71999990000","r":"address_not_found"}',
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(falhaEndereco))
      .mockResolvedValueOnce(jsonResponse(mockGeocode))
      .mockResolvedValueOnce(jsonResponse({ ...mockBackendEntrega, endereco: "Rua B, 20" }));

    const updated = await httpDeliveriesService.update("1", {
      ...baseInput,
      address: "Rua B, 20",
    });

    const [, putInit] = fetchMock.mock.calls[2];
    const putBody = JSON.parse(String(putInit?.body)) as Record<string, unknown>;
    expect(putBody.status).toBe("PENDENTE");
    expect(String(putBody.observacoes)).not.toContain('"r"');
    expect(updated.status).toBe("waiting_departure");
  });

  it("cria entrega via POST /entregas com geocodificação prévia", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(mockGeocode))
      .mockResolvedValueOnce(jsonResponse(mockBackendEntrega));

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
      demanda: 1,
      janela_inicio: "08:00",
      janela_fim: "18:00",
    });
    expect(created.customerName).toBe("Ana Paula");
  });

  it("atualiza status para FALHA via PUT /entregas/{id} preservando cliente e motivo", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(mockBackendEntrega))
      .mockResolvedValueOnce(
        jsonResponse({
          ...mockBackendEntrega,
          status: "FALHA",
          observacoes:
            'Portão fechado\n[JAS_META]:{"c":"Ana Paula","p":"71999990000","r":"customer_absent"}',
        }),
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
      .mockResolvedValueOnce(jsonResponse(mockBackendEntrega))
      .mockResolvedValueOnce(jsonResponse({ ...mockBackendEntrega, status: "ENTREGUE" }));

    const updated = await httpDeliveriesService.complete("1", "14:25");

    const [, putInit] = fetchMock.mock.calls[1];
    const putBody = JSON.parse(String(putInit?.body)) as Record<string, unknown>;
    expect(putBody.status).toBe("ENTREGUE");
    expect(updated.status).toBe("completed");
  });
});
