import type { NewDelivery } from "@/types/domain";

export type FieldErrors = Partial<Record<keyof NewDelivery, string>>;

const TIME_FORMAT = /^([01]\d|2[0-3]):[0-5]\d$/;

/** Mesma validação para o formulário e para a importação de CSV. */
export function validateNewDelivery(values: NewDelivery): FieldErrors {
  const errors: FieldErrors = {};

  if (!values.customerName.trim()) errors.customerName = "Informe o nome do cliente.";
  if (!values.address.trim()) errors.address = "Informe o endereço.";
  if (!TIME_FORMAT.test(values.windowStart)) errors.windowStart = "Use o formato HH:mm (ex.: 19:30).";
  if (!TIME_FORMAT.test(values.windowEnd)) errors.windowEnd = "Use o formato HH:mm (ex.: 20:00).";
  if (!errors.windowStart && !errors.windowEnd && values.windowEnd <= values.windowStart) {
    errors.windowEnd = "O horário final deve ser depois do inicial.";
  }
  if (values.phone && values.phone.replace(/\D/g, "").length < 10) {
    errors.phone = "Informe o telefone com DDD.";
  }
  return errors;
}