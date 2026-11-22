import type { RoutePlan } from "@/types/domain";
import type { RoutePlanDTO } from "@/types/dto";
import { USE_MOCK } from "./config";
import { http } from "./http";
import { toRoutePlan } from "./mappers";
import { mockRoutesService } from "./mock/mockRoutes";

export interface RoutesService {
  get(): Promise<RoutePlan>;
  optimize(): Promise<RoutePlan>;
  share(): Promise<string>;
}

const httpRoutesService: RoutesService = {
  async get() {
    return toRoutePlan(await http<RoutePlanDTO>("/routes/today"));
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