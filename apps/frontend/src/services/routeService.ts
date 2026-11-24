import type { RoutePlan } from "@/types/domain";
import type {
  BackendDepositoResponseDTO,
  BackendEntregaResponseDTO,
  BackendRotaResponseDTO,
  BackendRotaWithParadasResponseDTO,
  BackendVeiculoResponseDTO,
} from "@/types/dto";
import { USE_MOCK } from "./config";
import { HttpError, http } from "./http";
import { toRoutePlanFromBackend } from "./mappers";
import { mockRoutesService } from "./mock/mockRoutes";

export interface RoutesService {
  get(): Promise<RoutePlan | null>;
  optimize(): Promise<RoutePlan>;
  share(): Promise<string>;
}

const OPTIMIZE_PAYLOAD = {
  minimize: "distance",
  time_limit_seconds: 5,
  allow_unassigned: false,
} as const;

function todayIsoDate(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

async function resolveDefaultDeposito(): Promise<BackendDepositoResponseDTO> {
  const depositos = await http<BackendDepositoResponseDTO[]>("/depositos?ativo=true");
  if (depositos.length === 0) {
    throw new HttpError(
      422,
      "Nenhum depósito ativo cadastrado no sistema. Cadastre um ponto de saída antes de otimizar a rota.",
    );
  }
  return depositos[0];
}

async function resolveDefaultVeiculo(): Promise<BackendVeiculoResponseDTO> {
  const veiculos = await http<BackendVeiculoResponseDTO[]>("/veiculos?ativo=true");
  if (veiculos.length === 0) {
    throw new HttpError(
      422,
      "Nenhum veículo ativo cadastrado no sistema. Cadastre um veículo antes de otimizar a rota.",
    );
  }
  return veiculos[0];
}

export const httpRoutesService: RoutesService = {
  async get() {
    const today = todayIsoDate();
    const rotas = await http<BackendRotaResponseDTO[]>(`/rotas?data=${today}`);
    const activeRota = rotas.find((r) => r.status !== "CANCELADA");
    if (!activeRota) {
      return null;
    }

    const [rotaDetalhe, deposito, veiculos] = await Promise.all([
      http<BackendRotaWithParadasResponseDTO>(`/rotas/${activeRota.id}`),
      http<BackendDepositoResponseDTO>(`/depositos/${activeRota.deposito_id}`),
      http<BackendVeiculoResponseDTO[]>("/veiculos?ativo=true"),
    ]);

    const veiculo =
      veiculos.find((v) => v.id === rotaDetalhe.veiculo_id) ?? veiculos[0] ?? null;

    return toRoutePlanFromBackend(rotaDetalhe, deposito, veiculo);
  },

  async optimize() {
    const today = todayIsoDate();
    const [deposito, veiculo, todasEntregas, rotasHoje] = await Promise.all([
      resolveDefaultDeposito(),
      resolveDefaultVeiculo(),
      http<BackendEntregaResponseDTO[]>("/entregas?limit=500"),
      http<BackendRotaResponseDTO[]>(`/rotas?data=${today}`),
    ]);

    // Apenas entregas elegíveis (nunca ENTREGUE, FALHA ou CANCELADA) entram na otimização
    const elegiveis = todasEntregas.filter(
      (e) => e.status === "PENDENTE" || e.status === "ATRIBUIDA",
    );
    if (elegiveis.length === 0) {
      throw new HttpError(
        422,
        "Não há entregas pendentes elegíveis para otimizar. Entregas já concluídas, com falha ou canceladas não entram em nova rota.",
      );
    }

    const rotaAtiva = rotasHoje.find((r) => r.status !== "CANCELADA") ?? null;

    if (rotaAtiva) {
      const novasSemVinculo = elegiveis.filter((e) => e.rota_id !== rotaAtiva.id);
      if (novasSemVinculo.length > 0) {
        throw new HttpError(
          422,
          `Já existe uma rota ativa hoje (${rotaAtiva.nome}) com entregas vinculadas. Para evitar perda de vínculos enquanto o backend não suporta substituição transacional, não é possível incorporar ${novasSemVinculo.length} nova(s) entrega(s) à rota existente.`,
        );
      }
      
      const reotimizada = await http<BackendRotaWithParadasResponseDTO>(
        `/rotas/${rotaAtiva.id}/otimizar`,
        {
          method: "POST",
          body: JSON.stringify(OPTIMIZE_PAYLOAD),
        },
      );
      return toRoutePlanFromBackend(reotimizada, deposito, veiculo);
    }

    const novaRota = await http<BackendRotaResponseDTO>("/rotas", {
      method: "POST",
      body: JSON.stringify({
        nome: `Rota ${today}`,
        data: today,
        deposito_id: deposito.id,
        veiculo_id: veiculo.id,
        entrega_ids: elegiveis.map((e) => e.id),
      }),
    });

    let otimizada: BackendRotaWithParadasResponseDTO;
    try {
      otimizada = await http<BackendRotaWithParadasResponseDTO>(
        `/rotas/${novaRota.id}/otimizar`,
        {
          method: "POST",
          body: JSON.stringify(OPTIMIZE_PAYLOAD),
        },
      );
    } catch (err) {
      await http<void>(`/rotas/${novaRota.id}`, { method: "DELETE" }).catch(() => {});
      throw err;
    }

    return toRoutePlanFromBackend(otimizada, deposito, veiculo);
  },

  async share() {
    const plan = await httpRoutesService.get();
    if (!plan) {
      throw new HttpError(404, "Nenhuma rota ativa encontrada para compartilhar.");
    }
    const baseUrl = typeof window !== "undefined" ? window.location.origin : "http://localhost:5173";
    return `${baseUrl}/entregador?rota=${plan.id}`;
  },
};

export const routesService: RoutesService = USE_MOCK ? mockRoutesService : httpRoutesService;