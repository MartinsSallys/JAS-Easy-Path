import { create } from "zustand";
import type { Delivery, IssueReason, NewDelivery, RoutePlan } from "@/types/domain";
import { deliveriesService } from "@/services/deliveriesService";
import { routesService } from "@/services/routeService";

interface AppState {
  deliveries: Delivery[];
  route: RoutePlan | null;
  loading: boolean;
  error: string | null;
  /** Relógio da DEMONSTRAÇÃO (só usado no modo mock). */
  nowSimulated: string;

  refresh: () => Promise<void>;
  addDelivery: (input: NewDelivery) => Promise<void>;
  importDeliveries: (inputs: NewDelivery[]) => Promise<void>;
  removeDelivery: (id: string) => Promise<void>;
  completeDelivery: (id: string, at: string) => Promise<void>;
  reportIssue: (id: string, reason: IssueReason, note: string, at: string) => Promise<void>;
  suggestSequence: () => Promise<void>;
  shareRoute: () => Promise<string | null>;
  resetDemo: () => Promise<void>;
  setNowSimulated: (time: string) => void;
  clearError: () => void;
}

const messageOf = (e: unknown) => (e instanceof Error ? e.message : "Erro inesperado.");

/**
 * O store é só um CACHE para a tela. A fonte dos dados são os services.
 * Padrão de toda ação: chama o service -> recarrega os dados -> a tela atualiza sozinha.
 */
export const useAppStore = create<AppState>()((set) => {
  const reload = async () => {
    const [deliveries, route] = await Promise.all([deliveriesService.list(), routesService.get()]);
    set({ deliveries, route });
  };

  /** Liga "carregando", executa a ação e captura erro sem try/catch. */
  const run = (action: () => Promise<void>) => {
    set({ loading: true, error: null });
    return action()
      .catch((e: unknown) => set({ error: messageOf(e) }))
      .finally(() => set({ loading: false }));
  };

  return {
    deliveries: [],
    route: null,
    loading: false,
    error: null,
    nowSimulated: "19:45",

    refresh: () => run(reload),

    addDelivery: (input) =>
      run(async () => {
        await deliveriesService.create(input);
        await reload();
      }),

    importDeliveries: (inputs) =>
      run(async () => {
        await deliveriesService.createMany(inputs);
        await reload();
      }),

    removeDelivery: (id) =>
      run(async () => {
        await deliveriesService.remove(id);
        await reload();
      }),

    completeDelivery: (id, at) =>
      run(async () => {
        await deliveriesService.complete(id, at);
        await reload();
      }),

    reportIssue: (id, reason, note, at) =>
      run(async () => {
        await deliveriesService.reportIssue(id, reason, note, at);
        await reload();
      }),

    suggestSequence: () =>
      run(async () => {
        await routesService.optimize();
        await reload();
      }),

    shareRoute: () => {
      set({ error: null });
      return routesService.share().catch((e: unknown) => {
        set({ error: messageOf(e) });
        return null;
      });
    },

    resetDemo: () =>
      run(async () => {
        await deliveriesService.resetDemo();
        await reload();
      }),

    setNowSimulated: (time) => set({ nowSimulated: time }),
    clearError: () => set({ error: null }),
  };
});