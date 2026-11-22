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
  remove(id: string): Promise<void>;
  complete(id: string, at: string): Promise<Delivery>;
  reportIssue(id: string, reason: IssueReason, note: string, at: string): Promise<Delivery>;
  resetDemo(): Promise<void>;
}

const patch = (path: string, body: unknown) =>
  http<DeliveryDTO>(path, { method: "PATCH", body: JSON.stringify(body) });

const httpDeliveriesService: DeliveriesService = {
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
  async remove(id) {
    await http<void>(`/deliveries/${id}`, { method: "DELETE" });
  },
  async complete(id, at) {
    return toDelivery(
      await patch(`/deliveries/${id}`, {
        status: "completed",
        completedAt: at,
      }),
    );
  },
  async reportIssue(id, reason, note, at) {
    return toDelivery(
      await patch(`/deliveries/${id}`, {
        status: "issue",
        issueReason: reason,
        notes: note,
        updatedAt: at,
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