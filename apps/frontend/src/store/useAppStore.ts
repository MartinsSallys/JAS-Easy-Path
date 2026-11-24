import { create } from "zustand";
import type { Delivery, IssueReason, NewDelivery, RoutePlan } from "@/types/domain";
import { deliveriesService } from "@/services/deliveriesService";
import { routesService } from "@/services/routeService";

interface AppState {
  deliveries: Delivery[];
  route: RoutePlan | null;
  initialized: boolean;
  loading: boolean;
  error: string | null;
  /** Relógio da DEMONSTRAÇÃO (só usado no modo mock). */
  nowSimulated: string;

  refresh: () => Promise<void>;
  addDelivery: (input: NewDelivery) => Promise<void>;
  importDeliveries: (inputs: NewDelivery[]) => Promise<void>;
  updateDelivery: (id: string, input: NewDelivery) => Promise<void>;
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

export const useAppStore = create<AppState>()((set) => {
  const reload = async (errorPrefix?: string) => {
    const [deliveriesRes, routeRes] = await Promise.allSettled([
      deliveriesService.list(),
      routesService.get(),
    ]);

    const updates: Partial<AppState> = { initialized: true };
    const errors: string[] = [];

    if (deliveriesRes.status === "fulfilled") {
      updates.deliveries = deliveriesRes.value;
    } else {
      errors.push(messageOf(deliveriesRes.reason));
    }

    if (routeRes.status === "fulfilled") {
      updates.route = routeRes.value;
    } else {
      errors.push(messageOf(routeRes.reason));
    }

    if (errors.length > 0) {
      const detail = errors.join(" ");
      updates.error = errorPrefix ? `${errorPrefix}: ${detail}` : detail;
    }

    set(updates);
  };

  const mutateAndReload = async (mutation: () => Promise<void>) => {
    set({ loading: true, error: null });
    try {
      await mutation();
    } catch (e: unknown) {
      set({ loading: false, error: messageOf(e) });
      throw e;
    }

    await reload("Alteração salva, mas houve falha ao atualizar a lista");
    set({ loading: false });
  };

  return {
    deliveries: [],
    route: null,
    initialized: false,
    loading: false,
    error: null,
    nowSimulated: "19:45",

    refresh: async () => {
      set({ loading: true, error: null });
      try {
        await reload();
      } finally {
        set({ loading: false });
      }
    },

    addDelivery: (input) =>
      mutateAndReload(async () => {
        const created = await deliveriesService.create(input);
        set((s) => ({ deliveries: [...s.deliveries, created] }));
      }),

    importDeliveries: (inputs) =>
      mutateAndReload(async () => {
        const created = await deliveriesService.createMany(inputs);
        set((s) => ({ deliveries: [...s.deliveries, ...created] }));
      }),

    updateDelivery: (id, input) =>
      mutateAndReload(async () => {
        const updated = await deliveriesService.update(id, input);
        set((s) => ({
          deliveries: s.deliveries.map((d) => (d.id === id ? updated : d)),
        }));
      }),

    removeDelivery: (id) =>
      mutateAndReload(async () => {
        await deliveriesService.remove(id);
        set((s) => ({ deliveries: s.deliveries.filter((d) => d.id !== id) }));
      }),

    completeDelivery: (id, at) =>
      mutateAndReload(async () => {
        const updated = await deliveriesService.complete(id, at);
        set((s) => ({
          deliveries: s.deliveries.map((d) => (d.id === id ? updated : d)),
        }));
      }),

    reportIssue: (id, reason, note, at) =>
      mutateAndReload(async () => {
        const updated = await deliveriesService.reportIssue(id, reason, note, at);
        set((s) => ({
          deliveries: s.deliveries.map((d) => (d.id === id ? updated : d)),
        }));
      }),

    suggestSequence: () =>
      mutateAndReload(async () => {
        const optimized = await routesService.optimize();
        set({ route: optimized });
      }),

    shareRoute: async () => {
      set({ error: null });
      try {
        return await routesService.share();
      } catch (e: unknown) {
        set({ error: messageOf(e) });
        return null;
      }
    },

    resetDemo: () =>
      mutateAndReload(async () => {
        await deliveriesService.resetDemo();
      }),

    setNowSimulated: (time) => set({ nowSimulated: time }),
    clearError: () => set({ error: null }),
  };
});