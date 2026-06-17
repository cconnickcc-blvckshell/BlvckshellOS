"use client";

import { useEffect, useRef, useState } from "react";
import { PageHeader, Panel, eventTone } from "@/components/ui";
import { getEvents } from "@/lib/api";
import type { ObserverEvent } from "@/lib/types";

export default function ObserverPage() {
  const [events, setEvents] = useState<ObserverEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (paused) return;
    let active = true;
    async function poll() {
      try {
        const data = await getEvents(300);
        if (active) {
          setEvents(data);
          setError(null);
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "unreachable");
      }
    }
    poll();
    const timer = setInterval(poll, 1000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [paused]);

  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events, paused]);

  return (
    <div className="flex h-full flex-col px-10 py-8">
      <div className="flex items-center justify-between">
        <PageHeader
          title="Observer"
          subtitle="Every event in the harness, as it happens. The technical truth."
        />
        <button
          onClick={() => setPaused((p) => !p)}
          className="rounded-full border border-border px-4 py-1.5 font-mono text-xs text-text-secondary hover:text-text-primary"
        >
          {paused ? "▶ resume" : "⏸ pause"}
        </button>
      </div>

      {error && <p className="mb-3 font-mono text-xs text-error">{error}</p>}

      <Panel className="flex-1 overflow-hidden p-0">
        <div className="h-full overflow-y-auto p-4 font-mono text-xs">
          {events.map((event) => (
            <div
              key={event.id}
              className="flex gap-3 border-b border-border/30 py-1.5"
            >
              <span className="w-20 shrink-0 text-text-secondary">
                {new Date(event.timestamp).toLocaleTimeString()}
              </span>
              <span className={`w-44 shrink-0 ${eventTone(event.event_type)}`}>
                {event.event_type}
              </span>
              <span className="w-24 shrink-0 text-active">{event.source}</span>
              <span className="flex-1 truncate text-text-primary/80">
                {event.message}
              </span>
            </div>
          ))}
          {events.length === 0 && !error && (
            <p className="text-text-secondary">Listening for events…</p>
          )}
          <div ref={bottomRef} />
        </div>
      </Panel>
    </div>
  );
}
