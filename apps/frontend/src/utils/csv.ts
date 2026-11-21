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

function findUnclosedQuoteLine(text: string): number | null {
  let inQuotes = false;
  let openedAtLine: number | null = null;
  let line = 1;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (inQuotes && text[i + 1] === '"') {
        i++; // aspa escapada ("") dentro de campo entre aspas
      } else {
        inQuotes = !inQuotes;
        openedAtLine = inQuotes ? line : null;
      }
    } else if (ch === "\n") {
      line++;
    }
  }

  return inQuotes ? openedAtLine : null;
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

  const unclosedQuoteLine = findUnclosedQuoteLine(text);

  const parserErrorsByRow = new Map<number, string[]>();
  const globalParserErrors: string[] = [];

  for (const err of parsed.errors) {
    if (err.code === "MissingQuotes" && unclosedQuoteLine !== null) continue;

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

  if (unclosedQuoteLine === 1) {
    return {
      rows: [],
      fileError: "Erro de estrutura CSV (MissingQuotes): aspas não fechadas no cabeçalho (linha 1).",
    };
  }

  const rows: CsvRow[] = parsed.data.map((raw, index) => {
    const lineNumber = index + 2;
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

    const quoteError =
      unclosedQuoteLine !== null && lineNumber >= unclosedQuoteLine && index === parsed.data.length - 1
        ? [`Erro de estrutura CSV (MissingQuotes): aspas abertas sem fechamento (linha ${unclosedQuoteLine}).`]
        : [];

    const rowErrors = [
      ...quoteError,
      ...(parserErrorsByRow.get(index) ?? []),
      ...Object.values(validateNewDelivery(delivery)),
    ];

    return { line: lineNumber, delivery, errors: rowErrors };
  });

  if (unclosedQuoteLine !== null && rows.length === 0) {
    return {
      rows: [],
      fileError: `Erro de estrutura CSV (MissingQuotes): aspas abertas sem fechamento na linha ${unclosedQuoteLine}.`,
    };
  }

  const fileError =
    rows.length === 0
      ? parsed.errors.length > 0
        ? `Erro ao ler o arquivo CSV: ${parsed.errors[0].message}`
        : "O arquivo não tem linhas de dados."
      : null;

  return { rows, fileError };
}