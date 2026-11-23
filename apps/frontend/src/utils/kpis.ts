import type { Delivery } from "@/types/domain";

/**
 * Indica se a entrega está atrasada (prazo máximo ultrapassado e ainda não concluída).
 * Calculada em tempo real — nunca persistida no banco — para evitar dados obsoletos.
 * A comparação de string funciona porque o formato "HH:mm" tem sempre 5 caracteres.
 */
export function isLate(d: Delivery, now: string): boolean {
  return d.status !== "completed" && d.windowEnd < now;
}

export function computeKpis(deliveries: Delivery[], now: string) {
  const total = deliveries.length;
  const completed = deliveries.filter((d) => d.status === "completed").length;
  return {
    total,
    completed,
    issues: deliveries.filter((d) => d.status === "issue").length,
    inProgress: deliveries.filter((d) => d.status === "in_progress").length,
    waiting: deliveries.filter((d) => d.status === "waiting_departure").length,
    late: deliveries.filter((d) => isLate(d, now)).length,
    completionRate: total ? Math.round((completed / total) * 100) : 0,
  };
}