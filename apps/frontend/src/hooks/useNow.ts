import { useEffect, useState } from "react";
import { USE_MOCK } from "@/services/config";
import { useAppStore } from "@/store/useAppStore";
import { currentHHmm } from "@/utils/time";

/** Hora "de agora" em HH:mm: simulada no modo demo, real quando conectado à API. */
export function useNow(): string {
  const simulated = useAppStore((state) => state.nowSimulated);
  const [real, setReal] = useState(currentHHmm());

  useEffect(() => {
    const id = setInterval(() => setReal(currentHHmm()), 30_000);
    return () => clearInterval(id);
  }, []);

  return USE_MOCK ? simulated : real;
}