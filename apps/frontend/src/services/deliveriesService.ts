import type { Delivery, IssueReason, NewDelivery } from "@/types/domain";
import type { DeliveryDTO } from "@/types/dto";
import { USE_MOCK } from "./config";
import { http } from "./http";
import { toDelivery, toNewDeliveryDTO } from "./mappers";
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

const patch = (path: string, body: unknown) =>
  http<DeliveryDTO>(path, { method: "PATCH", body: JSON.stringify(body) });

// Edição do cadastro substitui o recurso inteiro: PUT (api.md seção 3.4).
// No backend real o equivalente é PUT /api/v1/entregas/{id}.
const put = (path: string, body: unknown) =>
  http<DeliveryDTO>(path, { method: "PUT", body: JSON.stringify(body) });

export const httpDeliveriesService: DeliveriesService = {
  async list() {
    return (await http<DeliveryDTO[]>("/deliveries")).map(toDelivery);
  },
  async create(input) {
    return toDelivery(
      await http<DeliveryDTO>("/deliveries", {
        method: "POST",
        body: JSON.stringify(toNewDeliveryDTO(input)),
      }),
    );
  },
  async createMany(inputs) {
    const dtos = await http<DeliveryDTO[]>("/deliveries/bulk", {
      method: "POST",
      body: JSON.stringify(inputs.map(toNewDeliveryDTO)),
    });
    return dtos.map(toDelivery);
  },
  async update(id, input) {
    return toDelivery(
      await put(`/deliveries/${id}`, toNewDeliveryDTO(input)),
    );
  },
  async remove(id) {
    await http<void>(`/deliveries/${id}`, { method: "DELETE" });
  },
  async complete(id, at) {
    return toDelivery(
      await patch(`/deliveries/${id}`, {
        status: "completed",
        completed_at: at,
      }),
    );
  },
  async reportIssue(id, reason, note, at) {
    return toDelivery(
      await patch(`/deliveries/${id}`, {
        status: "issue",
        issue_reason: reason,
        notes: note,
        updated_at: at,
      }),
    );
  },
  async resetDemo() {
    // A API real não tem "restaurar demonstração".
  },
};

export const deliveriesService: DeliveriesService = USE_MOCK
  ? mockDeliveriesService
  : httpDeliveriesService;