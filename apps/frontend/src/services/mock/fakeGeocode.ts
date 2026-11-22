import type { Place } from "@/types/domain";

/**
 * SIMULAÇÃO: transforma um texto em coordenadas fixas perto da origem.
 * NÃO é geocodificação real. A real é responsabilidade do backend (issue #6).
 */
export function fakeGeocode(address: string, origin: Place) {
  let hash = 0;
  for (const char of address) {
    hash = (hash * 31 + (char.codePointAt(0) ?? 0)) % 100000;
  }
  const angle = (hash % 360) * (Math.PI / 180);
  const radius = 0.004 + ((hash % 97) / 97) * 0.03;
  return {
    lat: origin.lat + Math.sin(angle) * radius,
    lng: origin.lng + Math.cos(angle) * radius,
  };
}