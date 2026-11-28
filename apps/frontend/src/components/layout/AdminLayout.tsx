import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  MapPinned,
  Menu,
  PackageSearch,
  Smartphone,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { USE_MOCK } from "@/services/config";
import { useAppStore } from "@/store/useAppStore";

const links = [
  { to: "/", label: "Resumo do dia", icon: LayoutDashboard, end: true },
  { to: "/entregas", label: "Entregas", icon: PackageSearch, end: false },
  { to: "/rota", label: "Rota", icon: MapPinned, end: false },
];

export function AdminLayout() {
  const [open, setOpen] = useState(false);
  const loading = useAppStore((s) => s.loading);
  const error = useAppStore((s) => s.error);
  const clearError = useAppStore((s) => s.clearError);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 md:flex">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-800/80 bg-slate-950 px-4 py-2.5 text-white md:hidden">
        <NavLink
          to="/"
          onClick={() => setOpen(false)}
          className="flex items-center gap-2.5"
        >
          <img
            src="/logo.png"
            alt="Logo JAS Easy Path"
            className="h-9 w-9 rounded-xl object-contain"
          />
          <div className="leading-tight">
            <span className="block text-sm font-bold tracking-tight">JAS Easy Path</span>
            <span className="block text-[11px] text-slate-400">Roteirização</span>
          </div>
        </NavLink>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? "Fechar menu" : "Abrir menu"}
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg hover:bg-slate-800"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>

      <aside
        className={cn(
          "w-full shrink-0 border-b border-slate-800 bg-slate-950 p-4 text-slate-100 md:sticky md:top-0 md:flex md:h-screen md:w-64 md:flex-col md:justify-between md:border-b-0 md:border-r",
          open ? "block" : "hidden",
        )}
      >
        <div className="space-y-6">
          <div className="hidden items-center gap-3 md:flex">
            <img
              src="/logo.png"
              alt="Logo JAS Easy Path"
              className="h-11 w-11 shrink-0 rounded-xl object-contain"
            />
            <div className="min-w-0">
              <h1 className="truncate text-base font-bold tracking-tight text-white">
                JAS Easy Path
              </h1>
              <p className="truncate text-xs text-slate-400">Roteirização de entregas</p>
            </div>
          </div>

          <nav aria-label="Menu principal" className="space-y-1">
            {links.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm transition-colors",
                    isActive
                      ? "bg-blue-600 font-semibold text-white"
                      : "text-slate-300 hover:bg-slate-900 hover:text-white",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </NavLink>
            ))}

            <div className="pt-3">
              <NavLink
                to="/entregador"
                onClick={() => setOpen(false)}
                className="flex min-h-11 items-center gap-3 rounded-lg border border-slate-800 px-3 text-sm text-slate-300 hover:bg-slate-900 hover:text-white"
              >
                <Smartphone className="h-4 w-4 shrink-0 text-emerald-400" />
                Visão do entregador
              </NavLink>
            </div>
          </nav>
        </div>

        <div className="mt-6 border-t border-slate-800 pt-4 text-xs text-slate-400">
          {USE_MOCK ? (
            <span className="inline-flex items-center gap-1.5 text-amber-300">
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              Protótipo: dados fictícios
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Conectado à API
            </span>
          )}
        </div>
      </aside>

      <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">
        <div className="mx-auto max-w-6xl space-y-4">
          {loading ? (
            <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-medium text-blue-800">
              Sincronizando dados...
            </div>
          ) : null}

          {error ? (
            <div
              role="alert"
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              <span className="min-w-0 flex-1 break-words">{error}</span>
              <button
                type="button"
                onClick={clearError}
                className="shrink-0 text-xs font-semibold underline hover:text-red-950"
              >
                Fechar
              </button>
            </div>
          ) : null}

          <Outlet />
        </div>
      </main>
    </div>
  );
}