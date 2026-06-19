"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { BrainOrb, stateLabel } from "@/components/BrainOrb";
import { api, type Brain, type Pipeline } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

function statusColor(status: string): string {
  if (status === "COMPLETED") return "text-success";
  if (status === "running") return "text-active";
  if (status === "PARTIAL" || status === "NEEDS_OPERATOR") return "text-warning";
  return "text-text-secondary";
}

function PipelinesInner() {
  const params = useSearchParams();
  const focus = params.get("focus");
  const [brains, setBrains] = useState<Brain[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [selected, setSelected] = useState<Pipeline | null>(null);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const [b, p] = await Promise.all([api.brains(), api.pipelines()]);
        if (!active) return;
        setBrains(b);
        setPipelines(p);
        setOnline(true);
        const focusId = focus ?? selected?.pipeline_id ?? p[0]?.pipeline_id;
        if (focusId) {
          const detail = await api.pipeline(focusId).catch(() => null);
          if (active && detail) setSelected(detail);
        }
      } catch {
        if (active) setOnline(false);
      }
    }
    poll();
    const id = setInterval(poll, 1500);
    return () => {
      active = false;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus]);

  return (
    <div className="h-full overflow-y-auto p-8">
      <PageHeader
        title="Pipelines"
        subtitle="Watch the brains think in real time."
        online={online}
      />

        <section className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {brains.map((brain) => (
          <div
            key={brain.brain_id}
            className="glass flex flex-col items-center gap-3 rounded-xl p-5 text-center"
          >
            <BrainOrb state={brain.state} variant="compact" />
            <div>
              <div className="font-display text-sm text-text-primary">{brain.name}</div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-text-secondary">
                {stateLabel(brain.state)}
              </div>
            </div>
          </div>
        ))}
        {brains.length === 0 && (
          <div className="col-span-full font-mono text-sm text-text-secondary">
            No brains registered.
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <div className="space-y-2">
          <h2 className="mb-3 font-display text-sm uppercase tracking-widest text-text-secondary">
            Runs
          </h2>
          {pipelines.map((p) => (
            <button
              key={p.pipeline_id}
              onClick={() => setSelected(p)}
              className={`glass w-full rounded-lg p-4 text-left transition-colors hover:border-primary ${
                selected?.pipeline_id === p.pipeline_id ? "border-primary" : ""
              }`}
            >
              <div className="line-clamp-2 font-body text-sm text-text-primary">{p.idea}</div>
              <div className="mt-2 flex items-center justify-between">
                <span className="font-mono text-[10px] text-text-secondary">
                  {p.pipeline_id.slice(0, 8)}
                </span>
                <span className={`font-mono text-[10px] uppercase ${statusColor(p.status)}`}>
                  {p.status}
                </span>
              </div>
            </button>
          ))}
          {pipelines.length === 0 && (
            <div className="font-mono text-sm text-text-secondary">No runs yet.</div>
          )}
        </div>

        <div className="glass min-h-[300px] rounded-xl p-6">
          {selected ? (
            <motion.div
              key={selected.pipeline_id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <div className="mb-4 flex items-center justify-between">
                <h2 className="font-display text-lg text-text-primary">Pipeline</h2>
                <span className={`font-mono text-xs uppercase ${statusColor(selected.status)}`}>
                  {selected.status}
                </span>
              </div>
              <p className="mb-6 font-body text-text-primary">{selected.idea}</p>

              {selected.history && selected.history.length > 0 && (
                <div className="mb-6">
                  <div className="mb-2 font-mono text-[10px] uppercase tracking-widest text-text-secondary">
                    Brain outputs
                  </div>
                  <div className="space-y-2">
                    {selected.history.map((h, i) => (
                      <div key={i} className="rounded-lg border border-border bg-bg/40 p-3">
                        <span className="font-mono text-xs text-active">{h.brain}</span>
                        <p className="mt-1 font-body text-sm text-text-primary">{h.summary}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selected.output && (
                <div>
                  <div className="mb-2 font-mono text-[10px] uppercase tracking-widest text-text-secondary">
                    Synthesis
                  </div>
                  <pre className="whitespace-pre-wrap rounded-lg border border-primary/30 bg-primary/5 p-4 font-body text-sm text-text-primary">
                    {selected.output}
                  </pre>
                </div>
              )}
            </motion.div>
          ) : (
            <div className="flex h-full items-center justify-center font-mono text-sm text-text-secondary">
              Select a run to inspect it.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function PipelinesPage() {
  return (
    <Suspense fallback={<div className="p-8 font-mono text-text-secondary">Loading…</div>}>
      <PipelinesInner />
    </Suspense>
  );
}
