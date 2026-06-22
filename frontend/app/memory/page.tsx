"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, type MemoryNote, type Opinion } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

type Tab = "opinions" | "notes";

export default function MemoryPage() {
  const [tab, setTab] = useState<Tab>("opinions");
  const [opinions, setOpinions] = useState<Opinion[]>([]);
  const [notes, setNotes] = useState<MemoryNote[]>([]);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const [op, nt] = await Promise.all([api.opinions(), api.memoryNotes()]);
        if (active) {
          setOpinions(op);
          setNotes(nt);
          setOnline(true);
        }
      } catch {
        if (active) setOnline(false);
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
    <div className="h-full overflow-y-auto p-8">
      <PageHeader
        title="Memory"
        subtitle="The system's developing point of view — standing opinions and durable notes."
        online={online}
      />

      <div className="mb-6 flex gap-2 font-mono text-xs uppercase tracking-widest">
        {(["opinions", "notes"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-lg border px-3 py-1.5 transition-colors ${
              tab === t
                ? "border-active/40 bg-active/10 text-active"
                : "border-border text-text-secondary hover:text-text-primary"
            }`}
          >
            {t === "opinions" ? `Opinions (${opinions.length})` : `Notes (${notes.length})`}
          </button>
        ))}
      </div>

      {tab === "opinions" ? (
        opinions.length === 0 ? (
          <div className="glass rounded-xl p-12 text-center font-mono text-sm text-text-secondary">
            No standing opinions yet. They form after enough conversation to warrant a position.
          </div>
        ) : (
          <div className="space-y-3">
            {opinions.map((o, i) => (
              <motion.div
                key={o.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03 }}
                className="glass relative rounded-xl border-l-2 border-l-active p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <span className="font-mono text-[10px] uppercase tracking-widest text-text-secondary">
                      {o.topic}
                    </span>
                    <p className="mt-1 font-body text-text-primary">{o.statement}</p>
                    <p className="mt-2 font-body text-sm text-text-secondary">{o.reasoning}</p>
                  </div>
                  <span className="shrink-0 font-mono text-xs text-active">
                    ✦ {o.confidence.toFixed(2)}
                  </span>
                </div>
                <div className="mt-3 font-mono text-[10px] uppercase tracking-widest text-text-secondary">
                  formed {new Date(o.created_at).toLocaleString()}
                  {o.supersedes ? " · revised from a prior opinion" : ""}
                </div>
              </motion.div>
            ))}
          </div>
        )
      ) : notes.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center font-mono text-sm text-text-secondary">
          No notes yet. They're written after a conversation by the reflection job.
        </div>
      ) : (
        <div className="space-y-3">
          {notes.map((n, i) => (
            <motion.div
              key={n.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              className="glass relative rounded-xl border-l-2 border-l-border p-5"
            >
              <p className="font-body text-text-primary">{n.content}</p>
              {n.topics.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {n.topics.map((t) => (
                    <span
                      key={t}
                      className="rounded-full border border-border px-2 py-0.5 font-mono text-[10px] text-text-secondary"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
              <div className="mt-3 font-mono text-[10px] uppercase tracking-widest text-text-secondary">
                {new Date(n.created_at).toLocaleString()}
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
