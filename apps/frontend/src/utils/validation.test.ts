import { describe, expect, it } from "vitest";
import { validateNewDelivery } from "./validation";
import type { NewDelivery } from "@/types/domain";

function makeDelivery(overrides: Partial<NewDelivery> = {}): NewDelivery {
  return {
    orderCode: "#101",
    customerName: "João Silva",
    phone: "(71) 99999-8888",
    address: "Rua Central, 100",
    windowStart: "",
    windowEnd: "",
    priority: "normal",
    notes: "",
    ...overrides,
  };
}

describe("validateNewDelivery", () => {
  it("aceita janela vazia (herda expediente)", () => {
    const errors = validateNewDelivery(makeDelivery({ windowStart: "", windowEnd: "" }));
    expect(errors.windowStart).toBeUndefined();
    expect(errors.windowEnd).toBeUndefined();
    expect(Object.keys(errors)).toHaveLength(0);
  });

  it("rejeita quando apenas o início ou apenas o fim da janela é preenchido", () => {
    const onlyStart = validateNewDelivery(makeDelivery({ windowStart: "19:00", windowEnd: "" }));
    expect(onlyStart.windowEnd).toBeDefined();

    const onlyEnd = validateNewDelivery(makeDelivery({ windowStart: "", windowEnd: "20:00" }));
    expect(onlyEnd.windowStart).toBeDefined();
  });

  it("rejeita janela com menos de 8 minutos de atendimento", () => {
    const errors = validateNewDelivery(makeDelivery({ windowStart: "09:00", windowEnd: "09:07" }));
    expect(errors.windowEnd).toContain("8 minutos");
  });

  it("aceita janela exata de 8 minutos de atendimento", () => {
    const errors = validateNewDelivery(makeDelivery({ windowStart: "09:00", windowEnd: "09:08" }));
    expect(errors.windowStart).toBeUndefined();
    expect(errors.windowEnd).toBeUndefined();
  });

  it("aceita término da janela em 24:00 (fim do dia)", () => {
    const errors = validateNewDelivery(makeDelivery({ windowStart: "23:30", windowEnd: "24:00" }));
    expect(errors.windowStart).toBeUndefined();
    expect(errors.windowEnd).toBeUndefined();
  });

  it("rejeita início da janela em 24:00", () => {
    const errors = validateNewDelivery(makeDelivery({ windowStart: "24:00", windowEnd: "24:00" }));
    expect(errors.windowStart).toBeDefined();
  });
});