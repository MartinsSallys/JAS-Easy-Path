import type { Delivery } from "@/types/domain";

interface Point {
  lat: number;
  lng: number;
}

const EARTH_RADIUS_KM = 6371;
const AVERAGE_SPEED_KMH = 25; // DEMONSTRATIVA
const MINUTES_PER_STOP = 4; // DEMONSTRATIVA

const toRad = (deg: number) => (deg * Math.PI) / 180;

/** Distância em LINHA RETA entre dois pontos (fórmula de Haversine). */
export function haversineKm(a: Point, b: Point): number {
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h));
}

/** Estimativa grosseira: soma das retas origem -> parada 1 -> parada 2 ... */
export function estimateRoute(origin: Point, stops: Point[]) {
  let km = 0;
  let previous = origin;
  for (const stop of stops) {
    km += haversineKm(previous, stop);
    previous = stop;
  }
  const minutes = (km / AVERAGE_SPEED_KMH) * 60 + stops.length * MINUTES_PER_STOP;
  return { distanceKm: Math.round(km * 10) / 10, durationMin: Math.round(minutes) };
}

/**
 * SIMULAÇÃO: "vizinho mais próximo". Sempre vai para a parada mais perto da atual.
 * NÃO é otimização real: ignora janelas de horário, prioridade e trânsito.
 */
export function nearestNeighborOrder(start: Point, deliveries: Delivery[]): Delivery[] {
  const remaining = [...deliveries];
  const ordered: Delivery[] = [];
  let current: Point = start;

  while (remaining.length > 0) {
    let bestIndex = 0;
    let bestDistance = Infinity;
    remaining.forEach((candidate, index) => {
      const distance = haversineKm(current, candidate);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = index;
      }
    });
    const [next] = remaining.splice(bestIndex, 1);
    ordered.push(next);
    current = next;
  }
  return ordered;
}