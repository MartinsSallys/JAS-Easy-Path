import { cn } from "@/lib/utils";

/** Classe comum de input/select/textarea. Fica vermelha quando há erro. */
export const inputClass = (hasError: boolean) =>
  cn(
    "w-full min-h-11 rounded-lg border bg-white px-3 py-2 text-sm text-slate-900",
    "focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-blue-600",
    hasError ? "border-red-500" : "border-slate-300",
  );