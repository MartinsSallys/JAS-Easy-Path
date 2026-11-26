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

/**
 * Excluir só é bloqueada para estados operacionais (issue #4): entrega
 * em andamento, concluída ou com pendência (FALHA no backend) faz parte
 * do histórico da rota e o backend rejeita com 409. Entrega vinculada a
 * rota PODE ser cancelada — o backend remove a parada do plano otimizado
 * na mesma chamada.
 */
export function isDeliveryDeletable(d: Delivery): boolean {
  return (
    d.status !== "in_progress" && d.status !== "completed" && d.status !== "issue"
  );
}
