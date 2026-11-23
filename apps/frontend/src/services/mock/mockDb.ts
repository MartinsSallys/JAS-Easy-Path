import type { Delivery, RoutePlan, VehicleRoute } from "@/types/domain";
import { seedDeliveries, seedOrigin } from "@/mocks/seed";
import { estimateRoute } from "@/utils/geo";

/** "Banco de dados" falso: guarda tudo no localStorage do navegador. */

const STORAGE_KEY = "jas-mock-db-v2";

export interface MockDb {
  deliveries: Delivery[];
  route: RoutePlan;
}

/** Simula a demora da rede, para você ver os estados de carregamento. */
export const wait = (ms = 250) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Recalcula distância e tempo de cada veículo e os totais do plano do dia. */
export function recalcRoute(db: MockDb): MockDb {
  const byId = new Map(db.deliveries.map((d) => [d.id, d]));

  const routes: VehicleRoute[] = db.route.routes.map((vehicleRoute) => {
    const stops = vehicleRoute.stopIds
      .map((id) => byId.get(id))
      .filter((d): d is Delivery => d !== undefined);
    const { distanceKm, durationMin } = estimateRoute(db.route.origin, stops);
    const serviceMin = stops.length * 8;
    const travelMin = Math.max(0, durationMin - serviceMin);

    return {
      ...vehicleRoute,
      load: stops.length,
      distanceKm,
      durationMin,
      travelMin,
      waitMin: 0,
      serviceMin,
    };
  });

  const totalDistanceKm =
    Math.round(routes.reduce((sum, r) => sum + r.distanceKm, 0) * 10) / 10;
  const totalDurationMin = routes.reduce((sum, r) => sum + r.durationMin, 0);

  return {
    ...db,
    route: {
      ...db.route,
      routes,
      totalDistanceKm,
      totalDurationMin,
    },
  };
}

function seed(): MockDb {
  const deliveries = seedDeliveries();
  // Divide inicialmente entre 2 veículos para demonstrar o seletor de múltiplos veículos
  const splitIndex = Math.ceil(deliveries.length * 0.6);
  const motoStops = deliveries.slice(0, splitIndex).map((d) => d.id);
  const carroStops = deliveries.slice(splitIndex).map((d) => d.id);

  return recalcRoute({
    deliveries,
    route: {
      id: "rota-hoje",
      origin: seedOrigin,
      routes: [
        {
          vehicleId: "v1",
          vehicleName: "Moto 01 — Carlos (demo)",
          capacity: 12,
          load: motoStops.length,
          stopIds: motoStops,
          distanceKm: 0,
          durationMin: 0,
          travelMin: 0,
          waitMin: 0,
          serviceMin: 0,
        },
        {
          vehicleId: "v2",
          vehicleName: "Carro 01 — Mariana (demo)",
          capacity: 20,
          load: carroStops.length,
          stopIds: carroStops,
          distanceKm: 0,
          durationMin: 0,
          travelMin: 0,
          waitMin: 0,
          serviceMin: 0,
        },
      ],
      totalDistanceKm: 0,
      totalDurationMin: 0,
      status: "running",
      isSimulation: false,
    },
  });
}

export function saveDb(db: MockDb): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
}

export function loadDb(): MockDb {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as MockDb;
      if (Array.isArray(parsed?.route?.routes)) return parsed;
    } catch {
      // ignora cache corrompido e recria do seed
    }
  }
  const fresh = seed();
  saveDb(fresh);
  return fresh;
}

export function resetDb(): void {
  saveDb(seed());
}