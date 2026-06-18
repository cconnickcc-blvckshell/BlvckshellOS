"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import {
  formatApiError,
  getChatHistory,
  getChatSessions,
  OUTCOME_BADGE_STYLES,
  recordOutcome,
  sendChatMessage,
  type ChatMessage,
  type ChatSession,
  type JudgmentOutcome,
} from "@/lib/api";

const SESSION_KEY = "blvckshell_session_id";

export interface DisplayMessage {
  id: string;
  role: "operator" | "blvckbot";
  content: string;
  createdAt: string;
  judgmentOutcome?: JudgmentOutcome | null;
  actionsTaken?: Array<{ capability: string; status?: string }>;
  judgmentIds?: string[];
  pending?: boolean;
}

function toDisplayMessage(msg: ChatMessage): DisplayMessage {
  const meta = msg.metadata ?? {};
  return {
    id: msg.id,
    role: msg.role === "operator" ? "operator" : "blvckbot",
    content: msg.content,
    createdAt: msg.created_at,
    judgmentOutcome: meta.judgment_outcome ?? null,
    actionsTaken: meta.actions_taken,
    judgmentIds: meta.judgment_ids ?? (meta.judgment_id ? [meta.judgment_id] : undefined),
  };
}

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function OutcomeBadge({ outcome }: { outcome: JudgmentOutcome }) {
  return (
    <span
      className={clsx(
        "rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase",
        OUTCOME_BADGE_STYLES[outcome],
      )}
    >
      {outcome}
    </span>
  );
}

function OutcomePrompt({
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
    } catch (err) {
      setSubmitting(false);
      // Outcome recording is non-critical; surface briefly via console for debugging.
      console.warn("Outcome recording failed:", formatApiError(err));
    }
  }

  if (!judgmentId) return null;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      className="mt-2 rounded-lg border border-border/60 bg-surface/60 p-3"
    >
      <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-text-secondary">
        How did this turn out?
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={submitting}
          onClick={() => rate(0.9, "good")}
          className="rounded-full border border-success/40 px-3 py-1 font-mono text-xs text-success hover:bg-success/10 disabled:opacity-40"
        >
          ✓ Good
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => rate(-0.7, "bad")}
          className="rounded-full border border-error/40 px-3 py-1 font-mono text-xs text-error hover:bg-error/10 disabled:opacity-40"
        >
          ✗ Bad
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => rate(0.3, "mixed")}
          className="rounded-full border border-warning/40 px-3 py-1 font-mono text-xs text-warning hover:bg-warning/10 disabled:opacity-40"
        >
          ~ Mixed
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={onDone}
          className="rounded-full border border-border px-3 py-1 font-mono text-xs text-text-secondary hover:text-text-primary"
        >
          skip
        </button>
      </div>
    </motion.div>
  );
}

