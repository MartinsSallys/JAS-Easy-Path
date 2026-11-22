import type { RoutePlan } from "@/types/domain";
import type { RoutePlanDTO } from "@/types/dto";
import { USE_MOCK } from "./config";
import { HttpError, http } from "./http";
import { toRoutePlan } from "./mappers";
import { mockRoutesService } from "./mock/mockRoutes";

export interface RoutesService {
  get(): Promise<RoutePlan | null>;
  optimize(): Promise<RoutePlan>;
  share(): Promise<string>;
}

const httpRoutesService: RoutesService = {
  async get() {
    try {
      return toRoutePlan(await http<RoutePlanDTO>("/routes/today"));
    } catch (e) {
      if (e instanceof HttpError && e.status === 404) {
        return null;
      }
      throw e;
    }
  },
  async optimize() {
    return toRoutePlan(await http<RoutePlanDTO>("/routes/today/optimize", { method: "POST" }));
  },
  async share() {
    const result = await http<{ url: string }>("/routes/today/share", { method: "POST" });
    return result.url;
  },
};

export const routesService: RoutesService = USE_MOCK ? mockRoutesService : httpRoutesService;