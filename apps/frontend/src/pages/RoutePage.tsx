import { useMemo, useState } from "react";
import { Check, Copy, ExternalLink, Route as RouteIcon, Share2, Sparkles, Truck } from "lucide-react";
import { useNow } from "@/hooks/useNow";
import { USE_MOCK } from "@/services/config";
import { useAppStore } from "@/store/useAppStore";
import { haversineKm } from "@/utils/geo";
import { googleMapsRouteUrl, googleMapsStopUrl } from "@/utils/navigation";
import { needsVisit, orderedStops, selectVehicleRoute } from "@/utils/route";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { RouteMap } from "@/components/shared/RouteMap";
import { StatusBadge } from "@/components/shared/StatusBadge";

export default function RoutePage() {
  const deliveries = useAppStore((s) => s.deliveries);
  const route = useAppStore((s) => s.route);
  const initialized = useAppStore((s) => s.initialized);
  const loading = useAppStore((s) => s.loading);
  const suggestSequence = useAppStore((s) => s.suggestSequence);
  const shareRoute = useAppStore((s) => s.shareRoute);
  const now = useNow();

  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const activeRoute = useMemo(
    () => selectVehicleRoute(route, selectedVehicleId),
    [route, selectedVehicleId],
  );

  const stops = useMemo(
    () => orderedStops(deliveries, activeRoute),
    [deliveries, activeRoute],
  );

if (!initialized) {
  return <p className="text-sm text-slate-500">Carregando plano de rota...</p>;
}
  const hasRoutes = !!route && route.routes.length > 0;
  const hasDeliveries = deliveries.length > 0;
  const pendingStops = stops.filter(needsVisit);
  const navigation = route ? googleMapsRouteUrl(route.origin, pendingStops) : null;

  const handleOptimize = async () => {
    try {
      await suggestSequence();
    } catch {
      // Erro já registrado no store
    }
  };

  const handleShare = async () => {
    const url = await shareRoute();
    if (!url) return;
    setShareUrl(url);
    await navigator.clipboard
      .writeText(url)
      .then(() => setCopied(true))
      .catch(() => setCopied(false));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900">Rota do dia</h1>
            {route?.isSimulation ? (
              <Badge tone="orange">Sequência estimada / simulada</Badge>
            ) : null}
          </div>
          {route ? (
            <p className="text-sm text-slate-500">
              Saída: {route.origin.name} ({route.origin.address})
            </p>
          ) : (
            <p className="text-sm text-slate-500">
              Nenhuma rota gerada para hoje ({deliveries.length} entrega(s) cadastrada(s))
            </p>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant={hasRoutes ? "secondary" : "primary"}
            onClick={() => void handleOptimize()}
            disabled={loading || !hasDeliveries}
          >
            <Sparkles className={`h-4 w-4 ${hasRoutes ? "text-blue-600" : "text-white"}`} />
            {hasRoutes ? "Sugerir sequência" : "Gerar primeira rota"}
          </Button>

          {hasRoutes ? (
            <Button variant="secondary" onClick={() => void handleShare()}>
              <Share2 className="h-4 w-4" />
              Compartilhar rota
            </Button>
          ) : null}

          {navigation?.url ? (
            <a
              href={navigation.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              <ExternalLink className="h-4 w-4" />
              Abrir no Google Maps
            </a>
          ) : null}
        </div>
      </div>

      {!hasRoutes ? (
        <Card className="space-y-3 py-10 text-center">
          <RouteIcon className="mx-auto h-10 w-10 text-blue-600" />
          <h2 className="text-lg font-semibold text-slate-900">
            Nenhuma rota gerada para hoje
          </h2>
          <p className="mx-auto max-w-md text-sm text-slate-500">
            {hasDeliveries
              ? `Você possui ${deliveries.length} entrega(s) cadastrada(s). Clique em "Gerar primeira rota" para montar a sequência de atendimento.`
              : "Cadastre ou importe entregas na aba Entregas para gerar a primeira rota do dia."}
          </p>
          {hasDeliveries ? (
            <div className="pt-2">
              <Button onClick={() => void handleOptimize()} disabled={loading}>
                <Sparkles className="h-4 w-4" />
                Gerar primeira rota
              </Button>
            </div>
          ) : null}
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 uppercase">
              <Truck className="h-4 w-4" />
              Veículo:
            </span>
            {route.routes.map((vr) => {
              const isSelected = activeRoute?.vehicleId === vr.vehicleId;
              return (
                <button
                  key={vr.vehicleId}
                  type="button"
                  onClick={() => setSelectedVehicleId(vr.vehicleId)}
                  className={`min-h-10 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                    isSelected
                      ? "border-blue-600 bg-blue-600 text-white"
                      : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {vr.vehicleName} ({vr.load}/{vr.capacity} pedidos)
                </button>
              );
            })}
          </div>

          {shareUrl ? (
            <Card className="flex flex-wrap items-center justify-between gap-3 border-blue-200 bg-blue-50/60">
              <div className="space-y-0.5 text-xs">
                <p className="font-semibold text-blue-950">Link para o entregador:</p>
                <p className="font-mono text-blue-800 break-all">{shareUrl}</p>
                {USE_MOCK ? (
                  <p className="text-amber-800">
                    Modo demonstração: este link abre os dados salvos apenas neste navegador.
                  </p>
                ) : null}
              </div>
              <Button
                variant="secondary"
                onClick={() => {
                  void navigator.clipboard.writeText(shareUrl);
                  setCopied(true);
                }}
                className="min-h-9 px-3 text-xs"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-green-600" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "Copiado" : "Copiar link"}
              </Button>
            </Card>
          ) : null}

          {navigation?.truncated ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900">
              O link do Google Maps inclui as primeiras {navigation.usedStops} paradas pendentes (limite de navegação por link).
            </div>
          ) : null}

          {activeRoute ? (
            <div className="grid gap-6 lg:grid-cols-5">
              <div className="space-y-2 lg:col-span-3">
                <RouteMap origin={route.origin} stops={stops} />
                <p className="text-xs text-slate-500">
                  * As linhas tracejadas ligam as paradas na ordem de visita (linha reta ilustrativa).
                </p>
              </div>

              <div className="space-y-3 lg:col-span-2">
                <Card className="flex items-center justify-between bg-slate-900 text-white">
                  <div>
                    <p className="text-xs text-slate-400">{activeRoute.vehicleName}</p>
                    <p className="text-lg font-bold">
                      {activeRoute.distanceKm} km · {activeRoute.durationMin} min
                    </p>
                  </div>
                  <Badge tone="blue">
                    Carga: {activeRoute.load}/{activeRoute.capacity}
                  </Badge>
                </Card>

                {stops.length === 0 ? (
                  <Card>
                    <p className="text-sm text-slate-600">Nenhuma parada atribuída a este veículo.</p>
                  </Card>
                ) : (
                  <ol className="space-y-2.5">
                    {stops.map((stop, idx) => {
                      const prevPoint = idx === 0 ? route.origin : stops[idx - 1];
                      const legKm = Math.round(haversineKm(prevPoint, stop) * 10) / 10;

                      return (
                        <li key={stop.id}>
                          <Card className="space-y-2 p-3.5">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex items-start gap-2.5">
                                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
                                  {idx + 1}
                                </span>
                                <div>
                                  <p className="text-sm font-semibold text-slate-900">
                                    {stop.customerName} <span className="font-mono text-xs text-slate-400">{stop.orderCode}</span>
                                  </p>
                                  <p className="text-xs text-slate-600">{stop.address}</p>
                                </div>
                              </div>
                              <StatusBadge delivery={stop} now={now} />
                            </div>

                            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2 text-xs text-slate-500">
                              <span>
                                Janela: <strong>{stop.windowStart}–{stop.windowEnd}</strong> · ~{legKm} km do ponto anterior
                              </span>
                              <a
                                href={googleMapsStopUrl(stop)}
                                target="_blank"
                                rel="noreferrer"
                                className="font-medium text-blue-600 hover:underline"
                              >
                                Navegar ↗
                              </a>
                            </div>
                          </Card>
                        </li>
                      );
                    })}
                  </ol>
                )}
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}