import type { Delivery } from "@/types/domain";

/**
 * Edição do cadastro só é permitida antes da entrega entrar na rota
 * (issue #4: corrigir os dados antes de gerar a rota). Depois de otimizada,
 * trocar o endereço não recalcula a sequência que o entregador segue —
 * por isso entregas com vínculo de rota (`routeId`) ficam bloqueadas mesmo
 * quando o status ainda é "aguardando" (o backend mapeia ATRIBUIDA para cá).
 * A exceção é a pendência "endereço não localizado": a entrega não tem
 * posição válida na rota e corrigir o endereço é justamente a solução.
 */
export function isDeliveryEditable(d: Delivery): boolean {
  if (d.routeId) return false;
  return (
    d.status === "waiting_departure" ||
    (d.status === "issue" && d.issueReason === "address_not_found")
  );
}
