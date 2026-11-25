import type { Delivery, IssueReason, NewDelivery } from "@/types/domain";
import type {
  BackendEntregaResponseDTO,
  BackendEntregaUpdateDTO,
  BackendGeocodeResponseDTO,
} from "@/types/dto";
import { USE_MOCK } from "./config";
import { HttpError, http } from "./http";
import {
  formatBackendObservacoes,
  parseBackendObservacoes,
  toBackendEntregaCreateDTO,
  toDeliveryFromBackend,
} from "./mappers";
import { isDeliveryEditable } from "@/utils/delivery";
import { mockDeliveriesService } from "./mock/mockDeliveries";

/** O "contrato" que o resto do app usa. Mock e API real cumprem o MESMO contrato. */
export interface DeliveriesService {
  list(): Promise<Delivery[]>;
  create(input: NewDelivery): Promise<Delivery>;
  createMany(inputs: NewDelivery[]): Promise<Delivery[]>;
  update(id: string, input: NewDelivery): Promise<Delivery>;
  remove(id: string): Promise<void>;
  complete(id: string, at: string): Promise<Delivery>;
  reportIssue(id: string, reason: IssueReason, note: string, at: string): Promise<Delivery>;
  resetDemo(): Promise<void>;
}

async function geocodeAddress(address: string): Promise<{ latitude: number; longitude: number }> {
  const geo = await http<BackendGeocodeResponseDTO>("/geocoding/forward", {
    method: "POST",
    body: JSON.stringify({ endereco: address, country_code: "br" }),
  });
  const best = geo.results[0];
  if (!best) {
    throw new HttpError(
      422,
      `Não foi possível localizar coordenadas para o endereço "${address}". Verifique rua, número e cidade.`,
    );
  }
  return { latitude: best.latitude, longitude: best.longitude };
}

// Edição do cadastro substitui o recurso inteiro: PUT (api.md seção 3.4).
// No backend real o equivalente é PUT /api/v1/entregas/{id}.

export const httpDeliveriesService: DeliveriesService = {
  async list() {
    const dtos = await http<BackendEntregaResponseDTO[]>("/entregas?limit=500");
    // Entregas CANCELADA não entram nas listas operacionais nem nas rotas do dia
    return dtos.filter((d) => d.status !== "CANCELADA").map(toDeliveryFromBackend);
  },

async create(input) {
    const coords = await geocodeAddress(input.address);
    const payload = toBackendEntregaCreateDTO(input, coords, 1);
    try {
      const created = await http<BackendEntregaResponseDTO>("/entregas", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      return toDeliveryFromBackend(created);
    } catch (err) {
      if (err instanceof HttpError && err.status === 500) {
        throw new HttpError(
          422,
          `Não foi possível salvar o pedido "${payload.pedido_id}". Verifique se já existe uma entrega cadastrada com este mesmo código.`,
        );
      }
      throw err;
    }
  },

  async createMany(inputs) {
    if (inputs.length === 0) return [];
    const geoList = await http<BackendGeocodeResponseDTO[]>("/geocoding/batch", {
      method: "POST",
      body: JSON.stringify({ enderecos: inputs.map((item) => item.address) }),
    });

    const payloads = inputs.map((input, idx) => {
      const best = geoList[idx]?.results[0];
      if (!best) {
        throw new HttpError(
          422,
          `Endereço não encontrado na linha ${idx + 1}: "${input.address}".`,
        );
      }
      return toBackendEntregaCreateDTO(
        input,
        { latitude: best.latitude, longitude: best.longitude },
        idx + 1,
      );
    });

    const createdList = await http<BackendEntregaResponseDTO[]>("/entregas/batch", {
      method: "POST",
      body: JSON.stringify({ entregas: payloads }),
    });
    return createdList.map(toDeliveryFromBackend);
  },
  async update(id, input) {
    const current = await http<BackendEntregaResponseDTO>(`/entregas/${id}`);
    const existing = toDeliveryFromBackend(current);
    if (!isDeliveryEditable(existing)) {
      throw new HttpError(
        409,
        current.rota_id !== null
          ? "Entrega já vinculada a uma rota — alterar o cadastro não recalcula a sequência otimizada."
          : "Só é possível editar entregas aguardando saída.",
      );
    }

    // Re-geocodifica só quando o endereço mudou, para não salvar endereço novo
    // com coordenadas antigas.
    const coords =
      input.address.trim() === current.endereco.trim()
        ? { latitude: current.latitude, longitude: current.longitude }
        : await geocodeAddress(input.address);

    const startRaw = input.windowStart.trim();
    const endRaw = input.windowEnd.trim();
    if ((startRaw === "") !== (endRaw === "")) {
      throw new Error("Informe o início e o fim da janela, ou deixe os dois em branco.");
    }

    // Corrigir a pendência "endereço não localizado" devolve a entrega à fila.
    const fixingAddressIssue =
      existing.status === "issue" && existing.issueReason === "address_not_found";

    const body: BackendEntregaUpdateDTO = {
      pedido_id: input.orderCode.trim() || current.pedido_id,
      endereco: input.address.trim(),
      latitude: coords.latitude,
      longitude: coords.longitude,
      demanda: current.demanda,
      // Janela vazia volta a herdar o expediente (api.md 3.4).
      janela_inicio: startRaw === "" ? null : startRaw,
      janela_fim: endRaw === "" ? null : endRaw,
      observacoes: formatBackendObservacoes({
        customerName: input.customerName,
        phone: input.phone,
        priority: input.priority,
        notes: input.notes,
      }),
      status: fixingAddressIssue ? "PENDENTE" : undefined,
    };

    const updated = await http<BackendEntregaResponseDTO>(`/entregas/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
    return toDeliveryFromBackend(updated);
  },
  async remove(id) {
    await http<void>(`/entregas/${id}`, { method: "DELETE" });
  },

  async complete(id, _at) {
    const current = await http<BackendEntregaResponseDTO>(`/entregas/${id}`);
    const parsed = parseBackendObservacoes(current.observacoes, `Pedido ${current.pedido_id}`);
    const body: BackendEntregaUpdateDTO = {
      status: "ENTREGUE",
      observacoes: formatBackendObservacoes({
        customerName: parsed.customerName,
        phone: parsed.phone,
        priority: parsed.priority,
        notes: parsed.notes,
      }),
    };
    const updated = await http<BackendEntregaResponseDTO>(`/entregas/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
    return toDeliveryFromBackend(updated);
  },

  async reportIssue(id, reason, note, _at) {
    const current = await http<BackendEntregaResponseDTO>(`/entregas/${id}`);
    const parsed = parseBackendObservacoes(current.observacoes, `Pedido ${current.pedido_id}`);
    const mergedNotes = [parsed.notes, note.trim()].filter(Boolean).join(" — ");
    const body: BackendEntregaUpdateDTO = {
      status: "FALHA",
      observacoes: formatBackendObservacoes({
        customerName: parsed.customerName,
        phone: parsed.phone,
        priority: parsed.priority,
        issueReason: reason,
        notes: mergedNotes,
      }),
    };
    const updated = await http<BackendEntregaResponseDTO>(`/entregas/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
    return toDeliveryFromBackend(updated);
  },

  async resetDemo() {
  },
};

export const deliveriesService: DeliveriesService = USE_MOCK
  ? mockDeliveriesService
  : httpDeliveriesService;