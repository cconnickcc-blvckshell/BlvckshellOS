"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { api, formatApiError } from "@/lib/api";

export default function IntakePage() {
  const router = useRouter();
  const [idea, setIdea] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  async function submit() {
    const text = idea.trim();
    if (!text) return;
    setStatus("sending");
    setErrorMessage(null);
    try {
      const res = await api.submitIdea(text, false);
      setStatus("sent");
      setTimeout(() => router.push(`/pipelines?focus=${res.pipeline_id}`), 600);
    } catch (err) {
      setStatus("error");
      setErrorMessage(formatApiError(err, "Could not reach the harness."));
    }
  }

  function toggleVoice() {
    const SR =
      (typeof window !== "undefined" &&
        ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)) ||
      null;
    if (!SR) {
      setStatus("error");
      setErrorMessage("Voice input is not available in this browser.");
      return;
    }
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }
    const recognition = new SR();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.onresult = (e: any) => {
      const transcript = Array.from(e.results)
        .map((r: any) => r[0].transcript)
        .join(" ");
      setIdea(transcript);
    };
    recognition.onend = () => setListening(false);
    recognition.start();
    recognitionRef.current = recognition;
    setListening(true);
  }

  return (
    <div className="flex h-full min-h-0 flex-col items-center justify-center overflow-y-auto px-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-3xl"
      >
        <h1 className="mb-2 text-center font-display text-3xl font-semibold tracking-tight">
          Drop an idea.
        </h1>
        <p className="mb-10 text-center font-body text-sm text-text-secondary">
          Launch a full pipeline — the orchestrator decomposes, routes, and executes.
        </p>

        <div className="glass relative rounded-2xl p-2 shadow-2xl shadow-primary/10">
          <textarea
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
            }}
            placeholder="I want to build a trading AI that outperforms the market…"
            rows={3}
            className="w-full resize-none bg-transparent px-5 py-4 font-body text-lg text-text-primary outline-none placeholder:text-text-secondary"
          />
          <div className="flex items-center justify-between px-4 pb-3">
            <button
              onClick={toggleVoice}
              className={`flex items-center gap-2 rounded-full border px-4 py-2 font-mono text-xs transition-colors ${
                listening
                  ? "border-active bg-active/20 text-active"
                  : "border-border text-text-secondary hover:border-primary hover:text-text-primary"
              }`}
            >
              <span className={listening ? "animate-pulse-fast" : ""}>●</span>
              {listening ? "listening" : "voice"}
            </button>
            <button
              onClick={submit}
              disabled={status === "sending" || !idea.trim()}
              className="rounded-full bg-primary px-6 py-2 font-display text-sm font-medium text-white transition-all hover:bg-active disabled:cursor-not-allowed disabled:opacity-40"
            >
              {status === "sending" ? "Running…" : "Run →"}
            </button>
          </div>
        </div>

        <div className="mt-4 h-5 text-center font-mono text-xs">
          {status === "sent" && <span className="text-success">Got it, running.</span>}
          {status === "error" && (
            <span className="text-error">
              {errorMessage || "Could not reach the harness or voice is unavailable."}
            </span>
          )}
          {status === "idle" && (
            <span className="text-text-secondary">⌘/Ctrl + Enter to run</span>
          )}
        </div>
      </motion.div>
    </div>
  );
}
