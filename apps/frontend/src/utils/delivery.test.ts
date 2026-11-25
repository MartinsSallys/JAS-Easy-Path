import { describe, expect, it } from "vitest";
import type { Delivery } from "@/types/domain";
import { isDeliveryEditable } from "./delivery";

const base: Delivery = {
  id: "del-1",
  orderCode: "#1001",
  customerName: "Ana Paula",
  phone: "",
  address: "Rua A, 10",
  lat: -13.37,
  lng: -39.07,
  windowStart: "18:00",
  windowEnd: "20:00",
  hasExplicitTimeWindow: true,
  priority: "normal",
  status: "waiting_departure",
  notes: "",
  issueReason: null,
  completedAt: null,
  history: [],
};

describe("isDeliveryEditable", () => {
  it("permite editar entrega aguardando saída", () => {
    expect(isDeliveryEditable({ ...base, status: "waiting_departure" })).toBe(true);
  });

  it("bloqueia entrega concluída ou já em andamento", () => {
    expect(isDeliveryEditable({ ...base, status: "completed" })).toBe(false);
    expect(isDeliveryEditable({ ...base, status: "in_progress" })).toBe(false);
  });

  it("permite corrigir pendência de endereço não localizado", () => {
    expect(
      isDeliveryEditable({ ...base, status: "issue", issueReason: "address_not_found" }),
    ).toBe(true);
  });

  it("bloqueia pendência registrada por outro motivo", () => {
    expect(
      isDeliveryEditable({ ...base, status: "issue", issueReason: "customer_absent" }),
    ).toBe(false);
  });
});
