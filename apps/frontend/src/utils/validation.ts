import type { NewDelivery } from "@/types/domain";
import { hhmmToMinutes } from "@/services/mappers";

export type FieldErrors = Partial<Record<keyof NewDelivery, string>>;

const MIN_WINDOW_MINUTES = 8;

/** Formata telefone brasileiro (10 ou 11 dígitos) enquanto o usuário digita. */
export function formatBrPhone(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 11);
  if (digits.length === 0) return "";
  if (digits.length <= 2) return `(${digits}`;
  if (digits.length <= 6) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  if (digits.length <= 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  }
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

/** Retorna true quando o telefone opcional está preenchido e possui DDD + 8 ou 9 dígitos. */
export function isValidOptionalPhone(phone: string): boolean {
  const digits = phone.replace(/\D/g, "");
  return digits.length === 10 || digits.length === 11;
}

/** Mesma validação para o formulário e para a importação de CSV. */
export function validateNewDelivery(values: NewDelivery): FieldErrors {
  const errors: FieldErrors = {};

  if (!values.customerName.trim()) {
    errors.customerName = "Informe o nome do cliente.";
  }
  if (!values.address.trim()) {
    errors.address = "Informe o endereço.";
  }

  const startRaw = values.windowStart.trim();
  const endRaw = values.windowEnd.trim();

  if (startRaw !== "" || endRaw !== "") {
    if (startRaw === "") {
      errors.windowStart = "Informe o início da janela ou deixe os dois horários em branco.";
    }
    if (endRaw === "") {
      errors.windowEnd = "Informe o fim da janela ou deixe os dois horários em branco.";
    }

    let startMin: number | null = null;
    let endMin: number | null = null;

    if (startRaw !== "") {
      try {
        startMin = hhmmToMinutes(startRaw);
        if (startMin >= 1440) {
          errors.windowStart = "O horário inicial deve ser antes de 24:00.";
          startMin = null;
        }
      } catch {
        errors.windowStart = "Use o formato HH:mm (ex.: 19:00).";
      }
    }

    if (endRaw !== "") {
      try {
        endMin = hhmmToMinutes(endRaw);
      } catch {
        errors.windowEnd = "Use o formato HH:mm até 24:00 (ex.: 20:00).";
      }
    }

    if (startMin !== null && endMin !== null) {
      if (endMin <= startMin) {
        errors.windowEnd = "O horário final deve ser depois do inicial.";
      } else if (endMin - startMin < MIN_WINDOW_MINUTES) {
        errors.windowEnd = `A janela precisa ter pelo menos ${MIN_WINDOW_MINUTES} minutos de atendimento.`;
      }
    }
  }

  if (values.phone && !isValidOptionalPhone(values.phone)) {
    errors.phone = "Informe o telefone com DDD (10 ou 11 dígitos).";
  }

  return errors;
}