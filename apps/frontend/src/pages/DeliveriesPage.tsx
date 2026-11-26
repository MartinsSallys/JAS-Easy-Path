import { useState } from "react";
import { FileSpreadsheet, Pencil, Plus, Search, Trash2 } from "lucide-react";
import type { Delivery, DeliveryStatus, NewDelivery } from "@/types/domain";
import { useNow } from "@/hooks/useNow";
import { useAppStore } from "@/store/useAppStore";
import { toDeliveryInput } from "@/services/mappers";
import { isDeliveryDeletable, isDeliveryEditable } from "@/utils/delivery";
import { issueLabel, priorityLabel } from "@/utils/format";
import { isLate } from "@/utils/kpis";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CsvImport } from "@/components/shared/CsvImport";
import { DeliveryForm } from "@/components/shared/DeliveryForm";
import { StatusBadge } from "@/components/shared/StatusBadge";

type Panel = "none" | "form" | "csv";
type Filter = "all" | "late" | DeliveryStatus;

const NOT_EDITABLE_HINT =
  "Edição disponível só para entregas aguardando — alterar o cadastro não recalcula a rota já otimizada.";

const NOT_DELETABLE_HINT =
  "Exclusão indisponível para entregas em andamento ou concluídas — elas fazem parte do histórico da rota.";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "Todas" },
  { id: "waiting_departure", label: "Aguardando" },
  { id: "in_progress", label: "Em andamento" },
  { id: "completed", label: "Concluídas" },
  { id: "issue", label: "Pendências" },
  { id: "late", label: "Atrasadas" },
];

