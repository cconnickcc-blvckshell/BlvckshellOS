"use client";

import { useEffect, useState } from "react";
import { ConfidenceBar, PageHeader, Panel } from "@/components/ui";
import { getDoctrine } from "@/lib/api";
import type { DoctrineRecord } from "@/lib/types";

export default function DoctrinePage() {
  const [records, setRecords] = useState<DoctrineRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await getDoctrine();
        if (active) {
          setRecords(data);
          setError(null);
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "unreachable");
      }
    }
    load();
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="px-10 py-8">
      <PageHeader
        title="Doctrine"
        subtitle="Validated beliefs, promoted from the ledger. The system's accumulated wisdom — append-only, never deleted."
      />

      {error && <p className="mb-4 font-mono text-xs text-error">{error}</p>}

      <div className="grid gap-3">
        {records.map((record) => (
          <Panel key={record.id} className="flex items-start gap-4 p-5">
            <span className="mt-1 text-lg text-active">✦</span>
            <div className="flex-1">
              <p className="text-text-primary">{record.belief}</p>
              <div className="mt-2 flex items-center gap-4">
                <span className="font-mono text-[11px] text-text-secondary">
                  {record.brain_id}
                </span>
                <ConfidenceBar value={record.confidence} />
              </div>
            </div>
          </Panel>
        ))}
        {records.length === 0 && !error && (
          <p className="font-mono text-xs text-text-secondary">
            No doctrine yet. Seed founding doctrine with{" "}
            <code className="text-active">blvckshell-seed</code>, or promote a
            judgment.
          </p>
        )}
      </div>
    </div>
  );
}
