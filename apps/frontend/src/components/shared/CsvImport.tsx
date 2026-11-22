import { useState, type ChangeEvent } from "react";
import { Download, FileSpreadsheet } from "lucide-react";
import type { NewDelivery } from "@/types/domain";
import { CSV_TEMPLATE, parseDeliveriesCsv, type CsvParseResult } from "@/utils/csv";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

interface CsvImportProps {
  onImport: (deliveries: NewDelivery[]) => Promise<void>;
  onClose: () => void;
  importing?: boolean;
}

export function CsvImport({ onImport, onClose, importing }: CsvImportProps) {
  const [result, setResult] = useState<CsvParseResult | null>(null);
  const [fileName, setFileName] = useState<string>("");

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    const text = await file.text();
    setResult(parseDeliveriesCsv(text));
  };

  const valid = result?.rows.filter((row) => row.errors.length === 0) ?? [];
  const invalidCount = (result?.rows.length ?? 0) - valid.length;

  const confirm = async () => {
    if (valid.length === 0) return;
    await onImport(valid.map((row) => row.delivery));
    onClose();
  };

  const templateHref = `data:text/csv;charset=utf-8,${encodeURIComponent(CSV_TEMPLATE)}`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Importar entregas via CSV</h2>
          <p className="text-xs text-slate-500">
            Colunas obrigatórias: <strong>cliente</strong> e <strong>endereco</strong>. Janelas vazias herdam o expediente.
          </p>
        </div>
        <a
          href={templateHref}
          download="modelo-entregas-jas.csv"
          className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          <Download className="h-4 w-4" />
          Baixar modelo CSV
        </a>
      </div>

      <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center hover:border-blue-500 hover:bg-blue-50/40">
        <FileSpreadsheet className="mb-2 h-8 w-8 text-blue-600" />
        <span className="text-sm font-medium text-slate-800">
          {fileName ? `Arquivo selecionado: ${fileName}` : "Clique para selecionar um arquivo .csv"}
        </span>
        <span className="mt-1 text-xs text-slate-500">
          Aceita separador vírgula (,) ou ponto e vírgula (;)
        </span>
        <input type="file" accept=".csv,text/csv" onChange={handleFile} className="sr-only" />
      </label>

      {result?.fileError ? (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {result.fileError}
        </div>
      ) : null}

      {result && result.rows.length > 0 ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge tone="green">{valid.length} válida(s)</Badge>
            {invalidCount > 0 ? <Badge tone="red">{invalidCount} com erro</Badge> : null}
          </div>

          <div className="max-h-64 overflow-auto rounded-lg border border-slate-200">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-slate-100 text-slate-700">
                <tr>
                  <th className="px-3 py-2">Linha</th>
                  <th className="px-3 py-2">Cliente</th>
                  <th className="px-3 py-2">Endereço</th>
                  <th className="px-3 py-2">Janela</th>
                  <th className="px-3 py-2">Situação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {result.rows.map((row) => {
                  const hasError = row.errors.length > 0;
                  return (
                    <tr key={row.line} className={hasError ? "bg-red-50/70" : "bg-white"}>
                      <td className="px-3 py-2 font-mono">{row.line}</td>
                      <td className="px-3 py-2 font-medium">{row.delivery.customerName || "—"}</td>
                      <td className="px-3 py-2">{row.delivery.address || "—"}</td>
                      <td className="px-3 py-2">
                        {row.delivery.windowStart || row.delivery.windowEnd
                          ? `${row.delivery.windowStart} – ${row.delivery.windowEnd}`
                          : "Expediente"}
                      </td>
                      <td className="px-3 py-2">
                        {hasError ? (
                          <span className="font-medium text-red-700">{row.errors.join(" ")}</span>
                        ) : (
                          <span className="text-green-700">Pronta para importar</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="flex flex-wrap justify-end gap-2 pt-2">
        <Button variant="secondary" onClick={onClose}>
          Fechar
        </Button>
        <Button onClick={confirm} disabled={valid.length === 0 || importing}>
          {importing ? "Importando..." : `Importar ${valid.length} entrega(s)`}
        </Button>
      </div>
    </div>
  );
}