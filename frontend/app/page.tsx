"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { motion } from "framer-motion";
import { submitIdea } from "@/lib/api";

export default function IntakePage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function launch() {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      const ack = await submitIdea(trimmed);
      router.push(`/pipeline?id=${ack.pipeline_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "intake failed");
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col items-center justify-center px-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-3xl"
      >
        <p className="mb-3 text-center font-mono text-xs uppercase tracking-[0.3em] text-text-secondary">
          drop an idea · the system takes over
        </p>
        <h1 className="mb-10 text-center font-display text-4xl font-semibold tracking-tight text-text-primary">
          What are we building?
        </h1>

        <div className="relative">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) launch();
            }}
            placeholder="I want to build a trading AI that outperforms the market…"
            rows={3}
            className="w-full resize-none rounded-2xl border border-border bg-surface/80 px-6 py-5 text-lg text-text-primary placeholder:text-text-secondary/60 focus:border-active focus:outline-none focus:ring-1 focus:ring-active"
          />
          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              title="Voice capture"
              className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-surface text-active transition-colors hover:border-active"
            >
              <span className="font-mono text-lg">◉</span>
            </button>
            <button
              type="button"
              onClick={launch}
              disabled={busy || !text.trim()}
              className="rounded-full bg-primary px-7 py-3 font-display text-sm font-semibold text-white transition-all hover:bg-active disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy ? "Running…" : "Launch ⏎"}
            </button>
          </div>
        </div>

        {error && (
          <p className="mt-4 text-center font-mono text-xs text-error">
            {error} — is the harness API running?
          </p>
        )}
        <p className="mt-8 text-center font-mono text-[11px] text-text-secondary">
          ⌘/Ctrl + Enter to launch
        </p>
      </motion.div>
    </div>
  );
}
