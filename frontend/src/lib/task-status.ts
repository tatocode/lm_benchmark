import type { TKey } from "@/lib/i18n";
import type { TaskStatus } from "@/lib/types";

export const TERMINAL_STATUSES: readonly TaskStatus[] = [
  "done",
  "failed",
  "cancelled",
  "interrupted",
];

export const STATUS_META: Record<
  TaskStatus,
  {
    labelKey: TKey;
    variant: "success" | "warning" | "destructive" | "secondary";
  }
> = {
  pending: { labelKey: "common.status.pending", variant: "secondary" },
  running: { labelKey: "common.status.running", variant: "warning" },
  done: { labelKey: "common.status.done", variant: "success" },
  failed: { labelKey: "common.status.failed", variant: "destructive" },
  cancelled: { labelKey: "common.status.cancelled", variant: "secondary" },
  interrupted: { labelKey: "common.status.interrupted", variant: "secondary" },
};
