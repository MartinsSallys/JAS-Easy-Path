import { describe, expect, it } from "vitest";
import { parseDeliveriesCsv } from "./csv";

describe("parseDeliveriesCsv", () => {
  it("reporta erro na linha quando abre aspas nas observações e não fecha", () => {
    const csv = [
      "pedido,cliente,telefone,endereco,janela_inicio,janela_fim,prioridade,observacoes",
      '#101,Maria Souza,(71) 98888-1234,"Rua das Flores, 10",19:00,19:30,normal,"Portão azul sem fechar',
    ].join("\n");

    const result = parseDeliveriesCsv(csv);
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].line).toBe(2);
    expect(result.rows[0].errors.some((e) => e.includes("MissingQuotes") || e.includes("aspas"))).toBe(true);
  });

  it("reporta erro na linha quando há coluna extra além do cabeçalho", () => {
    const csv = [
      "pedido,cliente,telefone,endereco,janela_inicio,janela_fim,prioridade,observacoes",
      "#102,Carlos Lima,(71) 97777-1111,Av. Brasil 50,18:00,19:00,alta,Obs,ColunaExtraInvalida",
    ].join("\n");

    const result = parseDeliveriesCsv(csv);
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].line).toBe(2);
    expect(result.rows[0].errors.some((e) => e.includes("TooManyFields"))).toBe(true);
  });

  it("aceita linha válida com janela vazia (herda expediente)", () => {
    const csv = [
      "pedido,cliente,telefone,endereco,janela_inicio,janela_fim,prioridade,observacoes",
      "#103,Ana Paula,(71) 96666-2222,Rua Nova 12,,,normal,Sem horário fixo",
    ].join("\n");

    const result = parseDeliveriesCsv(csv);
    expect(result.fileError).toBeNull();
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].errors).toHaveLength(0);
    expect(result.rows[0].delivery.windowStart).toBe("");
    expect(result.rows[0].delivery.windowEnd).toBe("");
  });

  it("reporta erro quando apenas um horário da janela está preenchido", () => {
    const csv = [
      "pedido,cliente,telefone,endereco,janela_inicio,janela_fim,prioridade,observacoes",
      "#104,Pedro Alves,(71) 95555-3333,Rua Velha 40,19:00,,normal,",
    ].join("\n");

    const result = parseDeliveriesCsv(csv);
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].errors.length).toBeGreaterThan(0);
  });

  it("reporta erro quando a janela tem menos de 8 minutos", () => {
    const csv = [
      "pedido,cliente,telefone,endereco,janela_inicio,janela_fim,prioridade,observacoes",
      "#105,Lucas Rocha,(71) 94444-4444,Rua Alta 88,14:00,14:05,normal,",
    ].join("\n");

    const result = parseDeliveriesCsv(csv);
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].errors.some((e) => e.includes("8 minutos"))).toBe(true);
  });

  it("aceita linha válida com janela terminando em 24:00", () => {
    const csv = [
      "pedido,cliente,telefone,endereco,janela_inicio,janela_fim,prioridade,observacoes",
      "#106,Fernanda Dias,(71) 93333-5555,Rua do Porto 9,23:30,24:00,alta,Última entrega",
    ].join("\n");

    const result = parseDeliveriesCsv(csv);
    expect(result.fileError).toBeNull();
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].errors).toHaveLength(0);
    expect(result.rows[0].delivery.windowEnd).toBe("24:00");
  });
});