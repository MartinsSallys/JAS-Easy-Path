import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Junta classes do Tailwind sem conflito (ex.: p-2 e p-4 juntos ficam só p-4). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}