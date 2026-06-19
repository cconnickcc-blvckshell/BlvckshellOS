"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import clsx from "clsx";
import { BrainOrb, stateLabel } from "@/components/BrainOrb";
import { createReconnectingObserverStream } from "@/lib/observerStream";
import { api, type AuditEvent, type Brain } from "@/lib/api";

export interface DelegationItem {
  id: string;
  brainId: string;
  capability: string;
  preview: string;
  timestamp: string;
  status: "active" | "done";
}

export interface BrainColumnProps {
  activeDelegation?: string;
  className?: string;
  onDelegation?: (brainId: string | undefined) => void;
  brainOrbRefs?: React.MutableRefObject<Map<string, HTMLElement>>;
}

export function BrainColumn({
  activeDelegation,
  className = "",
  onDelegation,
  brainOrbRefs,
}: BrainColumnProps) {
  const [brains, setBrains] = useState<Brain[]>([]);
  const [delegations, setDelegations] = useState<DelegationItem[]>([]);
  const [doctrineCount, setDoctrineCount] = useState(0);
  const [ledgerCount, setLedgerCount] = useState(0);
  const [pipelineCount, setPipelineCount] = useState(0);
  const [live, setLive] = useState(false);
  const pendingRef = useRef<Map<string, DelegationItem>>(new Map());

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const [b, doctrine, ledger, pipelines] = await Promise.all([
          api.brains(),
          api.doctrine(),
          api.ledger(),
          api.pipelines(),
        ]);
        if (!active) return;
        setBrains(b);
        setDoctrineCount(doctrine.length);
        setLedgerCount(ledger.length);
        setPipelineCount(pipelines.filter((p) => p.status === "running").length);
      } catch {
        /* offline */
      }
    }
    poll();
    const id = setInterval(poll, 2500);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    const es = createReconnectingObserverStream((event: AuditEvent) => {
      if (event.event_type === "AGENT_SPAWNED") {
        const cap = String(event.data.capability ?? "task");
        const brainId = String(
          event.data.target_brain_id ?? event.data.brain_id ?? event.source,
        );
        const item: DelegationItem = {
          id: event.id,
          brainId,
          capability: cap,
          preview: String(event.data.objective ?? event.message).slice(0, 80),
          timestamp: event.timestamp,
          status: "active",
        };
        pendingRef.current.set(String(event.data.agent_call_id ?? event.id), item);
        setDelegations((prev) => [item, ...prev].slice(0, 5));
        if (event.data.target_brain_id) onDelegation?.(String(event.data.target_brain_id));
      }
      if (event.event_type === "AGENT_RETURNED") {
        const key = String(event.data.agent_call_id ?? "");
        const pending = pendingRef.current.get(key);
        if (pending) {
          pending.status = "done";
          pending.preview = String(event.message).slice(0, 80);
          setDelegations((prev) =>
            prev.map((d) => (d.id === pending.id ? { ...pending } : d)),
          );
          pendingRef.current.delete(key);
        }
        onDelegation?.(undefined);
      }
    });
    es.onopen = () => setLive(true);
    es.onerror = () => setLive(false);
    return () => es.close();
  }, [onDelegation]);

  return (
    <div className={clsx("flex h-full flex-col overflow-hidden border-l border-border/60", className)}>
      <div className="shrink-0 border-b border-border px-4 py-3">
        <h2 className="font-display text-sm font-semibold text-text-primary">The Team</h2>
        <p className="font-mono text-[10px] text-text-secondary">specialist brains on standby</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <section>
          <h3 className="mb-3 font-mono text-[10px] uppercase tracking-widest text-text-secondary">
            Active brains
          </h3>
          <div className="space-y-4">
            {brains
              .filter((b) => b.brain_id !== "blvckbot")
              .map((brain) => (
                <motion.div
                  key={brain.brain_id}
                  ref={(el) => {
                    if (el && brainOrbRefs) brainOrbRefs.current.set(brain.brain_id, el);
                  }}
                  animate={
                    activeDelegation === brain.brain_id
                      ? { boxShadow: ["0 0 0px #A855F7", "0 0 16px rgba(168,85,247,0.4)", "0 0 0px #A855F7"] }
                      : {}
                  }
                  transition={{ repeat: activeDelegation === brain.brain_id ? Infinity : 0, duration: 1.2 }}
                  className="glass flex items-center gap-3 rounded-xl p-3"
                >
                  <BrainOrb state={brain.state} size={40} variant="compact" />
                  <div className="min-w-0 flex-1">
                    <div className="font-display text-xs text-text-primary">{brain.name}</div>
                    <div
                      className={clsx(
                        "font-mono text-[10px] uppercase tracking-widest",
                        activeDelegation === brain.brain_id ? "text-active animate-pulse" : "text-text-secondary",
                      )}
                    >
                      {stateLabel(brain.state)}
                    </div>
                  </div>
                </motion.div>
              ))}
            {brains.filter((b) => b.brain_id !== "blvckbot").length === 0 && (
              <p className="font-mono text-xs text-text-secondary">No specialist brains online.</p>
            )}
          </div>
        </section>

        <section>
          <h3 className="mb-2 font-mono text-[10px] uppercase tracking-widest text-text-secondary">
            Delegation feed
          </h3>
          <div className="space-y-2">
            {delegations.map((d) => (
              <motion.div
                key={d.id}
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: d.status === "active" ? 1 : 0.55 }}
                className="rounded-lg border border-border/50 bg-surface/40 px-3 py-2"
              >
                <div className="font-mono text-[10px] text-active">
                  → {d.brainId}: {d.capability}
                </div>
                <p className="mt-1 truncate font-body text-xs text-text-secondary">{d.preview}</p>
                <div className="mt-1 font-mono text-[9px] text-text-secondary">
                  {new Date(d.timestamp).toLocaleTimeString()}
                </div>
              </motion.div>
            ))}
            {delegations.length === 0 && (
              <p className="font-mono text-[10px] text-text-secondary">No recent delegations.</p>
            )}
          </div>
        </section>
      </div>

      <div className="shrink-0 border-t border-border px-4 py-3 font-mono text-[10px] text-text-secondary">
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <span>{doctrineCount} doctrine</span>
          <span>{ledgerCount} ledger</span>
          {pipelineCount > 0 && <span className="text-active">{pipelineCount} pipelines running</span>}
          <span className="flex items-center gap-1">
            <span className={clsx("h-1.5 w-1.5 rounded-full", live ? "bg-success animate-pulse" : "bg-text-secondary")} />
            observer {live ? "live" : "offline"}
          </span>
        </div>
      </div>
    </div>
  );
}
