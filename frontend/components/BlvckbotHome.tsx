"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { BlvckbotCore, type CoreState } from "@/components/BlvckbotCore";
import { VoiceInput } from "@/components/VoiceInput";
import { MediaAttach, filesToAttachments, type ChatAttachment } from "@/components/MediaAttach";
import { ChatTranscript, useStreamingText, type DisplayMessage } from "@/components/ChatTranscript";
import { BrainColumn } from "@/components/BrainColumn";
import { DelegationBeam } from "@/components/DelegationBeam";
import {
  formatApiError,
  getChatHistory,
  getChatSessions,
  sendChatMessage,
  type ChatMessage,
} from "@/lib/api";

const SESSION_KEY = "blvckshell_session_id";

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

export function BlvckbotHome() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [coreState, setCoreState] = useState<CoreState>("idle");
  const [micAmplitude, setMicAmplitude] = useState(0);
  const [dropActive, setDropActive] = useState(false);
  const [delegatingTo, setDelegatingTo] = useState<string | undefined>();
  const [showBrainColumn, setShowBrainColumn] = useState(false);
  const [speakingText, setSpeakingText] = useState<string | null>(null);
  const [outcomePromptId, setOutcomePromptId] = useState<string | null>(null);
  const [dismissedOutcomes, setDismissedOutcomes] = useState<Set<string>>(new Set());

  const outcomeTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const containerRef = useRef<HTMLDivElement>(null);
  const coreRef = useRef<HTMLDivElement>(null);
  const brainOrbRefs = useRef<Map<string, HTMLElement>>(new Map());
  const streamingContent = useStreamingText(speakingText, coreState === "speaking");

  const loadSession = useCallback(async (sid: string) => {
    const history = await getChatHistory(sid);
    setMessages(history.map(toDisplayMessage));
    setSessionId(sid);
    localStorage.setItem(SESSION_KEY, sid);
  }, []);

  useEffect(() => {
    let active = true;
    async function init() {
      try {
        await getChatSessions();
        const stored = localStorage.getItem(SESSION_KEY);
        if (stored && active) await loadSession(stored);
      } catch (err) {
        if (active) setError(formatApiError(err, "Could not connect to harness."));
      }
    }
    void init();
    return () => {
      active = false;
    };
  }, [loadSession]);

  useEffect(() => {
    if (coreState === "speaking" && streamingContent === speakingText) {
      const t = setTimeout(() => setCoreState("idle"), 400);
      return () => clearTimeout(t);
    }
  }, [coreState, streamingContent, speakingText]);

  function scheduleOutcomePrompt(msgId: string) {
    if (outcomeTimers.current.has(msgId)) return;
    outcomeTimers.current.set(
      msgId,
      setTimeout(() => setOutcomePromptId((c) => c ?? msgId), 30_000),
    );
  }

  const submitMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if ((!trimmed && attachments.length === 0) || coreState === "thinking") return;

      setError(null);
      setCoreState("thinking");

      const sentAttachments = [...attachments];
      const operatorMsg: DisplayMessage = {
        id: `op-${Date.now()}`,
        role: "operator",
        content: trimmed || `[${sentAttachments.map((a) => a.filename).join(", ")}]`,
        createdAt: new Date().toISOString(),
        attachments: sentAttachments.map((a) => ({
          type: a.type,
          filename: a.filename,
          media_type: a.media_type,
          previewUrl:
            a.previewUrl ??
            (a.type === "image" ? `data:${a.media_type};base64,${a.data}` : undefined),
        })),
      };
      const pendingId = `pending-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        operatorMsg,
        { id: pendingId, role: "blvckbot", content: "", createdAt: new Date().toISOString(), pending: true },
      ]);
      setInput("");
      setAttachments([]);

      try {
        const res = await sendChatMessage(trimmed, sessionId ?? undefined, sentAttachments);
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

        setMessages((prev) => [...prev.filter((m) => m.id !== pendingId), botMsg]);

        const targetBrain =
          res.actions_taken[0]?.brain_id ?? res.actions_taken[0]?.capability;
        if (targetBrain) {
          setCoreState("delegating");
          setDelegatingTo(targetBrain);
          setSpeakingText(res.response);
          setTimeout(() => {
            setCoreState("speaking");
            setDelegatingTo(undefined);
          }, 800);
        } else {
          setSpeakingText(res.response);
          setCoreState("speaking");
        }

        if (res.judgment_ids?.length) scheduleOutcomePrompt(botMsg.id);
      } catch (err) {
        setMessages((prev) => prev.filter((m) => m.id !== pendingId));
        setCoreState("error");
        setError(formatApiError(err, "Request failed."));
        setTimeout(() => setCoreState("idle"), 2000);
      }
    },
    [attachments, coreState, sessionId],
  );

  const displayMessages = messages.map((m) =>
    coreState === "speaking" && m.content === speakingText && m.role === "blvckbot"
      ? { ...m, content: streamingContent ?? m.content }
      : m,
  );

  return (
    <div ref={containerRef} className="relative flex h-full overflow-hidden">
      <DelegationBeam
        active={coreState === "delegating" && !!delegatingTo}
        fromRef={coreRef}
        toBrainId={delegatingTo}
        brainOrbRefs={brainOrbRefs}
        containerRef={containerRef}
      />

      {/* Main Blvckbot column */}
      <div className="flex min-w-0 flex-1 flex-col md:w-[55%]">
        <div
          ref={coreRef}
          className="relative flex flex-1 flex-col items-center justify-center px-4 pt-4"
          onDragEnter={() => setDropActive(true)}
          onDragLeave={() => setDropActive(false)}
        >
          <BlvckbotCore
            state={coreState}
            delegatingTo={delegatingTo}
            micAmplitude={micAmplitude}
            dropActive={dropActive}
            className="w-full max-w-[min(100%,320px)] aspect-square"
            onDrop={(files) => {
              setDropActive(false);
              void filesToAttachments(files).then((a) =>
                setAttachments((prev) => [...prev, ...a]),
              );
            }}
          />

          <VoiceInput
            disabled={coreState === "thinking"}
            className="mt-2"
            onTranscript={(text) => void submitMessage(text)}
            onListeningChange={(listening, amp) => {
              setMicAmplitude(amp);
              if (listening) setCoreState("listening");
              else if (coreState === "listening") setCoreState("idle");
            }}
          />
        </div>

        <div className="shrink-0 border-t border-border/60 px-2">
          <ChatTranscript
            messages={displayMessages}
            outcomePromptId={outcomePromptId}
            dismissedOutcomes={dismissedOutcomes}
            onOutcomePrompt={setOutcomePromptId}
            onDismissOutcome={(id) => setDismissedOutcomes((s) => new Set(s).add(id))}
          />

          {error && (
            <p className="px-3 py-1 font-mono text-xs text-error">{error}</p>
          )}

          <div className="flex items-end gap-2 p-3">
            <MediaAttach attachments={attachments} onChange={setAttachments} />
            <div className="glass flex min-w-0 flex-1 items-end rounded-xl p-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    void submitMessage(input);
                  }
                }}
                rows={1}
                placeholder="Type a message…"
                className="max-h-24 min-h-[36px] w-full resize-none bg-transparent px-2 py-1.5 font-body text-sm text-text-primary outline-none placeholder:text-text-secondary"
              />
              <button
                type="button"
                onClick={() => void submitMessage(input)}
                disabled={coreState === "thinking" || (!input.trim() && attachments.length === 0)}
                className="shrink-0 rounded-full bg-primary px-3 py-1.5 font-display text-sm text-white hover:bg-active disabled:opacity-40"
              >
                →
              </button>
            </div>
          </div>
          <p className="pb-2 text-center font-mono text-[9px] text-text-secondary">
            {input.length > 500 ? `${input.length} chars` : "⌘/Ctrl + Enter · voice is primary"}
          </p>
        </div>
      </div>

      {/* Brain column — desktop */}
      <BrainColumn
        activeDelegation={delegatingTo}
        brainOrbRefs={brainOrbRefs}
        onDelegation={(id) => {
          setDelegatingTo(id);
          setCoreState((s) => {
            if (id) return "delegating";
            if (s === "delegating") return "thinking";
            return s;
          });
        }}
        className="hidden w-[45%] md:flex"
      />

      {/* Mobile brain column drawer */}
      <button
        type="button"
        onClick={() => setShowBrainColumn(true)}
        className="fixed bottom-20 right-4 z-30 rounded-full border border-border bg-surface/90 px-3 py-2 font-mono text-[10px] text-active md:hidden"
      >
        Team ◎
      </button>
      {showBrainColumn && (
        <>
          <button
            type="button"
            aria-label="Close"
            className="fixed inset-0 z-40 bg-black/60 md:hidden"
            onClick={() => setShowBrainColumn(false)}
          />
          <div className="fixed inset-y-0 right-0 z-50 w-[85vw] max-w-sm md:hidden">
            <BrainColumn
              activeDelegation={delegatingTo}
              brainOrbRefs={brainOrbRefs}
              onDelegation={(id) => {
                setDelegatingTo(id);
                setCoreState((s) => {
                  if (id) return "delegating";
                  if (s === "delegating") return "thinking";
                  return s;
                });
              }}
              className="h-full bg-bg"
            />
          </div>
        </>
      )}
    </div>
  );
}
