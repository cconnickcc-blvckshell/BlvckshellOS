"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, type Judgment } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

export default function DoctrinePage() {
  const [entries, setEntries] = useState<Judgment[]>([]);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const data = await api.doctrine();
        if (active) {
          setEntries(data);
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
    <div className="p-8">
      <PageHeader
        title="Doctrine"
        subtitle="Validated beliefs. The system's accumulated wisdom — append-only."
        online={online}
      />

      {entries.length === 0 ? (
        <div className="glass rounded-xl p-12 text-center font-mono text-sm text-text-secondary">
          No doctrine yet. Beliefs are promoted here once proven correct.
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((e, i) => (
            <motion.div
              key={e.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              className="glass relative rounded-xl border-l-2 border-l-active p-5"
            >
              <div className="flex items-start justify-between gap-4">
                <p className="font-body text-text-primary">{e.belief}</p>
                <span className="shrink-0 font-mono text-xs text-active">
                  ✦ {e.confidence.toFixed(2)}
                </span>
              </div>
              <div className="mt-3 font-mono text-[10px] uppercase tracking-widest text-text-secondary">
                {e.brain_id} · promoted {new Date(e.timestamp).toLocaleString()}
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
