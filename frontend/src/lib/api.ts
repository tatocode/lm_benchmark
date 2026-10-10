import type {
  ImageMeta,
  ModelListResult,
  PresetOut,
  ProbeResult,
  TaskConfig,
  TaskDetail,
  TaskSummary,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export function assetUrl(path: string): string {
  if (!path) return path;
  if (/^https?:\/\//.test(path) || path.startsWith("data:")) return path;
  return `${BASE}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<{ ok: boolean }>("/api/health"),

  createTask: (name: string, config: TaskConfig) =>
    request<TaskSummary>("/api/tasks", {
      method: "POST",
      body: JSON.stringify({ name, config }),
    }),

  listTasks: (limit = 100, offset = 0) =>
    request<TaskSummary[]>(`/api/tasks?limit=${limit}&offset=${offset}`),

  getTask: (id: string) => request<TaskDetail>(`/api/tasks/${id}`),

  cancelTask: (id: string) =>
    request<{ ok: boolean }>(`/api/tasks/${id}/cancel`, { method: "POST" }),

  deleteTask: (id: string) =>
    request<{ ok: boolean }>(`/api/tasks/${id}`, { method: "DELETE" }),

  listPresets: () => request<PresetOut[]>("/api/presets"),

  savePreset: (name: string, config: TaskConfig) =>
    request<PresetOut>("/api/presets", {
      method: "POST",
      body: JSON.stringify({ name, config }),
    }),

  deletePreset: (id: string) =>
    request<{ ok: boolean }>(`/api/presets/${id}`, { method: "DELETE" }),

  probe: (config: Pick<TaskConfig, "protocol" | "base_url" | "api_key" | "model">) =>
    request<ProbeResult>("/api/probe", {
      method: "POST",
      body: JSON.stringify(config),
    }),

  listModels: (config: Pick<TaskConfig, "protocol" | "base_url" | "api_key">) =>
    request<ModelListResult>("/api/models", {
      method: "POST",
      body: JSON.stringify(config),
    }),

  samples: () =>
    request<{ text: string[]; vision: string[] }>("/api/samples"),

  listImages: () => request<ImageMeta[]>("/api/images"),

  uploadImage: (name: string, mime: string, dataBase64: string) =>
    request<ImageMeta>("/api/images", {
      method: "POST",
      body: JSON.stringify({ name, mime, data_base64: dataBase64 }),
    }),

  deleteImage: (id: string) =>
    request<{ ok: boolean }>(`/api/images/${id}`, { method: "DELETE" }),
};