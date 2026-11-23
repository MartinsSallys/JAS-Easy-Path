import type { DeliveryStatus, IssueReason, Priority } from "@/types/domain";

export const statusLabel: Record<DeliveryStatus, string> = {
  waiting_departure: "Aguardando saída",
  in_progress: "Em andamento",
  completed: "Concluída",
  issue: "Pendência",
};

export const issueLabel: Record<IssueReason, string> = {
  customer_absent: "Cliente ausente",
  address_not_found: "Endereço não localizado",
  customer_refused: "Cliente recusou o pedido",
  operational: "Problema operacional",
  other: "Outro",
};

export const priorityLabel: Record<Priority, string> = {
  low: "Baixa",
  normal: "Normal",
  high: "Alta",
};