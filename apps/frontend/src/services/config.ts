// true por padrão: sem .env o app roda com dados fictícios.
export const USE_MOCK: boolean = import.meta.env.VITE_USE_MOCK !== "false";
export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";