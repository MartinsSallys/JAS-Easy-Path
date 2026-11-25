import { afterEach, describe, expect, it, vi } from "vitest";
import type { BackendRotaWithParadasResponseDTO } from "@/types/dto";
import { HttpError } from "./http";
import { httpRoutesService } from "./routeService";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("httpRoutesService — criação, reotimização segura e bloqueio de transferência entre rotas", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("cria e otimiza a primeira rota do dia apenas com entregas elegíveis e sem vínculo (PENDENTE/ATRIBUIDA)", async () => {
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
            rota_id: null,
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
            rota_id: null,
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
      .mockResolvedValueOnce(jsonResponse([]))
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
      );

    const plan = await httpRoutesService.optimize();

    expect(plan.id).toBe("51");
    expect(plan.routes[0].stopIds).toEqual(["12"]);

    const postRotaBody = JSON.parse(String(fetchMock.mock.calls[4][1]?.body)) as {
      entrega_ids: number[];
    };
    expect(postRotaBody.entrega_ids).toEqual([12]);
  });

  it("bloqueia substituição de rota ativa de hoje quando há novas entregas sem vínculo e preserva a rota existente", async () => {
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

    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
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
            capacidade: 10,
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

      throw new Error(`Não deveria mutar estado no backend: ${method} ${url}`);
    });

    await expect(httpRoutesService.optimize()).rejects.toThrow(HttpError);

    const mutatingCalls = fetchMock.mock.calls.filter(
      ([, init]) => (init?.method ?? "GET") !== "GET",
    );
    expect(mutatingCalls).toHaveLength(0);

    const entrega10 = dbEntregas.find((e) => e.id === 10)!;
    expect(entrega10.rota_id).toBe(1);
    expect(entrega10.status).toBe("ATRIBUIDA");
    expect(entrega10.parada_ordem).toBe(1);
    expect(dbRotas).toHaveLength(1);
    expect(dbRotas[0].status).toBe("OTIMIZADA");
    expect(dbRotas[0].paradas).toHaveLength(1);
  });

  it("bloqueia criação quando não há rota hoje mas existe entrega vinculada a rota de outro dia", async () => {
    // Cenário: 1 entrega vinculada à rota otimizada de ontem (rota_id = 1) + 1 entrega nova hoje + nenhuma rota hoje
    const dbEntregas = [
      {
        id: 10,
        pedido_id: "#ONTEM-1",
        endereco: "Rua Ontem, 1",
        latitude: -13.37,
        longitude: -39.07,
        demanda: 1,
        status: "ATRIBUIDA",
        rota_id: 1 as number | null,
        parada_ordem: 1 as number | null,
        created_at: "2026-11-23T08:00:00",
        updated_at: "2026-11-23T08:05:00",
      },
      {
        id: 11,
        pedido_id: "#HOJE-1",
        endereco: "Rua Hoje, 2",
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

    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
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
            created_at: "2026-11-23T08:00:00",
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
            created_at: "2026-11-23T08:00:00",
          },
        ]);
      }

      if (url.includes("/entregas") && method === "GET") {
        return jsonResponse(dbEntregas);
      }

      // Nenhuma rota hoje
      if (url.includes("/rotas?") && method === "GET") {
        return jsonResponse([]);
      }

      throw new Error(`Não deveria mutar estado no backend: ${method} ${url}`);
    });

    await expect(httpRoutesService.optimize()).rejects.toThrow(HttpError);

    // Nenhuma requisição POST/PUT/DELETE deve ocorrer
    const mutatingCalls = fetchMock.mock.calls.filter(
      ([, init]) => (init?.method ?? "GET") !== "GET",
    );
    expect(mutatingCalls).toHaveLength(0);

    // Vínculo da entrega de ontem permanece 100% preservado
    const entregaOntem = dbEntregas.find((e) => e.id === 10)!;
    expect(entregaOntem.rota_id).toBe(1);
    expect(entregaOntem.status).toBe("ATRIBUIDA");
    expect(entregaOntem.parada_ordem).toBe(1);
  });
});