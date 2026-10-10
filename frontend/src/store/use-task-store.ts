"use client";

import { create } from "zustand";

import type {
  Analysis,
  RecordOut,
  Snapshot,
  SSEEvent,
  StepSummary,
  TaskStatus,
} from "@/lib/types";

interface ThroughputPoint {
  t: number;
  v: number;
}

interface TaskLiveState {
  taskId: string | null;
  status: TaskStatus;
  error: string;
  records: RecordOut[];
  snapshot: Snapshot | null;
  steps: StepSummary[];
  throughput: ThroughputPoint[];
  analysis: Partial<Analysis>;
  autoStopReason: string;
  reset: (taskId: string) => void;
  mergeInitial: (state: {
    status: TaskStatus;
    error?: string;
    records?: RecordOut[];
    snapshot?: Snapshot | null;
    steps?: StepSummary[];
    analysis?: Partial<Analysis>;
  }) => void;
  setStatus: (status: TaskStatus, error?: string) => void;
  apply: (event: SSEEvent) => void;
}

export const useTaskStore = create<TaskLiveState>((set, get) => ({
  taskId: null,
  status: "pending",
  error: "",
  records: [],
  snapshot: null,
  steps: [],
  throughput: [],
  analysis: {},
  autoStopReason: "",

  reset: (taskId) =>
    set({
      taskId,
      status: "pending",
      error: "",
      records: [],
      snapshot: null,
      steps: [],
      throughput: [],
      analysis: {},
      autoStopReason: "",
    }),

  mergeInitial: (state) => {
    const throughput = get().throughput;
    const snap = state.snapshot;
    if (snap && snap.elapsed_s && !throughput.length) {
      throughput.push({ t: snap.elapsed_s, v: snap.window_tps ?? 0 });
    }
    set({
      status: state.status,
      error: state.error ?? "",
      records: state.records ?? [],
      snapshot: state.snapshot ?? null,
      steps: state.steps ?? [],
      analysis: state.analysis ?? {},
      autoStopReason: "",
      throughput: [...throughput],
    });
  },

  setStatus: (status, error = "") => set({ status, error }),

  apply: (event) => {
    const s = get();
    switch (event.type) {
      case "status":
        set({ status: event.data.status, error: event.data.error ?? "" });
        break;
      case "records":
        set({ records: event.data });
        break;
      case "record":
        set({ records: [...s.records, event.data] });
        break;
      case "steps":
        set({ steps: event.data });
        break;
      case "analysis":
        set({ analysis: event.data });
        break;
      case "auto_stop":
        set({ autoStopReason: event.data.reason });
        break;
      case "snapshot": {
        const snap = event.data;
        const throughput = s.throughput;
        if (snap.elapsed_s) {
          const last = throughput[throughput.length - 1];
          const delta = last ? snap.elapsed_s - last.t : snap.elapsed_s;
          if (!last || delta >= 0.4 || snap.completed >= (snap.planned || 0)) {
            throughput.push({
              t: snap.elapsed_s,
              v: snap.window_tps ?? snap.throughput_tps ?? 0,
            });
          }
        }
        set({ snapshot: snap, throughput: [...throughput] });
        break;
      }
    }
  },
}));