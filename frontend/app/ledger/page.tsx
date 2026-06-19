"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type Judgment } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

function confidenceColor(c: number): string {
  if (c >= 0.8) return "text-success";
  if (c >= 0.5) return "text-warning";
  return "text-error";
}

export default function LedgerPage() {
  const [entries, setEntries] = useState<Judgment[]>([]);
  const [online, setOnline] = useState(true);
  const [brainFilter, setBrainFilter] = useState<string>("");

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const data = await api.ledger(brainFilter || undefined);
        if (active) {
          setEntries(data);
          setOnline(true);
        }
      } catch {
        if (active) setOnline(false);
      }
    }
    poll();
    const id = setInterval(poll, 2500);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [brainFilter]);

  const brains = useMemo(
    () => Array.from(new Set(entries.map((e) => e.brain_id))),
    [entries],
  );

  return (
    <div className="h-full overflow-y-auto p-8">
      <PageHeader
        title="Judgment Ledger"
        subtitle="Every belief, its confidence, and its outcome."
        online={online}
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <FilterChip active={!brainFilter} onClick={() => setBrainFilter("")}>
          all
        </FilterChip>
        {brains.map((b) => (
          <FilterChip key={b} active={brainFilter === b} onClick={() => setBrainFilter(b)}>
            {b}
          </FilterChip>
        ))}
      </div>

      <div className="glass overflow-hidden rounded-xl">
        <table className="w-full text-left text-sm">
          <thead className="table-scan-header border-b border-border font-mono text-[10px] uppercase tracking-widest text-text-secondary">
            <tr>
              <th className="px-4 py-3">Brain</th>
              <th className="px-4 py-3">Belief</th>
              <th className="px-4 py-3">Conf.</th>
              <th className="px-4 py-3">Outcome</th>
              <th className="px-4 py-3">State</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-b border-border/50 hover:bg-surface/50">
                <td className="px-4 py-3 font-mono text-xs text-active">{e.brain_id}</td>
                <td className="px-4 py-3 font-body text-text-primary">{e.belief}</td>
                <td className={`px-4 py-3 font-mono ${confidenceColor(e.confidence)}`}>
                  {e.confidence.toFixed(2)}
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {e.was_correct === null ? (
                    <span className="text-text-secondary">pending</span>
                  ) : e.was_correct ? (
                    <span className="text-success">correct</span>
                  ) : (
                    <span className="text-error">incorrect</span>
                  )}
                </td>
                <td className="px-4 py-3 font-mono text-xs">
                  {e.doctrine_promoted ? (
                    <span className="text-active">doctrine</span>
                  ) : e.retired ? (
                    <span className="text-text-secondary">retired</span>
                  ) : (
                    <span className="text-text-secondary">active</span>
                  )}
                </td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center font-mono text-text-secondary">
                  No judgments yet. Run a pipeline.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-3 py-1 font-mono text-xs transition-colors ${
        active
          ? "border-primary bg-primary/15 text-text-primary"
          : "border-border text-text-secondary hover:border-primary"
      }`}
    >
      {children}
    </button>
  );
}