export default function DeliveriesPage() {
  const deliveries = useAppStore((s) => s.deliveries);
  const loading = useAppStore((s) => s.loading);
  const addDelivery = useAppStore((s) => s.addDelivery);
  const importDeliveries = useAppStore((s) => s.importDeliveries);
  const updateDelivery = useAppStore((s) => s.updateDelivery);
  const removeDelivery = useAppStore((s) => s.removeDelivery);
  const now = useNow();

  const [panel, setPanel] = useState<Panel>("none");
  const [editing, setEditing] = useState<Delivery | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Delivery | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const visible = deliveries.filter((d) => {
    const matchesFilter =
      filter === "all" ? true : filter === "late" ? isLate(d, now) : d.status === filter;
    const text = `${d.orderCode} ${d.customerName} ${d.address}`.toLowerCase();
    return matchesFilter && text.includes(search.trim().toLowerCase());
  });

const handleCreate = async (input: NewDelivery) => {
    await addDelivery(input);
    setFeedback("Entrega cadastrada com sucesso.");
    setPanel("none");
  };

  const handleUpdate = async (input: NewDelivery) => {
    if (!editing) return;
    await updateDelivery(editing.id, input);
    if (selected?.id === editing.id) {
      setSelected(useAppStore.getState().deliveries.find((d) => d.id === editing.id) ?? null);
    }
    setFeedback(`Entrega ${editing.orderCode} atualizada.`);
    setEditing(null);
    setPanel("none");
  };

  const openCreate = () => {
    setFeedback(null);
    setEditing(null);
    setPanel((p) => (p === "form" ? "none" : "form"));
  };

  const openEdit = (d: Delivery) => {
    setFeedback(null);
    setEditing(d);
    setPanel("form");
  };

  const closeForm = () => {
    setEditing(null);
    setPanel("none");
  };

  const handleImport = async (inputs: NewDelivery[]) => {
    await importDeliveries(inputs);
    setFeedback(`${inputs.length} entrega(s) importada(s) com sucesso.`);
    setPanel("none");
  };

  const handleRemove = async (d: Delivery) => {
    if (!window.confirm(`Excluir a entrega ${d.orderCode} (${d.customerName})?`)) return;
    try {
      await removeDelivery(d.id);
      if (selected?.id === d.id) setSelected(null);
      setFeedback(`Entrega ${d.orderCode} removida.`);
    } catch {
      // Erro já registrado no store; não exibe confirmação falsa de remoção.
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Entregas</h1>
          <p className="text-sm text-slate-500">{deliveries.length} pedido(s) cadastrado(s) hoje</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant={panel === "csv" ? "primary" : "secondary"}
            onClick={() => {
              setFeedback(null);
              setPanel((p) => (p === "csv" ? "none" : "csv"));
            }}
          >
            <FileSpreadsheet className="h-4 w-4" />
            Importar CSV
          </Button>
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" />
            Nova entrega
          </Button>
        </div>
      </div>

      {feedback ? (
        <div
          role="status"
          className="flex items-center justify-between rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800"
        >
          <span>{feedback}</span>
          <button type="button" onClick={() => setFeedback(null)} className="text-xs underline">
            Fechar
          </button>
        </div>
      ) : null}

      {panel === "form" ? (
        <Card>
          <DeliveryForm
            key={editing?.id ?? "new"}
            initialValues={editing ? toDeliveryInput(editing) : undefined}
            onSubmit={editing ? handleUpdate : handleCreate}
            onCancel={closeForm}
            submitting={loading}
          />
        </Card>
      ) : null}

      {panel === "csv" ? (
        <Card>
          <CsvImport
            onImport={handleImport}
            onClose={() => setPanel("none")}
            importing={loading}
          />
        </Card>
      ) : null}

      <Card className="space-y-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-1.5">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                className={`min-h-9 rounded-lg px-3 text-xs font-medium transition-colors ${
                  filter === f.id
                    ? "bg-blue-600 text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="relative w-full md:w-72">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              placeholder="Buscar cliente, pedido ou endereço..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="min-h-10 w-full rounded-lg border border-slate-300 bg-white pr-3 pl-9 text-sm"
            />
          </div>
        </div>

        {visible.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 py-10 text-center">
            <p className="text-sm font-medium text-slate-700">Nenhuma entrega encontrada</p>
            <p className="mt-1 text-xs text-slate-500">
              Ajuste os filtros ou cadastre uma nova entrega acima.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs text-slate-500 uppercase">
                <tr>
                  <th className="py-3 pr-3">Pedido</th>
                  <th className="px-3 py-3">Cliente</th>
                  <th className="px-3 py-3">Endereço</th>
                  <th className="px-3 py-3">Janela</th>
                  <th className="px-3 py-3">Prioridade</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="py-3 pl-3 text-right">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visible.map((d) => (
                  <tr
                    key={d.id}
                    onClick={() => setSelected(d)}
                    className="cursor-pointer hover:bg-slate-50"
                  >
                    <td className="py-3 pr-3 font-mono text-xs font-semibold text-slate-700">
                      {d.orderCode}
                    </td>
                    <td className="px-3 py-3">
                      <p className="font-medium text-slate-900">{d.customerName}</p>
                      {d.phone ? <p className="text-xs text-slate-500">{d.phone}</p> : null}
                    </td>
                    <td className="px-3 py-3 text-slate-600">{d.address}</td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-700">
                      {d.windowStart} – {d.windowEnd}
                    </td>
                    <td className="px-3 py-3">
                      <Badge tone={d.priority === "high" ? "red" : d.priority === "low" ? "gray" : "blue"}>
                        {priorityLabel[d.priority]}
                      </Badge>
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge delivery={d} now={now} />
                    </td>
                    <td className="py-3 pl-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        onClick={() => openEdit(d)}
                        disabled={!isDeliveryEditable(d)}
                        title={isDeliveryEditable(d) ? undefined : NOT_EDITABLE_HINT}
                        aria-label={`Editar entrega ${d.orderCode}`}
                        className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg text-slate-400 hover:bg-blue-50 hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-slate-400"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleRemove(d)}
                        disabled={!isDeliveryDeletable(d)}
                        title={isDeliveryDeletable(d) ? undefined : NOT_DELETABLE_HINT}
                        aria-label={`Excluir entrega ${d.orderCode}`}
                        className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-slate-400"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {selected ? (
        <Card className="space-y-3 border-blue-200 bg-blue-50/30">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                Detalhes do pedido {selected.orderCode} — {selected.customerName}
              </h2>
              <p className="text-xs text-slate-600">{selected.address}</p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                onClick={() => openEdit(selected)}
                disabled={!isDeliveryEditable(selected)}
                title={isDeliveryEditable(selected) ? undefined : NOT_EDITABLE_HINT}
                className="min-h-9 px-3 text-xs"
              >
                Editar
              </Button>
              <Button variant="secondary" onClick={() => setSelected(null)} className="min-h-9 px-3 text-xs">
                Fechar
              </Button>
            </div>
          </div>

          {selected.issueReason ? (
            <p className="text-xs font-medium text-orange-700">
              Motivo da pendência: {issueLabel[selected.issueReason]}
            </p>
          ) : null}

          {selected.notes ? (
            <p className="text-xs text-slate-700">
              <strong>Observações:</strong> {selected.notes}
            </p>
          ) : null}

          <div className="space-y-1">
            <p className="text-xs font-semibold text-slate-700">Histórico:</p>
            <ul className="space-y-1 text-xs text-slate-600">
              {selected.history.map((h, idx) => (
                <li key={idx}>
                  <span className="font-mono font-semibold">{h.at}</span> — {h.text}
                </li>
              ))}
            </ul>
          </div>
        </Card>
      ) : null}
    </div>
  );
}