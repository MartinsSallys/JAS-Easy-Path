import { afterEach, describe, expect, it, vi } from "vitest";
import { httpRoutesService } from "./routeService";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("httpRoutesService — reotimização segura", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("otimiza apenas entregas elegíveis e arquiva rota anterior via PUT sem chamar DELETE", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      // 1. GET /depositos
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 1,
            nome: "Depósito",
            endereco: "Centro",
            latitude: -13.37,
            longitude: -39.07,
            ativo: true,
            created_at: "2026-11-24T08:00:00",
          },
        ]),
      )
      // 2. GET /veiculos
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 1,
            placa: "ABC-1234",
            capacidade: 10,
            tipo: "MOTO",
            ativo: true,
            created_at: "2026-11-24T08:00:00",
          },
        ]),
      )
      // 3. GET /entregas (1 ENTREGUE, 1 FALHA, 1 PENDENTE)
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 10,
            pedido_id: "#1",
            endereco: "Rua 1",
            latitude: -13.37,
            longitude: -39.07,
            demanda: 1,
            status: "ENTREGUE",
            created_at: "2026-11-24T08:00:00",
            updated_at: "2026-11-24T09:00:00",
          },
          {
            id: 11,
            pedido_id: "#2",
            endereco: "Rua 2",
            latitude: -13.38,
            longitude: -39.08,
            demanda: 1,
            status: "FALHA",
            created_at: "2026-11-24T08:00:00",
            updated_at: "2026-11-24T09:10:00",
          },
          {
            id: 12,
            pedido_id: "#3",
            endereco: "Rua 3",
            latitude: -13.39,
            longitude: -39.09,
            demanda: 1,
            status: "PENDENTE",
            created_at: "2026-11-24T08:00:00",
            updated_at: "2026-11-24T08:00:00",
          },
        ]),
      )
      // 4. GET /rotas?data=...
      .mockResolvedValueOnce(
        jsonResponse([
          {
            id: 50,
            nome: "Rota anterior",
            data: "2026-11-24",
            deposito_id: 1,
            veiculo_id: 1,
            status: "OTIMIZADA",
            distancia_total_km: 5,
            tempo_total_min: 20,
            created_at: "2026-11-24T08:00:00",
            updated_at: "2026-11-24T08:05:00",
          },
        ]),
      )
      // 5. POST /rotas
      .mockResolvedValueOnce(
        jsonResponse(
          {
            id: 51,
            nome: "Rota nova",
            data: "2026-11-24",
            deposito_id: 1,
            veiculo_id: 1,
            status: "RASCUNHO",
            created_at: "2026-11-24T10:00:00",
            updated_at: "2026-11-24T10:00:00",
          },
          201,
        ),
      )
      // 6. POST /rotas/51/otimizar
      .mockResolvedValueOnce(
        jsonResponse({
          id: 51,
          nome: "Rota nova",
          data: "2026-11-24",
          deposito_id: 1,
          veiculo_id: 1,
          status: "OTIMIZADA",
          distancia_total_km: 3.2,
          tempo_total_min: 15,
          created_at: "2026-11-24T10:00:00",
          updated_at: "2026-11-24T10:01:00",
          paradas: [
            {
              id: 1,
              rota_id: 51,
              entrega_id: 12,
              deposito_id: null,
              ordem: 1,
              endereco: "Rua 3",
              latitude: -13.39,
              longitude: -39.09,
              demanda: 1,
              tempo_servico_min: 8,
              status: "PENDENTE",
            },
          ],
        }),
      )
      // 7. PUT /rotas/50 (arquiva rota anterior sem DELETE)
      .mockResolvedValueOnce(
        jsonResponse({
          id: 50,
          nome: "Rota anterior",
          data: "2026-11-24",
          deposito_id: 1,
          veiculo_id: 1,
          status: "CANCELADA",
          created_at: "2026-11-24T08:00:00",
          updated_at: "2026-11-24T10:01:00",
        }),
      );

    const plan = await httpRoutesService.optimize();

    expect(plan.id).toBe("51");
    expect(plan.routes[0].stopIds).toEqual(["12"]);

    // Confirma que POST /rotas recebeu SOMENTE entrega_ids: [12]
    const postRotaBody = JSON.parse(String(fetchMock.mock.calls[4][1]?.body)) as {
      entrega_ids: number[];
    };
    expect(postRotaBody.entrega_ids).toEqual([12]);

    // Confirma que a rota anterior (50) foi arquivada via PUT CANCELADA e nunca via DELETE
    const putRotaCall = fetchMock.mock.calls[6];
    expect(String(putRotaCall[0])).toContain("/rotas/50");
    expect(putRotaCall[1]?.method).toBe("PUT");
    expect(JSON.parse(String(putRotaCall[1]?.body))).toEqual({ status: "CANCELADA" });
  });
});