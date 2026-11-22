interface Point {
  lat: number;
  lng: number;
}

export const MAX_WAYPOINTS = 8;

const coords = (p: Point) => `${p.lat},${p.lng}`;

export function googleMapsStopUrl(stop: Point): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${coords(stop)}&travelmode=driving`;
}

/** O Waze só aceita UM destino por link. Por isso navegamos parada a parada. */
export function wazeStopUrl(stop: Point): string {
  return `https://waze.com/ul?ll=${coords(stop)}&navigate=yes`;
}

export function googleMapsRouteUrl(origin: Point, stops: Point[]) {
  const used = stops.slice(0, MAX_WAYPOINTS + 1); // waypoints + destino final
  if (used.length === 0) return { url: null, usedStops: 0, truncated: false };

  const destination = used[used.length - 1];
  const waypoints = used.slice(0, -1).map(coords).join("|");

  let url = `https://www.google.com/maps/dir/?api=1&origin=${coords(origin)}&destination=${coords(destination)}&travelmode=driving`;
  if (waypoints) url += `&waypoints=${encodeURIComponent(waypoints)}`;

  return { url, usedStops: used.length, truncated: stops.length > used.length };
}