"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  api,
  connectObserverStream,
  OUTCOME_BADGE_STYLES,
  type AuditEvent,
  type JudgmentOutcome,
} from "@/lib/api";
import { auditEventToFeedItem, type JudgmentFeedItem } from "@/lib/judgmentEvents";

const MAX_ENTRIES = 20;

function outcomeStyle(outcome: string): string {
  if (outcome in OUTCOME_BADGE_STYLES) {
    return OUTCOME_BADGE_STYLES[outcome as JudgmentOutcome];
  }
  if (outcome === "HOLD" || outcome === "LOGGED") {
    return OUTCOME_BADGE_STYLES.HOLD;
  }
  return "border-border bg-surface/50 text-text-secondary";
}

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function JudgmentActivityFeed({ className = "" }: { className?: string }) {
  const [items, setItems] = useState<JudgmentFeedItem[]>([]);
  const [live, setLive] = useState(false);
  const seen = useRef<Set<string>>(new Set());

  useEffect(() => {
    let active = true;

    api
      .events()
      .then((events) => {
        if (!active) return;
        const seed: JudgmentFeedItem[] = [];
        for (const event of events) {
          const item = auditEventToFeedItem(event);
          if (!item || seen.current.has(item.id)) continue;
          seen.current.add(item.id);
          seed.push(item);
        }
        setItems(seed.slice(0, MAX_ENTRIES));
      })
      .catch(() => {});

    const es = connectObserverStream((event: AuditEvent) => {
      const item = auditEventToFeedItem(event);
      if (!item || seen.current.has(item.id)) return;
      seen.current.add(item.id);
      setItems((prev) => [item, ...prev].slice(0, MAX_ENTRIES));
    });

    es.onopen = () => setLive(true);
    es.onerror = () => setLive(false);

    return () => {
      active = false;
      es.close();
    };
  }, []);

  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-mono text-[10px] uppercase tracking-widest text-text-secondary">
          Judgment activity
        </h3>
        <span className="flex items-center gap-1.5 font-mono text-[10px] text-text-secondary">
          <span
            className={`h-1.5 w-1.5 rounded-full ${live ? "animate-pulse bg-active" : "bg-text-secondary"}`}
          />
          {live ? "live" : "offline"}
        </span>
      </div>

      <div className="glass max-h-48 overflow-y-auto rounded-lg p-2 font-mono text-[11px]">
        <AnimatePresence initial={false}>
          {items.map((item) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-start gap-2 border-b border-border/30 py-1.5 last:border-0"
            >
              <span
                className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] ${outcomeStyle(item.outcome)}`}
              >
                [{item.outcome}]
              </span>
              <span className="shrink-0 text-active">{item.brainId}</span>
              <span className="min-w-0 flex-1 truncate text-text-secondary">
                {item.detail}
                {item.signalCount > 0 && ` · ${item.signalCount} signals consumed`}
              </span>
              <span className="shrink-0 text-text-secondary">{formatTime(item.timestamp)}</span>
            </motion.div>
          ))}
        </AnimatePresence>
        {items.length === 0 && (
          <div className="py-4 text-center text-text-secondary">
            No judgment events yet. Chat with Blvckbot to see activity.
          </div>
        )}
      </div>
    </div>
  );
}
