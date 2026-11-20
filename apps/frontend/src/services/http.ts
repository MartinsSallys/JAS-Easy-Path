import type { ApiErrorDTO } from "@/types/dto";
import { API_URL } from "./config";

/** Único lugar do projeto que chama fetch. Devolve o JSON já tipado como T. */
export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    let message = `Erro ${response.status} ao chamar ${path}`;
    try {
      const body = (await response.json()) as Partial<ApiErrorDTO>;
      if (body.error?.message) {
        message = body.error.message;
      }
    } catch {
      // mantém a mensagem padrão se a resposta não vier em JSON
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T; // 204 = sucesso sem corpo (ex.: DELETE)
  }
  return (await response.json()) as T;
}