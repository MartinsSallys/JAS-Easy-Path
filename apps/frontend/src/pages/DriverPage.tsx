import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  MapPin,
  Navigation,
  Phone,
  Truck,
} from "lucide-react";
import type { IssueReason } from "@/types/domain";
import { useNow } from "@/hooks/useNow";
import { useAppStore } from "@/store/useAppStore";
import { issueLabel } from "@/utils/format";
import { googleMapsStopUrl, wazeStopUrl } from "@/utils/navigation";
import { needsVisit, orderedStops, selectVehicleRoute } from "@/utils/route";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/shared/StatusBadge";

type Mode = "idle" | "confirm_delivery" | "issue_form";

export default function DriverPage() {
  const deliveries = useAppStore((s) => s.deliveries);
  const route = useAppStore((s) => s.route);
  const loading = useAppStore((s) => s.loading);
  const completeDelivery = useAppStore((s) => s.completeDelivery);
  const reportIssue = useAppStore((s) => s.reportIssue);
  const now = useNow();

  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("idle");
  const [reason, setReason] = useState<IssueReason>("customer_absent");
  const [note, setNote] = useState("");

  const activeRoute = useMemo(
    () => selectVehicleRoute(route, selectedVehicleId),
    [route, selectedVehicleId],
  );
  const stops = useMemo(
    () => orderedStops(deliveries, activeRoute),
    [deliveries, activeRoute],
  );

  const next = stops.find(needsVisit);
  const completed = stops.filter((d) => d.status === "completed").length;
  const percent = stops.length ? Math.round((completed / stops.length) * 100) : 0;

  const handleDelivered = async () => {
    if (!next) return;
    await completeDelivery(next.id, now);
    setMode("idle");
  };

  const handleIssue = async () => {
    if (!next) return;
    await reportIssue(next.id, reason, note, now);
    setNote("");
    setReason("customer_absent");
    setMode("idle");
  };

  return (
    <div className="min-h-screen bg-slate-100 px-4 py-5">
      <div className="mx-auto max-w-md space-y-4">
        <header className="flex items-center justify-between">
          <Link
            to="/rota"
            className="inline-flex min-h-10 items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
          >
            <ArrowLeft className="h-4 w-4" />
            Voltar ao painel
          </Link>
          <span className="font-mono text-xs text-slate-500">{now}</span>
        </header>

        {route && route.routes.length > 1 ? (
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            <Truck className="h-4 w-4 shrink-0 text-slate-500" />
            {route.routes.map((vr) => {
              const isSelected = activeRoute?.vehicleId === vr.vehicleId;
              return (
                <button
                  key={vr.vehicleId}
                  type="button"
                  onClick={() => {
                    setSelectedVehicleId(vr.vehicleId);
                    setMode("idle");
                  }}
                  className={`min-h-9 shrink-0 rounded-full px-3 text-xs font-medium ${
                    isSelected
                      ? "bg-blue-600 text-white"
                      : "bg-white text-slate-700 ring-1 ring-slate-200"
                  }`}
                >
                  {vr.vehicleName}
                </button>
              );
            })}
          </div>
        ) : null}

        <Card className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-700">
              {activeRoute?.vehicleName ?? "Rota do entregador"}
            </span>
            <span className="font-bold text-blue-600">
              {completed}/{stops.length} ({percent}%)
            </span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-green-600 transition-all" style={{ width: `${percent}%` }} />
          </div>
        </Card>

        {next ? (
          <Card className="space-y-4 border-2 border-blue-600">
            <div className="flex items-start justify-between gap-2">
              <div>
                <span className="text-xs font-bold tracking-wide text-blue-600 uppercase">
                  Próxima parada
                </span>
                <h1 className="mt-0.5 text-xl font-bold text-slate-900">
                  {next.orderCode} · {next.customerName}
                </h1>
              </div>
              <StatusBadge delivery={next} now={now} />
            </div>

            <div className="space-y-1.5 text-sm text-slate-700">
              <p className="flex items-start gap-2">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                <span>{next.address}</span>
              </p>
              <p className="text-xs text-slate-500">
                Janela de entrega: <strong>{next.windowStart} – {next.windowEnd}</strong>
              </p>
              {next.notes ? (
                <p className="rounded-lg bg-amber-50 p-2.5 text-xs text-amber-900">
                  <strong>Obs.:</strong> {next.notes}
                </p>
              ) : null}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <a
                href={googleMapsStopUrl(next)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg bg-slate-900 px-3 text-xs font-semibold text-white hover:bg-slate-800"
              >
                <Navigation className="h-3.5 w-3.5" />
                Google Maps
              </a>
              <a
                href={wazeStopUrl(next)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg bg-sky-600 px-3 text-xs font-semibold text-white hover:bg-sky-700"
              >
                <Navigation className="h-3.5 w-3.5" />
                Waze
              </a>
            </div>

            {next.phone ? (
              <a
                href={`tel:${next.phone.replace(/\D/g, "")}`}
                className="flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white text-xs font-semibold text-slate-800 hover:bg-slate-50"
              >
                <Phone className="h-4 w-4 text-green-600" />
                Ligar para {next.phone}
              </a>
            ) : null}

            {mode === "idle" ? (
              <div className="grid grid-cols-2 gap-2 pt-2">
                <Button
                  variant="warning"
                  onClick={() => setMode("issue_form")}
                  className="min-h-12"
                >
                  <AlertTriangle className="h-4 w-4" />
                  Pendência
                </Button>
                <Button
                  variant="success"
                  onClick={() => setMode("confirm_delivery")}
                  className="min-h-12"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Entregue
                </Button>
              </div>
            ) : null}

            {mode === "confirm_delivery" ? (
              <div className="space-y-3 rounded-xl bg-green-50 p-3.5">
                <p className="text-sm font-semibold text-green-950">
                  Confirmar que o pedido {next.orderCode} foi entregue?
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="secondary" onClick={() => setMode("idle")}>
                    Cancelar
                  </Button>
                  <Button
                    variant="success"
                    onClick={() => void handleDelivered()}
                    disabled={loading}
                  >
                    Sim, entregue
                  </Button>
                </div>
              </div>
            ) : null}

            {mode === "issue_form" ? (
              <div className="space-y-3 rounded-xl bg-orange-50 p-3.5">
                <p className="text-sm font-semibold text-orange-950">Registrar pendência</p>
                <select
                  value={reason}
                  onChange={(e) => setReason(e.target.value as IssueReason)}
                  className="min-h-11 w-full rounded-lg border border-orange-300 bg-white px-3 text-sm"
                >
                  {(Object.keys(issueLabel) as IssueReason[]).map((key) => (
                    <option key={key} value={key}>
                      {issueLabel[key]}
                    </option>
                  ))}
                </select>
                <textarea
                  rows={2}
                  placeholder="Observação adicional (opcional)..."
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  className="w-full rounded-lg border border-orange-300 bg-white p-2.5 text-sm"
                />
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="secondary" onClick={() => setMode("idle")}>
                    Cancelar
                  </Button>
                  <Button
                    variant="warning"
                    onClick={() => void handleIssue()}
                    disabled={loading}
                  >
                    Confirmar pendência
                  </Button>
                </div>
              </div>
            ) : null}
          </Card>
        ) : (
          <Card className="py-8 text-center">
            <CheckCircle2 className="mx-auto h-10 w-10 text-green-600" />
            <h2 className="mt-2 text-lg font-bold text-slate-900">Todas as paradas finalizadas!</h2>
            <p className="mt-1 text-xs text-slate-500">
              Não há mais entregas pendentes para este veículo.
            </p>
          </Card>
        )}

        <div className="space-y-2">
          <h2 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
            Sequência do veículo ({stops.length})
          </h2>
          {stops.map((s, idx) => (
            <Card key={s.id} className="flex items-center justify-between gap-2 p-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">
                  {idx + 1}. {s.customerName}
                </p>
                <p className="truncate text-xs text-slate-500">{s.address}</p>
              </div>
              <StatusBadge delivery={s} now={now} />
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}