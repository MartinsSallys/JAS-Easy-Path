import type { BackendGeocodeResponseDTO } from "@/types/dto";
import { seedDeliveries } from "@/mocks/seed";
import { USE_MOCK } from "./config";
import { http } from "./http";

export interface AddressSuggestion {
  label: string;
  latitude: number;
  longitude: number;
}

const DEMO_PLACES: AddressSuggestion[] = [
  ...seedDeliveries().map((d) => ({
    label: d.address,
    latitude: d.lat,
    longitude: d.lng,
  })),
  {
    label: "Av. ACM, 1500 - Pituba, Salvador - BA",
    latitude: -12.9992,
    longitude: -38.4581,
  },
  {
    label: "Rua Chile, 42 - Centro Histórico, Salvador - BA",
    latitude: -12.9765,
    longitude: -38.5136,
  },
  {
    label: "Av. Tancredo Neves, 620 - Caminho das Árvores, Salvador - BA",
    latitude: -12.9814,
    longitude: -38.4559,
  },
];

export async function searchAddressSuggestions(
  query: string,
  signal?: AbortSignal,
): Promise<AddressSuggestion[]> {
  const trimmed = query.trim();
  if (trimmed.length < 4) return [];

  if (USE_MOCK) {
    const normalized = trimmed.toLowerCase();
    return DEMO_PLACES.filter((item) =>
      item.label.toLowerCase().includes(normalized),
    ).slice(0, 5);
  }

  const response = await http<BackendGeocodeResponseDTO>("/geocoding/forward", {
    method: "POST",
    body: JSON.stringify({ endereco: trimmed, country_code: "br" }),
    signal,
  });

  const seen = new Set<string>();
  return response.results
    .filter((item) => {
      if (!item.display_name || seen.has(item.display_name)) return false;
      seen.add(item.display_name);
      return true;
    })
    .slice(0, 5)
    .map((item) => ({
      label: item.display_name,
      latitude: item.latitude,
      longitude: item.longitude,
    }));
}