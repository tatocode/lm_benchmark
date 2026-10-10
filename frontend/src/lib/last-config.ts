import type { TaskConfig } from "@/lib/types";

const LAST_CONFIG_KEY = "lmbench.lastConfig";

export function saveLastConfig(config: TaskConfig): void {
  try {
    window.localStorage.setItem(
      LAST_CONFIG_KEY,
      JSON.stringify({ ...config, api_key: "" }),
    );
  } catch {
    /* ignore */
  }
}

export function loadLastConfig(): Partial<TaskConfig> | null {
  try {
    const raw = window.localStorage.getItem(LAST_CONFIG_KEY);
    return raw ? (JSON.parse(raw) as Partial<TaskConfig>) : null;
  } catch {
    return null;
  }
}

export function removeLastConfig(): void {
  try {
    window.localStorage.removeItem(LAST_CONFIG_KEY);
  } catch {
    /* ignore */
  }
}