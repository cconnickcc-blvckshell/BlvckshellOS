"use client";

import { useEffect, useRef, useState } from "react";
import { api, type AuditEvent } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

const EVENT_COLORS: Record<string, string> = {
  PIPELINE_STARTED: "text-active",
  PIPELINE_COMPLETED: "text-success",
  TASK_STARTED: "text-primary",
  TASK_COMPLETED: "text-success",
  TASK_FAILED: "text-error",
  LLM_CALL: "text-text-secondary",
  TOOL_CALL: "text-warning",
  JUDGMENT_CREATED: "text-active",
  JUDGMENT_UPDATED: "text-active",
  DOCTRINE_PROMOTED: "text-active",
  BRAIN_REGISTERED: "text-success",
  ERROR: "text-error",
};

export default function ObserverPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [online, setOnline] = useState(true);
  const [live, setLive] = useState(false);
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    let active = true;
    api
      .events()
      .then((data) => {
        if (!active) return;
        data.forEach((e) => seen.current.add(e.id));
        setEvents(data);
        setOnline(true);
      })
      .catch(() => active && setOnline(false));

    const es = new EventSource(api.streamUrl());
    es.onopen = () => setLive(true);
    es.onmessage = (msg) => {
      try {
        const event: AuditEvent = JSON.parse(msg.data);
        if (seen.current.has(event.id)) return;
        seen.current.add(event.id);
        setEvents((prev) => [event, ...prev].slice(0, 500));
      } catch {
        /* ignore malformed frames */
      }
    };
    es.onerror = () => setLive(false);

    return () => {
      active = false;
      es.close();
    };
  }, []);

  return (
    <div className="p-8">
      <PageHeader
        title="Observer"
        subtitle="Every event in the harness. The flight recorder."
        online={online}
      />

      <div className="mb-3 flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest">
        <span className={`h-1.5 w-1.5 rounded-full ${live ? "bg-active animate-pulse" : "bg-text-secondary"}`} />
        <span className={live ? "text-active" : "text-text-secondary"}>
          {live ? "streaming" : "polling"}
        </span>
      </div>

      <div className="glass max-h-[75vh] overflow-y-auto rounded-xl p-1 font-mono text-xs">
        {events.map((e) => (
          <div
            key={e.id}
            className="flex items-start gap-3 border-b border-border/40 px-3 py-2 hover:bg-surface/50"
          >
            <span className="shrink-0 text-text-secondary">
              {new Date(e.timestamp).toLocaleTimeString()}
            </span>
            <span className={`w-40 shrink-0 ${EVENT_COLORS[e.event_type] ?? "text-text-primary"}`}>
              {e.event_type}
            </span>
            <span className="w-24 shrink-0 text-active">{e.source}</span>
            <span className="text-text-primary">{e.message}</span>
          </div>
        ))}
        {events.length === 0 && (
          <div className="px-4 py-8 text-center text-text-secondary">
            No events yet. Run a pipeline to see the trace.
          </div>
        )}
      </div>
    </div>
  );
}
