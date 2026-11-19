/** Hora atual no formato "HH:mm". */
export function currentHHmm(): string {
  return new Date().toTimeString().slice(0, 5);
}