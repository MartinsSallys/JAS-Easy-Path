import { afterEach, describe, expect, it, vi } from "vitest";
import type { BackendRotaWithParadasResponseDTO } from "@/types/dto";
import { HttpError } from "./http";
import { httpRoutesService } from "./routeService";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("httpRoutesService — reotimização e rollback de estado", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("otimiza apenas entregas elegíveis e arquiva rota anterior via PUT sem chamar DELETE", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
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
            rota_id: 50,
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
            rota_id: 50,
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
            rota_id: null,
            created_at: "2026-11-24T08:00:00",
            updated_at: "2026-11-24T08:00:00",
          },
        ]),
      )
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

    const postRotaBody = JSON.parse(String(fetchMock.mock.calls[4][1]?.body)) as {
      entrega_ids: number[];
    };
    expect(postRotaBody.entrega_ids).toEqual([12]);

    const putRotaCall = fetchMock.mock.calls[6];
    expect(String(putRotaCall[0])).toContain("/rotas/50");
    expect(putRotaCall[1]?.method).toBe("PUT");
    expect(JSON.parse(String(putRotaCall[1]?.body))).toEqual({ status: "CANCELADA" });
  });

  it("preserva vínculos, status ATRIBUIDA e paradas da rota anterior quando a nova otimização falha com 422", async () => {
    const dbEntregas = [
      {
        id: 10,
        pedido_id: "#1",
        endereco: "Rua 1",
        latitude: -13.37,
        longitude: -39.07,
        demanda: 1,
        status: "ATRIBUIDA",
        rota_id: 1 as number | null,
        parada_ordem: 1 as number | null,
        created_at: "2026-11-24T08:00:00",
        updated_at: "2026-11-24T08:05:00",
      },
      {
        id: 11,
        pedido_id: "#2",
        endereco: "Rua 2",
        latitude: -13.38,
        longitude: -39.08,
        demanda: 1,
        status: "PENDENTE",
        rota_id: null as number | null,
        parada_ordem: null as number | null,
        created_at: "2026-11-24T09:00:00",
        updated_at: "2026-11-24T09:00:00",
      },
    ];

    const dbRotas: BackendRotaWithParadasResponseDTO[] = [
      {
        id: 1,
        nome: "Rota 1",
        data: "2026-11-24",
        deposito_id: 1,
        veiculo_id: 1,
        status: "OTIMIZADA",
        distancia_total_km: 4.5,
        tempo_total_min: 18,
        created_at: "2026-11-24T08:00:00",
        updated_at: "2026-11-24T08:05:00",
        otimizada_em: "2026-11-24T08:05:00",
        paradas: [
          {
            id: 100,
            rota_id: 1,
            entrega_id: 10,
            deposito_id: null,
            ordem: 1,
            endereco: "Rua 1",
            latitude: -13.37,
            longitude: -39.07,
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
    ];

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.includes("/depositos")) {
        return jsonResponse([
          {
            id: 1,
            nome: "Depósito",
            endereco: "Centro",
            latitude: -13.37,
            longitude: -39.07,
            ativo: true,
            created_at: "2026-11-24T08:00:00",
          },
        ]);
      }

      if (url.includes("/veiculos")) {
        return jsonResponse([
          {
            id: 1,
            placa: "ABC-1234",
            capacidade: 1,
            tipo: "MOTO",
            ativo: true,
            created_at: "2026-11-24T08:00:00",
          },
        ]);
      }

      if (url.includes("/entregas") && method === "GET") {
        return jsonResponse(dbEntregas);
      }

      if (url.includes("/rotas?") && method === "GET") {
        return jsonResponse(dbRotas);
      }

      if (url.endsWith("/rotas") && method === "POST") {
        const body = JSON.parse(String(init?.body)) as { entrega_ids: number[] };
        const nova: BackendRotaWithParadasResponseDTO = {
          id: 2,
          nome: "Rota 2",
          data: "2026-11-24",
          deposito_id: 1,
          veiculo_id: 1,
          status: "RASCUNHO",
          distancia_total_km: null,
          tempo_total_min: null,
          created_at: "2026-11-24T09:05:00",
          updated_at: "2026-11-24T09:05:00",
          otimizada_em: null,
          paradas: [],
        };
        dbRotas.push(nova);
        for (const eid of body.entrega_ids) {
          const ent = dbEntregas.find((e) => e.id === eid);
          if (ent) {
            ent.rota_id = 2;
            ent.status = "ATRIBUIDA";
          }
        }
        return jsonResponse(nova, 201);
      }

      if (url.endsWith("/rotas/2/otimizar") && method === "POST") {
        return jsonResponse(
          { detail: "Não foi possível encontrar solução viável com as restrições atuais" },
          422,
        );
      }

      if (url.endsWith("/rotas/2") && method === "DELETE") {
        const idx = dbRotas.findIndex((r) => r.id === 2);
        if (idx !== -1) dbRotas.splice(idx, 1);
        for (const ent of dbEntregas) {
          if (ent.rota_id === 2) {
            ent.rota_id = null;
            ent.parada_ordem = null;
            ent.status = "PENDENTE";
          }
        }
        return new Response(null, { status: 204 });
      }

      if (url.endsWith("/rotas/1/otimizar") && method === "POST") {
        const rota1 = dbRotas.find((r) => r.id === 1)!;
        const ent10 = dbEntregas.find((e) => e.id === 10)!;
        ent10.rota_id = 1;
        ent10.parada_ordem = 1;
        ent10.status = "ATRIBUIDA";
        rota1.status = "OTIMIZADA";
        return jsonResponse(rota1);
      }

      throw new Error(`Chamada inesperada: ${method} ${url}`);
    });

    await expect(httpRoutesService.optimize()).rejects.toThrow(HttpError);

    const entrega10 = dbEntregas.find((e) => e.id === 10)!;
    expect(entrega10.rota_id).toBe(1);
    expect(entrega10.status).toBe("ATRIBUIDA");
    expect(entrega10.parada_ordem).toBe(1);

    expect(dbRotas).toHaveLength(1);
    expect(dbRotas[0].id).toBe(1);
    expect(dbRotas[0].status).toBe("OTIMIZADA");
    expect(dbRotas[0].paradas).toHaveLength(1);
  });
});