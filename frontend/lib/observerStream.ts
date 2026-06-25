import type { AuditEvent } from "./api";

const HARNESS_URL = (
  typeof process !== "undefined"
    ? process.env.NEXT_PUBLIC_HARNESS_URL || "http://localhost:8000"
    : "http://localhost:8000"
).replace(/\/+$/, "");

const RECONNECT_MS = 3000;

/** EventSource wrapper that reconnects after errors or close. */
export function createReconnectingObserverStream(
  onEvent: (event: AuditEvent) => void,
): EventSource & { close: () => void } {
  let es: EventSource | null = null;
  let closed = false;
  let timer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    if (closed) return;
    es = new EventSource(`${HARNESS_URL}/observer/stream`);
    es.onmessage = (e) => {
      if (e.data.startsWith(":")) return;
      try {
        onEvent(JSON.parse(e.data) as AuditEvent);
      } catch {
        /* ignore */
      }
    };
    es.onerror = () => {
      es?.close();
      es = null;
      if (!closed) {
        timer = setTimeout(connect, RECONNECT_MS);
      }
    };
  }

  connect();

  return {
    get onopen() {
      return es?.onopen ?? null;
    },
    set onopen(handler: ((ev: Event) => void) | null) {
      if (es) es.onopen = handler;
    },
    get onerror() {
      return es?.onerror ?? null;
    },
    set onerror(handler: ((ev: Event) => void) | null) {
      if (es) es.onerror = handler;
    },
    close() {
      closed = true;
      if (timer) clearTimeout(timer);
      es?.close();
      es = null;
    },
  } as EventSource & { close: () => void };
}
