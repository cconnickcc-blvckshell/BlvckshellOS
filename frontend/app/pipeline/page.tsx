"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { BrainOrb } from "@/components/BrainOrb";
import { Panel, PageHeader, eventTone } from "@/components/ui";
import { getBrains, getPipeline } from "@/lib/api";
import type { BrainInfo, PipelineView } from "@/lib/types";

function PipelineInner() {
  const params = useSearchParams();
  const pipelineId = params.get("id");
  const [brains, setBrains] = useState<BrainInfo[]>([]);
  const [pipeline, setPipeline] = useState<PipelineView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const b = await getBrains();
        if (active) setBrains(b);
        if (pipelineId) {
          const p = await getPipeline(pipelineId);
          if (active) setPipeline(p);
        }
        if (active) setError(null);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "unreachable");
      }
    }
    poll();
    const timer = setInterval(poll, 1500);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [pipelineId]);

  const result = pipeline?.result as
    | { summary?: string; tasks?: { capability: string; brain_id: string; status: string; summary: string }[] }
    | null
    | undefined;

  return (
    <div className="px-10 py-8">
      <PageHeader
        title="Pipeline"
        subtitle={
          pipelineId
            ? `Watching ${pipelineId}`
            : "Live view of the brain federation. Launch an idea from Intake to begin."
        }
      />

      {error && (
        <p className="mb-6 font-mono text-xs text-error">
          {error} — is the harness API running?
        </p>
      )}

      <section className="mb-10 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        {brains.map((brain) => (
          <Panel key={brain.brain_id} className="flex flex-col items-center gap-3 p-6">
            <BrainOrb status={brain.status} label={brain.name} />
            <div className="text-center">
              <p className="font-display text-sm font-semibold text-text-primary">
                {brain.name}
              </p>
              <p className="font-mono text-[10px] uppercase tracking-wider text-text-secondary">
                {brain.status}
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-1">
              {brain.capabilities.slice(0, 3).map((cap) => (
                <span
                  key={cap}
                  className="rounded-full border border-border px-2 py-0.5 font-mono text-[9px] text-text-secondary"
                >
                  {cap}
                </span>
              ))}
            </div>
          </Panel>
        ))}
        {brains.length === 0 && !error && (
          <p className="font-mono text-xs text-text-secondary">Loading brains…</p>
        )}
      </section>

      {result?.summary && (
        <Panel className="mb-8 p-6">
          <h2 className="mb-2 font-display text-lg text-text-primary">Synthesis</h2>
          <p className="whitespace-pre-wrap text-sm text-text-primary/90">
            {result.summary}
          </p>
          <div className="mt-5 grid gap-2">
            {result.tasks?.map((t) => (
              <div
                key={t.capability}
                className="flex items-start gap-3 rounded-lg border border-border bg-background/40 p-3"
              >
                <span className="mt-0.5 font-mono text-[10px] uppercase text-active">
                  {t.brain_id}
                </span>
                <div className="flex-1">
                  <p className="font-mono text-[10px] text-text-secondary">
                    {t.capability} · {t.status}
                  </p>
                  <p className="text-xs text-text-primary/80">{t.summary}</p>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {pipelineId && (
        <Panel className="p-6">
          <h2 className="mb-4 font-display text-lg text-text-primary">
            Message & event flow
          </h2>
          <div className="max-h-[40vh] space-y-1 overflow-y-auto font-mono text-xs">
            {pipeline?.events.map((event) => (
              <div key={event.id} className="flex gap-3">
                <span className="text-text-secondary">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
                <span className={`w-44 shrink-0 ${eventTone(event.event_type)}`}>
                  {event.event_type}
                </span>
                <span className="text-active">{event.source}</span>
                <span className="truncate text-text-primary/70">
                  {event.message}
                </span>
              </div>
            ))}
            {(!pipeline || pipeline.events.length === 0) && (
              <p className="text-text-secondary">Waiting for events…</p>
            )}
          </div>
        </Panel>
      )}
    </div>
  );
}

export default function PipelinePage() {
  return (
    <Suspense
      fallback={
        <div className="px-10 py-8 font-mono text-xs text-text-secondary">
          Loading…
        </div>
      }
    >
      <PipelineInner />
    </Suspense>
  );
}
