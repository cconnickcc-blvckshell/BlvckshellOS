"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import { BrainOrb, stateLabel } from "@/components/BrainOrb";
import { JudgmentActivityFeed } from "@/components/JudgmentActivityFeed";
import {
  api,
  connectObserverStream,
  type AuditEvent,
  type Brain,
  type Judgment,
  type Pipeline,
} from "@/lib/api";

type Tab = "brains" | "ledger" | "doctrine" | "observer";

const TABS: { id: Tab; label: string }[] = [
  { id: "brains", label: "Brains" },
  { id: "ledger", label: "Ledger" },
  { id: "doctrine", label: "Doctrine" },
  { id: "observer", label: "Observer" },
];

const OBSERVER_COLORS: Record<string, string> = {
  JUDGMENT_GUARD_BLOCKED: "text-error",
  DOCTRINE_PROMOTED: "text-success animate-pulse",
  OUTCOME_RECORDED: "text-blue-400",
  AGENT_SPAWNED: "text-primary",
  AGENT_RETURNED: "text-primary",
};

function confidenceColor(c: number): string {
  if (c >= 0.8) return "text-success";
  if (c >= 0.5) return "text-warning";
  return "text-error";
}

function isRecentlyPromoted(ts: string): boolean {
  const promoted = new Date(ts).getTime();
  return Date.now() - promoted < 24 * 60 * 60 * 1000;
}

function BrainsTab() {
  const [brains, setBrains] = useState<Brain[]>([]);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [activePipeline, setActivePipeline] = useState<Pipeline | null>(null);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const [b, p] = await Promise.all([api.brains(), api.pipelines()]);
        if (!active) return;
        setBrains(b);
        setPipelines(p);
        const latest = p[0];
        if (latest) {
          const detail = await api.pipeline(latest.pipeline_id).catch(() => latest);
          if (active) setActivePipeline(detail);
        }
      } catch {
        /* harness offline */
      }
    }
    poll();
    const id = setInterval(poll, 2000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="space-y-6">
      <section>
        <h3 className="mb-3 font-mono text-[10px] uppercase tracking-widest text-text-secondary">
          Live brain states
        </h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {brains.map((brain) => (
            <div
              key={brain.brain_id}
              className="glass flex flex-col items-center gap-2 rounded-xl p-4 text-center"
            >
              <BrainOrb state={brain.state} size={48} />
              <div className="font-display text-xs text-text-primary">{brain.name}</div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-text-secondary">
                {stateLabel(brain.state)}
              </div>
            </div>
          ))}
          {brains.length === 0 && (
            <div className="col-span-full font-mono text-sm text-text-secondary">
              No brains registered.
            </div>
          )}
        </div>
      </section>

      {activePipeline && (
        <section className="glass rounded-xl p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="font-mono text-[10px] uppercase tracking-widest text-text-secondary">
              Latest pipeline
            </h3>
            <span className="font-mono text-[10px] text-active">{activePipeline.status}</span>
          </div>
          <p className="mb-3 line-clamp-2 font-body text-sm text-text-primary">
            {activePipeline.idea}
          </p>
          {activePipeline.output && (
            <pre className="max-h-32 overflow-y-auto whitespace-pre-wrap rounded-lg border border-border/50 bg-bg/40 p-3 font-body text-xs text-text-primary">
              {activePipeline.output}
            </pre>
          )}
          {pipelines.length > 1 && (
            <Link
              href="/pipelines"
              className="mt-2 inline-block font-mono text-[10px] text-active hover:underline"
            >
              View all pipelines →
            </Link>
          )}
        </section>
      )}

      <JudgmentActivityFeed />
    </div>
  );
}

