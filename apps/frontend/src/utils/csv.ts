import Papa from "papaparse";
import type { NewDelivery, Priority } from "@/types/domain";
import { validateNewDelivery } from "./validation";

export const CSV_TEMPLATE =
  "pedido,cliente,telefone,endereco,janela_inicio,janela_fim,prioridade,observacoes\n" +
  '#2001,Maria Souza,(71) 98888-1234,"Rua das Flores, 10 - Centro",19:00,19:30,normal,Portão azul\n';

const REQUIRED_COLUMNS = ["cliente", "endereco"];

export interface CsvRow {
  line: number;
  delivery: NewDelivery;
  errors: string[];
}

export interface CsvParseResult {
  rows: CsvRow[];
  fileError: string | null;
}

function toPriority(raw: string): Priority {
  const value = raw.trim().toLowerCase();
  if (value === "alta" || value === "high") return "high";
  if (value === "baixa" || value === "low") return "low";
  return "normal";
}

/** O Excel costuma salvar "9:00" em vez de "09:00". */
function toTime(raw: string): string {
  const value = raw.trim();
  return /^\d:\d{2}$/.test(value) ? `0${value}` : value;
}

export function parseDeliveriesCsv(text: string): CsvParseResult {
  const parsed = Papa.parse<Record<string, string>>(text, {
    header: true,
    skipEmptyLines: "greedy",
    transformHeader: (header) => header.replace(/^\uFEFF/, "").trim().toLowerCase(),
  });

  const columns = parsed.meta.fields ?? [];
  const missing = REQUIRED_COLUMNS.filter((column) => !columns.includes(column));
  if (missing.length > 0) {
    return { rows: [], fileError: `Colunas obrigatórias ausentes: ${missing.join(", ")}.` };
  }

  // Agrupa erros estruturais do PapaParse (ex.: aspas sem fechar ou colunas extras/faltando)
  const parserErrorsByRow = new Map<number, string[]>();
  const globalParserErrors: string[] = [];

  for (const err of parsed.errors) {
    const detail = `Erro de estrutura CSV (${err.code}): ${err.message}`;
    if (typeof err.row === "number") {
      const list = parserErrorsByRow.get(err.row) ?? [];
      list.push(detail);
      parserErrorsByRow.set(err.row, list);
    } else {
      globalParserErrors.push(detail);
    }
  }

  if (globalParserErrors.length > 0) {
    return { rows: [], fileError: globalParserErrors.join(" | ") };
  }

  const rows: CsvRow[] = parsed.data.map((raw, index) => {
    const delivery: NewDelivery = {
      orderCode: (raw.pedido ?? "").trim(),
      customerName: (raw.cliente ?? "").trim(),
      phone: (raw.telefone ?? "").trim(),
      address: (raw.endereco ?? "").trim(),
      windowStart: toTime(raw.janela_inicio ?? ""),
      windowEnd: toTime(raw.janela_fim ?? ""),
      priority: toPriority(raw.prioridade ?? ""),
      notes: (raw.observacoes ?? "").trim(),
    };

    const rowErrors = [
      ...(parserErrorsByRow.get(index) ?? []),
      ...Object.values(validateNewDelivery(delivery)),
    ];

    return { line: index + 2, delivery, errors: rowErrors };
  });

  const fileError =
    rows.length === 0
      ? parsed.errors.length > 0
        ? `Erro ao ler o arquivo CSV: ${parsed.errors[0].message}`
        : "O arquivo não tem linhas de dados."
      : null;

  return { rows, fileError };
}