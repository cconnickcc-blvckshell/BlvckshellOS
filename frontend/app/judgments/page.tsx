"use client";

import { useEffect, useMemo, useState } from "react";
import { ConfidenceBar, PageHeader, Panel } from "@/components/ui";
import { getJudgments } from "@/lib/api";
import type { JudgmentEntry } from "@/lib/types";

export default function JudgmentsPage() {
  const [entries, setEntries] = useState<JudgmentEntry[]>([]);
  const [brainFilter, setBrainFilter] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await getJudgments();
        if (active) {
          setEntries(data);
          setError(null);
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "unreachable");
      }
    }
    load();
    const timer = setInterval(load, 3000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  const brains = useMemo(
    () => Array.from(new Set(entries.map((e) => e.brain_id))).sort(),
    [entries],
  );
  const filtered = entries.filter(
    (e) => brainFilter === "all" || e.brain_id === brainFilter,
  );

  return (
    <div className="px-10 py-8">
      <PageHeader
        title="Judgment Ledger"
        subtitle="Every belief, with its confidence and outcome. The substrate the system learns from."
      />

      <div className="mb-5 flex items-center gap-2">
        <span className="font-mono text-xs text-text-secondary">brain:</span>
        {["all", ...brains].map((b) => (
          <button
            key={b}
            onClick={() => setBrainFilter(b)}
            className={`rounded-full px-3 py-1 font-mono text-xs transition-colors ${
              brainFilter === b
                ? "bg-primary/30 text-text-primary"
                : "border border-border text-text-secondary hover:text-text-primary"
            }`}
          >
            {b}
          </button>
        ))}
      </div>

      {error && <p className="mb-4 font-mono text-xs text-error">{error}</p>}

      <Panel className="overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border text-text-secondary">
              <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-wider">Brain</th>
              <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-wider">Belief</th>
              <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-wider">Confidence</th>
              <th className="px-4 py-3 font-mono text-[11px] uppercase tracking-wider">Outcome</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((entry) => (
              <tr key={entry.id} className="border-b border-border/50 align-top">
                <td className="px-4 py-3 font-mono text-xs text-active">
                  {entry.brain_id}
                  {entry.doctrine_promoted && (
                    <span className="ml-1 text-success" title="Promoted to doctrine">✦</span>
                  )}
                </td>
                <td className="px-4 py-3 text-text-primary/90">{entry.belief}</td>
                <td className="px-4 py-3">
                  <ConfidenceBar value={entry.confidence} />
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {entry.was_correct === null ? (
                    <span className="text-text-secondary">pending</span>
                  ) : entry.was_correct ? (
                    <span className="text-success">correct</span>
                  ) : (
                    <span className="text-error">incorrect</span>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center font-mono text-xs text-text-secondary">
                  No judgments yet. Launch a pipeline from Intake.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
