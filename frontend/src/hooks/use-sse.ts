"use client";

import { useEffect, useRef } from "react";

import type { SSEEvent } from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export function useSSE(
  taskId: string | null,
  onEvent: (event: SSEEvent) => void,
  enabled: boolean,
) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!taskId || !enabled) return;
    let closed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let retry = 0;

    const connect = async () => {
      try {
        const res = await fetch(`${BASE}/api/tasks/${taskId}/events`, {
          cache: "no-store",
          headers: { Accept: "text/event-stream" },
        });
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (!closed) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let idx: number;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            const block = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            const line = block
              .split("\n")
              .find((l) => l.startsWith("data: "));
            if (line) {
              try {
                onEventRef.current(JSON.parse(line.slice(6)));
              } catch {
                /* ignore malformed */
              }
            }
          }
        }
        retry = 0;
      } catch {
        /* connection error, will retry */
      }
      if (closed) return;
      retry += 1;
      timer = setTimeout(connect, Math.min(2000 * retry, 10000));
    };

    connect();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
    };
  }, [taskId, enabled]);
}