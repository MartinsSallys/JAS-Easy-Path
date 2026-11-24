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
import { mockDeliveriesService } from "./mock/mockDeliveries";

/** O "contrato" que o resto do app usa. Mock e API real cumprem o MESMO contrato. */
export interface DeliveriesService {
  list(): Promise<Delivery[]>;
  create(input: NewDelivery): Promise<Delivery>;
  createMany(inputs: NewDelivery[]): Promise<Delivery[]>;
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

export const httpDeliveriesService: DeliveriesService = {
  async list() {
    const dtos = await http<BackendEntregaResponseDTO[]>("/entregas?limit=500");
    // Entregas CANCELADA não entram nas listas operacionais nem nas rotas do dia
    return dtos.filter((d) => d.status !== "CANCELADA").map(toDeliveryFromBackend);
  },

  async create(input) {
    const coords = await geocodeAddress(input.address);
    const payload = toBackendEntregaCreateDTO(input, coords, 1);
    const created = await http<BackendEntregaResponseDTO>("/entregas", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return toDeliveryFromBackend(created);
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