"use client";

import { useEffect, useRef, useState } from "react";
import type { StreamEventMap } from "./types";

export type StreamHandlers = {
  [K in keyof StreamEventMap]?: (data: StreamEventMap[K]) => void;
} & {
  /** Called on every (re)connect so the caller can resync state it may have missed. */
  onOpen?: () => void;
};

export type StreamStatus = "connecting" | "open" | "reconnecting";

const EVENTS: (keyof StreamEventMap)[] = ["session.updated", "message.appended", "prompt.updated", "entity.updated"];

/** Subscribe to one of the proxied SSE endpoints. EventSource reconnects on its own. */
export function useEventStream(url: string | null, handlers: StreamHandlers): StreamStatus {
  const ref = useRef(handlers);
  const [status, setStatus] = useState<StreamStatus>("connecting");

  useEffect(() => {
    ref.current = handlers;
  });

  useEffect(() => {
    if (!url) return;
    const es = new EventSource(url);
    const listeners = EVENTS.map((type) => {
      const fn = (ev: MessageEvent<string>) => {
        let data: unknown;
        try {
          data = JSON.parse(ev.data);
        } catch {
          return;
        }
        (ref.current[type] as ((d: unknown) => void) | undefined)?.(data);
      };
      es.addEventListener(type, fn as EventListener);
      return [type, fn] as const;
    });
    es.onopen = () => {
      setStatus("open");
      ref.current.onOpen?.();
    };
    es.onerror = () => setStatus("reconnecting");
    return () => {
      listeners.forEach(([type, fn]) => es.removeEventListener(type, fn as EventListener));
      es.close();
    };
  }, [url]);

  return url ? status : "connecting";
}
