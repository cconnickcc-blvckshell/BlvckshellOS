"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import {
  OUTCOME_BADGE_STYLES,
  recordOutcome,
  type JudgmentOutcome,
} from "@/lib/api";

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function OutcomeBadge({ outcome }: { outcome: JudgmentOutcome }) {
  return (
    <span
      className={clsx(
        "rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase",
        OUTCOME_BADGE_STYLES[outcome],
      )}
    >
      {outcome}
    </span>
  );
}

function OutcomeArcButtons({
  message,
  onDone,
}: {
  message: DisplayMessage;
  onDone: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const judgmentId = message.judgmentIds?.[0];

  async function rate(quality: number, label: string) {
    if (!judgmentId || submitting) return;
    setSubmitting(true);
    try {
      await recordOutcome(judgmentId, {
        actual_outcome: message.content.slice(0, 500),
        outcome_quality: quality,
        lessons: [`operator rated: ${label}`],
      });
      onDone();
    } catch {
      setSubmitting(false);
    }
  }

  if (!judgmentId) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-3 font-mono text-[10px] text-text-secondary">
      <button type="button" disabled={submitting} onClick={() => rate(0.9, "good")} className="hover:text-success">
        ○ good
      </button>
      <button type="button" disabled={submitting} onClick={() => rate(-0.7, "bad")} className="hover:text-error">
        ○ bad
      </button>
      <button type="button" disabled={submitting} onClick={() => rate(0.3, "mixed")} className="hover:text-warning">
        ○ mixed
      </button>
      <button type="button" disabled={submitting} onClick={onDone} className="hover:text-text-primary">
        · skip
      </button>
    </div>
  );
}

export interface ChatTranscriptProps {
  messages: DisplayMessage[];
  outcomePromptId: string | null;
  dismissedOutcomes: Set<string>;
  onOutcomePrompt: (id: string | null) => void;
  onDismissOutcome: (id: string) => void;
}

export interface DisplayMessage {
  id: string;
  role: "operator" | "blvckbot";
  content: string;
  createdAt: string;
  judgmentOutcome?: import("@/lib/api").JudgmentOutcome | null;
  actionsTaken?: Array<{ capability: string; brain_id?: string; status?: string; result?: string }>;
  judgmentIds?: string[];
  pending?: boolean;
  attachments?: Array<{
    type: "image" | "video" | "document";
    filename: string;
    media_type: string;
    previewUrl?: string;
  }>;
}

export function ChatTranscript({
  messages,
  outcomePromptId,
  dismissedOutcomes,
  onOutcomePrompt,
  onDismissOutcome,
}: ChatTranscriptProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const visible = messages.slice(-20);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  return (
    <div
      ref={scrollRef}
      className="max-h-[28vh] min-h-[80px] flex-1 overflow-y-auto px-2 py-3"
    >
      <AnimatePresence initial={false}>
        {visible.map((msg) => {
          if (msg.role === "operator") {
            return (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mb-3 text-right"
              >
                {msg.attachments && msg.attachments.length > 0 && (
                  <div className="mb-2 flex flex-wrap justify-end gap-2">
                    {msg.attachments.map((a, i) =>
                      a.type === "image" && a.previewUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          key={`${a.filename}-${i}`}
                          src={a.previewUrl}
                          alt={a.filename}
                          className="max-h-24 max-w-[160px] rounded-lg border border-border object-cover"
                        />
                      ) : (
                        <span
                          key={`${a.filename}-${i}`}
                          className="rounded-full border border-border bg-surface/80 px-2 py-1 font-mono text-[10px] text-text-secondary"
                        >
                          {a.type === "video" ? "▶" : "📄"} {a.filename}
                        </span>
                      ),
                    )}
                  </div>
                )}
                <p className="font-body text-sm text-text-secondary">
                  {msg.content}
                  <span className="ml-2 font-mono text-[9px]">{formatTime(msg.createdAt)}</span>
                </p>
              </motion.div>
            );
          }

          const showPrompt =
            !msg.pending &&
            msg.judgmentIds?.length &&
            !dismissedOutcomes.has(msg.id) &&
            outcomePromptId === msg.id;

          const showLink =
            !msg.pending &&
            msg.judgmentIds?.length &&
            !dismissedOutcomes.has(msg.id) &&
            outcomePromptId !== msg.id;

          const content = msg.content;

          return (
            <motion.div key={msg.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} className="mb-4">
              {msg.pending ? (
                <p className="font-mono text-xs text-text-secondary">…</p>
              ) : (
                <p className="whitespace-pre-wrap font-body text-base text-text-primary">{content}</p>
              )}
              {!msg.pending && (
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  {msg.judgmentOutcome && <OutcomeBadge outcome={msg.judgmentOutcome} />}
                  {msg.actionsTaken?.map((a) => (
                    <span
                      key={a.capability}
                      className="font-mono text-[9px] text-text-secondary/70"
                      title={a.result}
                    >
                      → {a.capability}
                      {a.status ? ` (${a.status})` : ""}
                    </span>
                  ))}
                  <span className="font-mono text-[9px] text-text-secondary">{formatTime(msg.createdAt)}</span>
                </div>
              )}
              {showPrompt && (
                <OutcomeArcButtons
                  message={msg}
                  onDone={() => {
                    onDismissOutcome(msg.id);
                    onOutcomePrompt(null);
                  }}
                />
              )}
              {showLink && (
                <button
                  type="button"
                  onClick={() => onOutcomePrompt(msg.id)}
                  className="mt-1 font-mono text-[9px] text-text-secondary underline hover:text-active"
                >
                  Record outcome
                </button>
              )}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}

/** Simulate streaming by revealing words over time. */
export function useStreamingText(fullText: string | null, active: boolean, ms = 30): string | null {
  const [shown, setShown] = useState<string | null>(null);

  useEffect(() => {
    if (!active || !fullText) {
      setShown(null);
      return;
    }
    const words = fullText.split(/(\s+)/);
    let i = 0;
    setShown("");
    const id = window.setInterval(() => {
      i += 1;
      if (i >= words.length) {
        clearInterval(id);
        setShown(fullText);
        return;
      }
      setShown(words.slice(0, i).join(""));
    }, ms);
    return () => clearInterval(id);
  }, [active, fullText, ms]);

  return active ? shown : fullText;
}