export function ChatPanel({ className = "" }: { className?: string }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSessionMenu, setShowSessionMenu] = useState(false);
  const [outcomePromptId, setOutcomePromptId] = useState<string | null>(null);
  const [dismissedOutcomes, setDismissedOutcomes] = useState<Set<string>>(new Set());

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const outcomeTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    });
  }, []);

  const loadSession = useCallback(
    async (sid: string) => {
      const history = await getChatHistory(sid);
      setMessages(history.map(toDisplayMessage));
      setSessionId(sid);
      localStorage.setItem(SESSION_KEY, sid);
      scrollToBottom();
    },
    [scrollToBottom],
  );

  useEffect(() => {
    let active = true;

    async function init() {
      try {
        const recentSessions = await getChatSessions();
        if (!active) return;
        setSessions(recentSessions);

        const stored = localStorage.getItem(SESSION_KEY);
        if (stored) {
          await loadSession(stored);
        }
      } catch (err) {
        if (active) setError(formatApiError(err, "Could not connect to harness."));
      }
    }

    init();
    return () => {
      active = false;
    };
  }, [loadSession]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    const timers = outcomeTimers.current;
    return () => {
      timers.forEach((t) => clearTimeout(t));
    };
  }, []);

  function scheduleOutcomePrompt(msgId: string) {
    if (outcomeTimers.current.has(msgId)) return;
    const timer = setTimeout(() => {
      setOutcomePromptId((current) => current ?? msgId);
    }, 30_000);
    outcomeTimers.current.set(msgId, timer);
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;

    setError(null);
    setSending(true);
    setInput("");

    const optimisticId = `pending-${Date.now()}`;
    const operatorMsg: DisplayMessage = {
      id: optimisticId,
      role: "operator",
      content: text,
      createdAt: new Date().toISOString(),
    };
    const typingId = `typing-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      operatorMsg,
      {
        id: typingId,
        role: "blvckbot",
        content: "",
        createdAt: new Date().toISOString(),
        pending: true,
      },
    ]);

    try {
      const res = await sendChatMessage(text, sessionId ?? undefined);
      localStorage.setItem(SESSION_KEY, res.session_id);
      setSessionId(res.session_id);

      const botMsg: DisplayMessage = {
        id: `bot-${Date.now()}`,
        role: "blvckbot",
        content: res.response,
        createdAt: new Date().toISOString(),
        judgmentOutcome: res.judgment_outcome,
        actionsTaken: res.actions_taken,
        judgmentIds: res.judgment_ids,
      };

      setMessages((prev) => [
        ...prev.filter((m) => m.id !== typingId && m.id !== optimisticId),
        { ...operatorMsg, id: `op-${Date.now()}` },
        botMsg,
      ]);

      if (res.judgment_ids?.length) {
        scheduleOutcomePrompt(botMsg.id);
      }

      const updatedSessions = await getChatSessions();
      setSessions(updatedSessions);
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== typingId && m.id !== optimisticId));
      setError(formatApiError(err, "Failed to send message. Is the harness running?"));
      setInput(text);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  function startNewSession() {
    localStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    setMessages([]);
    setOutcomePromptId(null);
    setDismissedOutcomes(new Set());
    outcomeTimers.current.forEach((t) => clearTimeout(t));
    outcomeTimers.current.clear();
    setShowSessionMenu(false);
  }

  async function switchSession(sid: string) {
    setShowSessionMenu(false);
    setOutcomePromptId(null);
    setDismissedOutcomes(new Set());
    try {
      await loadSession(sid);
    } catch (err) {
      setError(formatApiError(err, "Could not load session history."));
    }
  }

  const sessionLabel =
    sessions.find((s) => s.session_id === sessionId)?.session_id.slice(0, 8) ?? "new session";

  return (
    <div className={clsx("flex h-full flex-col bg-bg/40", className)}>
      <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h2 className="font-display text-sm font-semibold text-text-primary">Blvckbot</h2>
          <p className="font-mono text-[10px] text-text-secondary">conversational coordinator</p>
        </div>
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowSessionMenu((v) => !v)}
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 font-mono text-[10px] text-text-secondary hover:border-primary hover:text-text-primary"
          >
            {sessionLabel} ▾
          </button>
          {showSessionMenu && (
            <div className="absolute right-0 top-full z-20 mt-1 w-56 rounded-lg border border-border bg-surface py-1 shadow-xl">
              <button
                type="button"
                onClick={startNewSession}
                className="w-full px-3 py-2 text-left font-mono text-xs text-active hover:bg-primary/10"
              >
                + New session
              </button>
              {sessions.map((s) => (
                <button
                  key={s.session_id}
                  type="button"
                  onClick={() => switchSession(s.session_id)}
                  className={clsx(
                    "w-full px-3 py-2 text-left font-mono text-xs hover:bg-surface/80",
                    s.session_id === sessionId ? "text-active" : "text-text-secondary",
                  )}
                >
                  {s.session_id.slice(0, 8)} · {s.message_count} msgs ·{" "}
                  {new Date(s.created_at).toLocaleDateString()}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary/20 font-display text-sm text-active">
              B
            </div>
            <p className="font-display text-lg text-text-primary">Blvckbot is ready.</p>
            <p className="mt-1 max-w-xs font-body text-sm text-text-secondary">
              Ask anything. I coordinate specialist brains and remember every conversation.
            </p>
          </div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((msg) => {
            if (msg.role === "operator") {
              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="mb-4 flex flex-col items-end"
                >
                  <div className="max-w-[85%] rounded-2xl rounded-tr-sm border border-primary/20 bg-primary/10 px-4 py-3">
                    <p className="whitespace-pre-wrap font-body text-sm text-text-primary">
                      {msg.content}
                    </p>
                  </div>
                  <div className="mt-1 flex gap-2 font-mono text-[10px] text-text-secondary">
                    <span>you</span>
                    <span>{formatTime(msg.createdAt)}</span>
                  </div>
                </motion.div>
              );
            }

            const showOutcomePrompt =
              !msg.pending &&
              msg.judgmentIds?.length &&
              !dismissedOutcomes.has(msg.id) &&
              outcomePromptId === msg.id;

            const showRecordLink =
              !msg.pending &&
              msg.judgmentIds?.length &&
              !dismissedOutcomes.has(msg.id) &&
              outcomePromptId !== msg.id;

            return (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                className="mb-4 flex gap-2"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/30 font-display text-xs text-active">
                  B
                </div>
                <div className="min-w-0 max-w-[90%]">
                  <div className="rounded-2xl rounded-tl-sm border border-border bg-surface/80 px-4 py-3">
                    {msg.pending ? (
                      <div className="flex items-center gap-2 font-mono text-xs text-text-secondary">
                        <span className="inline-flex gap-1">
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-active [animation-delay:0ms]" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-active [animation-delay:150ms]" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-active [animation-delay:300ms]" />
                        </span>
                        thinking…
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap font-body text-sm text-text-primary">
                        {msg.content}
                      </p>
                    )}
                  </div>

                  {!msg.pending && (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {msg.judgmentOutcome && <OutcomeBadge outcome={msg.judgmentOutcome} />}
                      {msg.actionsTaken?.map((a) => (
                        <span
                          key={a.capability}
                          className="rounded-full border border-border bg-surface/60 px-2 py-0.5 font-mono text-[10px] text-text-secondary"
                        >
                          → {a.capability}
                        </span>
                      ))}
                      <span className="font-mono text-[10px] text-text-secondary">
                        {formatTime(msg.createdAt)}
                      </span>
                    </div>
                  )}

                  {showOutcomePrompt && (
                    <OutcomePrompt
                      message={msg}
                      onDone={() => {
                        setDismissedOutcomes((s) => new Set(s).add(msg.id));
                        setOutcomePromptId(null);
                      }}
                    />
                  )}

                  {showRecordLink && (
                    <button
                      type="button"
                      onClick={() => setOutcomePromptId(msg.id)}
                      className="mt-1 font-mono text-[10px] text-text-secondary underline hover:text-active"
                    >
                      Record outcome
                    </button>
                  )}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      <div className="shrink-0 border-t border-border p-4">
        {error && <p className="mb-2 font-mono text-xs text-error">{error}</p>}
        <div className="glass rounded-xl p-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={sending}
            placeholder="Message Blvckbot…"
            rows={2}
            className="w-full resize-none bg-transparent px-3 py-2 font-body text-sm text-text-primary outline-none placeholder:text-text-secondary disabled:opacity-50"
          />
          <div className="flex items-center justify-between px-2 pb-1">
            <span className="font-mono text-[10px] text-text-secondary">
              {input.length > 500 ? `${input.length} chars` : "⌘/Ctrl + Enter"}
            </span>
            <button
              type="button"
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className="rounded-full bg-primary px-4 py-1.5 font-display text-sm text-white transition hover:bg-active disabled:cursor-not-allowed disabled:opacity-40"
            >
              {sending ? "…" : "→"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
