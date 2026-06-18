import type { AuditEvent } from "./api";

export interface JudgmentFeedItem {
  id: string;
  timestamp: string;
  outcome: string;
  brainId: string;
  detail: string;
  signalCount: number;
  kind: "stage" | "guard" | "created";
}

const JUDGMENT_EVENT_TYPES = new Set([
  "JUDGMENT_STAGE_COMPLETED",
  "JUDGMENT_GUARD_BLOCKED",
  "JUDGMENT_CREATED",
]);

export function isJudgmentEvent(event: AuditEvent): boolean {
  return JUDGMENT_EVENT_TYPES.has(event.event_type);
}

export function auditEventToFeedItem(event: AuditEvent): JudgmentFeedItem | null {
  if (!isJudgmentEvent(event)) return null;

  if (event.event_type === "JUDGMENT_GUARD_BLOCKED") {
    return {
      id: event.id,
      timestamp: event.timestamp,
      outcome: "HOLD",
      brainId: event.source,
      detail: event.message || "guard blocked",
      signalCount: 0,
      kind: "guard",
    };
  }

  if (event.event_type === "JUDGMENT_STAGE_COMPLETED") {
    const stage = String(event.data.stage ?? "");
    const consumed = (event.data.consumed_signals as string[] | undefined) ?? [];
    const output = (event.data.output as Record<string, unknown> | undefined) ?? {};

    if (stage === "DECISION") {
      const finalOutcome = String(output.final_outcome ?? "—");
      return {
        id: event.id,
        timestamp: event.timestamp,
        outcome: finalOutcome,
        brainId: event.source,
        detail: "Evidence→Decision",
        signalCount: consumed.length,
        kind: "stage",
      };
    }

    if (stage !== "EVIDENCE" && stage !== "CONFIDENCE") return null;

    const provisional = output.provisional_outcome
      ? String(output.provisional_outcome)
      : stage;

    return {
      id: event.id,
      timestamp: event.timestamp,
      outcome: provisional,
      brainId: event.source,
      detail: stage,
      signalCount: consumed.length,
      kind: "stage",
    };
  }

  if (event.event_type === "JUDGMENT_CREATED") {
    return {
      id: event.id,
      timestamp: event.timestamp,
      outcome: "LOGGED",
      brainId: event.source,
      detail: event.message?.slice(0, 60) || "belief recorded",
      signalCount: 0,
      kind: "created",
    };
  }

  return null;
}
