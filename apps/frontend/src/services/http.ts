import type { ApiErrorDTO } from "@/types/dto";
import { API_URL } from "./config";

export class HttpError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "HttpError";
    this.status = status;
  }
}

interface FastApiValidationItem {
  loc?: (string | number)[];
  msg?: string;
}

interface FastApiErrorBody extends Partial<ApiErrorDTO> {
  detail?: string | FastApiValidationItem[];
}

function extractErrorMessage(body: FastApiErrorBody, fallback: string): string {
  if (body.error?.message) {
    return body.error.message;
  }
  if (typeof body.detail === "string" && body.detail.trim() !== "") {
    return body.detail;
  }
  if (Array.isArray(body.detail) && body.detail.length > 0) {
    return body.detail
      .map((item) => {
        const field = item.loc ? item.loc.slice(1).join(".") : "";
        return field ? `${field}: ${item.msg ?? "valor inválido"}` : (item.msg ?? "valor inválido");
      })
      .join(" | ");
  }
  return fallback;
}

/** Único lugar do projeto que chama fetch. Devolve o JSON já tipado como T. */
export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    let message = `Erro ${response.status} ao chamar ${path}`;
    try {
      const body = (await response.json()) as FastApiErrorBody;
      message = extractErrorMessage(body, message);
    } catch {
      // mantém a mensagem padrão se a resposta não vier em JSON
    }
    throw new HttpError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}