function LedgerTab() {
  const [entries, setEntries] = useState<Judgment[]>([]);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const data = await api.ledger();
        if (active) setEntries(data.slice(0, 20));
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

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-mono text-[10px] uppercase tracking-widest text-text-secondary">
          Recent judgments
        </h3>
        <Link href="/ledger" className="font-mono text-[10px] text-active hover:underline">
          Full ledger →
        </Link>
      </div>
      <div className="glass overflow-hidden rounded-xl">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-border font-mono text-[10px] uppercase tracking-widest text-text-secondary">
            <tr>
              <th className="px-3 py-2">Brain</th>
              <th className="px-3 py-2">Belief</th>
              <th className="px-3 py-2">Conf.</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-border/40 hover:bg-surface/40">
                <td className="px-3 py-2 font-mono text-active">{e.brain_id}</td>
                <td className="max-w-[200px] truncate px-3 py-2 font-body text-text-primary">
                  {e.belief}
                </td>
                <td className={`px-3 py-2 font-mono ${confidenceColor(e.confidence)}`}>
                  {e.confidence.toFixed(2)}
                </td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr>
                <td colSpan={3} className="px-3 py-6 text-center font-mono text-text-secondary">
                  No judgments yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DoctrineTab() {
  const [entries, setEntries] = useState<Judgment[]>([]);
  const [recentPromotions, setRecentPromotions] = useState(0);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const data = await api.doctrine();
        if (!active) return;
        setEntries(data);
        setRecentPromotions(data.filter((e) => isRecentlyPromoted(e.timestamp)).length);
      } catch {
        /* offline */
      }
    }
    poll();
    const id = setInterval(poll, 4000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-mono text-[10px] uppercase tracking-widest text-text-secondary">
          Promoted beliefs
          {recentPromotions > 0 && (
            <span className="ml-2 text-success">· {recentPromotions} recent</span>
          )}
        </h3>
        <Link href="/doctrine" className="font-mono text-[10px] text-active hover:underline">
          Full doctrine →
        </Link>
      </div>
      <div className="max-h-[50vh] space-y-2 overflow-y-auto">
        {entries.slice(0, 15).map((e) => {
          const recent = isRecentlyPromoted(e.timestamp);
          return (
            <motion.div
              key={e.id}
              animate={recent ? { boxShadow: ["0 0 0px rgba(34,197,94,0)", "0 0 12px rgba(34,197,94,0.35)", "0 0 0px rgba(34,197,94,0)"] } : {}}
              transition={recent ? { duration: 2, repeat: Infinity } : {}}
              className={clsx(
                "glass rounded-lg border-l-2 p-3",
                recent ? "border-l-success" : "border-l-active",
              )}
            >
              <p className="line-clamp-2 font-body text-sm text-text-primary">{e.belief}</p>
              <div className="mt-1 font-mono text-[10px] text-text-secondary">
                {e.brain_id} · {e.confidence.toFixed(2)}
              </div>
            </motion.div>
          );
        })}
        {entries.length === 0 && (
          <div className="glass rounded-xl p-8 text-center font-mono text-sm text-text-secondary">
            No doctrine yet.
          </div>
        )}
      </div>
    </div>
  );
}

function ObserverTab() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [live, setLive] = useState(false);
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    let active = true;
    api
      .events()
      .then((data) => {
        if (!active) return;
        data.forEach((e) => seen.current.add(e.id));
        setEvents(data.slice(0, 100));
      })
      .catch(() => {});

    const es = connectObserverStream((event) => {
      if (seen.current.has(event.id)) return;
      seen.current.add(event.id);
      setEvents((prev) => [event, ...prev].slice(0, 200));
    });
    es.onopen = () => setLive(true);
    es.onerror = () => setLive(false);

    return () => {
      active = false;
      es.close();
    };
  }, []);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-mono text-[10px] uppercase tracking-widest text-text-secondary">
            Live audit stream
          </h3>
          <span
            className={`h-1.5 w-1.5 rounded-full ${live ? "animate-pulse bg-active" : "bg-text-secondary"}`}
          />
        </div>
        <Link href="/observer" className="font-mono text-[10px] text-active hover:underline">
          Full observer →
        </Link>
      </div>
      <div className="glass max-h-[55vh] overflow-y-auto rounded-xl p-1 font-mono text-[11px]">
        {events.map((e) => (
          <div
            key={e.id}
            className="flex items-start gap-2 border-b border-border/30 px-2 py-1.5 hover:bg-surface/40"
          >
            <span className="shrink-0 text-text-secondary">
              {new Date(e.timestamp).toLocaleTimeString()}
            </span>
            <span
              className={clsx(
                "w-36 shrink-0 truncate",
                OBSERVER_COLORS[e.event_type] ?? "text-text-secondary",
              )}
            >
              {e.event_type}
            </span>
            <span className="w-20 shrink-0 text-active">{e.source}</span>
            <span className="min-w-0 flex-1 truncate text-text-primary">{e.message}</span>
          </div>
        ))}
        {events.length === 0 && (
          <div className="px-4 py-8 text-center text-text-secondary">No events yet.</div>
        )}
      </div>
    </div>
  );
}

export function CommandCenter({ className = "" }: { className?: string }) {
  const [tab, setTab] = useState<Tab>("brains");

  return (
    <div className={clsx("flex h-full flex-col overflow-hidden", className)}>
      <div className="shrink-0 border-b border-border px-4 py-3">
        <h2 className="font-display text-sm font-semibold text-text-primary">Command Center</h2>
        <p className="font-mono text-[10px] text-text-secondary">watch the system work</p>
      </div>

      <div className="flex shrink-0 gap-1 border-b border-border px-4 py-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={clsx(
              "rounded-lg px-3 py-1.5 font-mono text-xs transition-colors",
              tab === t.id
                ? "bg-primary/20 text-text-primary"
                : "text-text-secondary hover:bg-surface hover:text-text-primary",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
          >
            {tab === "brains" && <BrainsTab />}
            {tab === "ledger" && <LedgerTab />}
            {tab === "doctrine" && <DoctrineTab />}
            {tab === "observer" && <ObserverTab />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
