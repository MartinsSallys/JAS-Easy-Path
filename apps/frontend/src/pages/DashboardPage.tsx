import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { RotateCcw } from "lucide-react";
import { useNow } from "@/hooks/useNow";
import { USE_MOCK } from "@/services/config";
import { useAppStore } from "@/store/useAppStore";
import { computeKpis } from "@/utils/kpis";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

export default function DashboardPage() {
  const deliveries = useAppStore((s) => s.deliveries);
  const route = useAppStore((s) => s.route);
  const nowSimulated = useAppStore((s) => s.nowSimulated);
  const setNowSimulated = useAppStore((s) => s.setNowSimulated);
  const resetDemo = useAppStore((s) => s.resetDemo);
  const now = useNow();

  const kpis = computeKpis(deliveries, now);
  const recordedTotal = kpis.completed + kpis.issues;

  const chartData = [
    { name: "Aguardando", value: kpis.waiting, color: "#94a3b8" },
    { name: "Em andamento", value: kpis.inProgress, color: "#2563eb" },
    { name: "Concluídas", value: kpis.completed, color: "#16a34a" },
    { name: "Pendências", value: kpis.issues, color: "#f97316" },
  ];

  const metrics = [
    { label: "Total do dia", value: kpis.total, accent: "text-slate-900" },
    { label: "Concluídas", value: kpis.completed, accent: "text-green-600" },
    { label: "Em andamento", value: kpis.inProgress, accent: "text-blue-600" },
    { label: "Aguardando saída", value: kpis.waiting, accent: "text-slate-600" },
    { label: "Pendências", value: kpis.issues, accent: "text-orange-600" },
    { label: "Atrasadas", value: kpis.late, accent: "text-red-600" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Resumo do dia</h1>
          <p className="text-sm text-slate-500">Horário de referência: {now}</p>
        </div>

        {USE_MOCK ? (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-200 bg-amber-50/80 px-3 py-2">
            <label htmlFor="sim-clock" className="text-xs font-medium text-amber-900">
              Hora da demonstração:
            </label>
            <input
              id="sim-clock"
              type="time"
              value={nowSimulated}
              onChange={(e) => setNowSimulated(e.target.value)}
              className="rounded-lg border border-amber-300 bg-white px-2 py-1 text-xs font-medium text-slate-800"
            />
            <Button
              variant="secondary"
              onClick={() => {
                void resetDemo().catch(() => {});
              }}
              className="min-h-9 px-3 py-1 text-xs"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Restaurar demonstração
            </Button>
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {metrics.map((m) => (
          <Card key={m.label} className="p-4">
            <p className="text-xs font-medium text-slate-500">{m.label}</p>
            <p className={`mt-1 text-2xl font-bold ${m.accent}`}>{m.value}</p>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">Progresso das entregas</h2>
            <span className="text-sm font-bold text-blue-600">{kpis.completionRate}%</span>
          </div>

          <div
            role="progressbar"
            aria-valuenow={kpis.completionRate}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Taxa de conclusão das entregas"
            className="h-3 w-full overflow-hidden rounded-full bg-slate-100"
          >
            <div
              className="h-full rounded-full bg-green-600 transition-all"
              style={{ width: `${kpis.completionRate}%` }}
            />
          </div>

          {route ? (
            <div className="grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 text-sm sm:grid-cols-4">
              <div>
                <p className="text-xs text-slate-500">Veículos ativos</p>
                <p className="font-semibold text-slate-900">{route.routes.length}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Distância estimada</p>
                <p className="font-semibold text-slate-900">{route.totalDistanceKm} km</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Duração estimada</p>
                <p className="font-semibold text-slate-900">{route.totalDurationMin} min</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Baixas registradas</p>
                <p className="font-semibold text-slate-900">
                  {recordedTotal}/{kpis.total}
                </p>
              </div>
            </div>
          ) : null}

          <p className="text-xs text-slate-400">
            {USE_MOCK
              ? "Distância e duração são estimativas calculadas em linha reta (modo demonstração); baixas refletem o status registrado."
              : "Distância e duração são estimativas calculadas pelo motor de otimização; baixas refletem os registros gravados pelo entregador."}
          </p>
        </Card>

        <Card className="space-y-3">
          <h2 className="text-base font-semibold text-slate-900">Distribuição por status</h2>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                  {chartData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}