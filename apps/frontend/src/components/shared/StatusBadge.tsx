import type { Delivery } from "@/types/domain";
import { isLate } from "@/utils/kpis";
import { statusLabel } from "@/utils/format";
import { Badge, type Tone } from "@/components/ui/Badge";

const toneByStatus: Record<Delivery["status"], Tone> = {
  waiting_departure: "gray",
  in_progress: "blue",
  completed: "green",
  issue: "orange",
};

export function StatusBadge({ delivery, now }: { delivery: Delivery; now: string }) {
  if (isLate(delivery, now)) {
    return <Badge tone="red">{delivery.status === "issue" ? "Pendência (atrasada)" : "Atrasada"}</Badge>;
  }
  return <Badge tone={toneByStatus[delivery.status]}>{statusLabel[delivery.status]}</Badge>;
}