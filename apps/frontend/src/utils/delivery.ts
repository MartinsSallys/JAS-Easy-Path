import type { Delivery } from "@/types/domain";

/**
 * Edição do cadastro só é permitida antes da entrega entrar na rota
 * (issue #4: corrigir os dados antes de gerar a rota). Depois de otimizada,
 * trocar o endereço não recalcula a sequência que o entregador segue.
 * A exceção é a pendência "endereço não localizado": a entrega não tem
 * posição válida na rota e corrigir o endereço é justamente a solução.
 */
export function isDeliveryEditable(d: Delivery): boolean {
  return (
    d.status === "waiting_departure" ||
    (d.status === "issue" && d.issueReason === "address_not_found")
  );
}
