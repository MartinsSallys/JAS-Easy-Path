import { useEffect, useMemo } from "react";
import L from "leaflet";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import type { Delivery, Place } from "@/types/domain";

interface RouteMapProps {
  origin: Place;
  stops: Delivery[];
}

type LatLng = [number, number];

/** Ícone redondo e numerado, feito com HTML (evita o bug do ícone padrão do Leaflet no Vite). */
function pin(label: string, modifier = "") {
  return L.divIcon({
    className: "",
    html: `<div class="stop-pin ${modifier}">${label}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

/** Ajusta o zoom para caberem todos os pontos sempre que a rota muda. */
function FitBounds({ points }: { points: LatLng[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 0) map.fitBounds(points, { padding: [30, 30] });
  }, [map, points]);
  return null;
}

export function RouteMap({ origin, stops }: RouteMapProps) {
  const originPoint: LatLng = [origin.lat, origin.lng];
  const points = useMemo<LatLng[]>(
    () => [[origin.lat, origin.lng], ...stops.map((s): LatLng => [s.lat, s.lng])],
    [origin, stops],
  );

  return (
    <MapContainer
      center={originPoint}
      zoom={13}
      className="h-[420px] w-full rounded-xl" // o mapa PRECISA de altura, senão some
      aria-label="Mapa da rota"
    >
      <TileLayer
        attribution="&copy; colaboradores do OpenStreetMap"
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds points={points} />
      {/* A linha reta liga os pontos NA ORDEM. Não segue as ruas. */}
      <Polyline positions={points} pathOptions={{ color: "#2563eb", weight: 3, dashArray: "6 6" }} />
      <Marker position={originPoint} icon={pin("P", "stop-pin--origin")}>
        <Popup>{origin.name}</Popup>
      </Marker>
      {stops.map((stop, index) => {
        const modifier =
          stop.status === "completed" ? "stop-pin--done" : stop.status === "issue" ? "stop-pin--issue" : "";
        return (
          <Marker key={stop.id} position={[stop.lat, stop.lng]} icon={pin(String(index + 1), modifier)}>
            <Popup>
              <strong>
                {index + 1}. {stop.customerName}
              </strong>
              <br />
              {stop.address}
              <br />
              {stop.windowStart} – {stop.windowEnd}
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}