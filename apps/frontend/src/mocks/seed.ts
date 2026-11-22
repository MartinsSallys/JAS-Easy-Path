import type { Delivery, DeliveryStatus, Place, Priority } from "@/types/domain";

// TODOS os dados abaixo são FICTÍCIOS (nome, endereço e coordenadas).
export const seedOrigin: Place = {
  name: "Pizzaria Forno Bom (demo)",
  address: "Rua das Palmeiras, 100 - Centro",
  lat: -12.9714,
  lng: -38.5014,
};

// [cliente, endereço, lat, lng, janela início, janela fim, status, prioridade, observações]
type Row = [string, string, number, number, string, string, DeliveryStatus, Priority, string];

const rows: Row[] = [
  ["Ana Paula Lima", "Rua A, 12 - Centro", -12.969, -38.499, "18:30", "19:00", "completed", "normal", ""],
  ["Fabio Nunes", "Av. F, 910 - Ondina", -12.984, -38.512, "19:20", "19:50", "in_progress", "high", "Portão azul"],
  // ... mais 13 linhas com coordenadas espalhadas perto da origem
];

export function seedDeliveries(): Delivery[] {
  return rows.map(([customerName, address, lat, lng, windowStart, windowEnd, status, priority, notes], i) => ({
    id: `e${i + 1}`,
    orderCode: `#${1001 + i}`,
    customerName,
    phone: `(71) 98888-${String(1000 + i).padStart(4, "0")}`,
    address,
    lat,
    lng,
    windowStart,
    windowEnd,
    priority,
    status,
    notes,
    issueReason: status === "issue" ? "customer_absent" : null,
    completedAt: status === "completed" ? windowEnd : null,
    history: [{ at: "18:00", text: "Pedido cadastrado" }],
  }));
}