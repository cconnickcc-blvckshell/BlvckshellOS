// Thin client for the Blvckshell harness HTTP API.

import { createReconnectingObserverStream } from "./observerStream";

export const HARNESS_URL = (
  process.env.NEXT_PUBLIC_HARNESS_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export type BrainState =
  | "IDLE"
  | "THINKING"
  | "EXECUTING"
  | "ERROR"
  | "OFFLINE";

export type JudgmentOutcome =
  | "PROCEED"
  | "STAGED_PROCEED"
  | "REQUEST_MORE_EVIDENCE"
  | "HOLD";

export interface Brain {
  brain_id: string;
  name: string;
  description: string;
  capabilities: string[];
  model: string;
  tools: string[];
  state: BrainState;
  pipeline_participant?: boolean;
}

export interface Pipeline {
  pipeline_id: string;
  idea: string;
  status: string;
  output?: string;
  plan?: Array<Record<string, unknown>>;
  history?: Array<{ brain: string; summary: string }>;
}

export interface Judgment {
  id: string;
  brain_id: string;
  context_id: string;
  timestamp: string;
  belief: string;
  confidence: number;
  was_correct: boolean | null;
  doctrine_promoted: boolean;
  retired: boolean;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  event_type: string;
  source: string;
  context_id: string | null;
  message: string;
  data: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: string;
  brain_id?: string | null;
  content: string;
  metadata?: {
    judgment_outcome?: JudgmentOutcome;
    judgment_id?: string;
    judgment_ids?: string[];
    actions_taken?: Array<{
      capability: string;
      brain_id?: string;
      objective?: string;
      status?: string;
      result?: string;
    }>;
    source?: string;
  };
  created_at: string;
}

export interface ChatSession {
  session_id: string;
  operator_id: string;
  created_at: string;
  message_count: number;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  judgment_outcome: JudgmentOutcome | null;
  actions_taken: Array<{
    capability: string;
    brain_id?: string;
    objective?: string;
    status?: string;
    result?: string;
  }>;
  judgment_ids: string[];
}

export interface MemoryNote {
  id: string;
  session_id: string;
  operator_id?: string | null;
  content: string;
  topics: string[];
  created_at: string;
  source_entry_ids: string[];
}

export interface Opinion {
  id: string;
  operator_id?: string | null;
  topic: string;
  statement: string;
  reasoning: string;
  confidence: number;
  source_note_ids: string[];
  supersedes?: string | null;
  superseded_by?: string | null;
  retired: boolean;
  created_at: string;
  changelog: Array<{ action: string; timestamp: string; details?: Record<string, unknown> }>;
}

export interface MemorySearchResult {
  notes: MemoryNote[];
  opinions: Opinion[];
}

export interface OutcomeRecord {
  actual_outcome: string;
  outcome_quality: number;
  missed_opportunity?: string | null;
  lessons?: string[];
}

export interface Approval {
  id: string;
  brain_id: string;
  context_id: string;
  timestamp: string;
  belief: string;
  confidence: number;
  evidence: string[];
  assumptions: string[];
  outcome: string | null;
}

export interface Lead {
  id: string;
  title: string;
  description: string;
  skills: string[];
  budget_amount?: number | null;
  budget_currency?: string;
  engagement_type?: string | null;
  source: string;
  score?: number;
  score_factors?: Record<string, number>;
}

export interface FiverrLeadPayload {
  title: string;
  description: string;
  budget?: number;
  currency?: string;
  skills?: string[];
  engagement_type?: string;
  factors?: Record<string, number>;
}

export interface ApiErrorBody {
  code?: string;
  message?: string;
  detail?: string;
  correlation_id?: string;
  source?: string;
  context_id?: string;
}

export class ApiError extends Error {
  status: number;
  code: string;
  detail: string;
  correlationId?: string;
  path: string;

  constructor(
    path: string,
    status: number,
    body: ApiErrorBody | string | null,
  ) {
    const parsed = parseErrorBody(body);
    const message =
      parsed.detail || parsed.message || `Request to ${path} failed (${status})`;
    super(message);
    this.name = "ApiError";
    this.path = path;
    this.status = status;
    this.code = parsed.code || `HTTP_${status}`;
    this.detail = message;
    this.correlationId = parsed.correlation_id;
  }
}

function parseErrorBody(body: ApiErrorBody | string | null): ApiErrorBody {
  if (!body) return {};
  if (typeof body === "string") {
    const trimmed = body.trim();
    return trimmed ? { message: trimmed, detail: trimmed } : {};
  }
  const message = (body.message || body.detail || "").trim();
  const detail = (body.detail || body.message || "").trim();
  return {
    ...body,
    message: message || detail,
    detail: detail || message,
  };
}

export function formatApiError(err: unknown, fallback = "Request failed"): string {
  if (err instanceof ApiError) {
    const parts = [err.detail];
    if (err.code && err.code !== `HTTP_${err.status}`) {
      parts.push(`[${err.code}]`);
    }
    if (err.correlationId) {
      parts.push(`(ref: ${err.correlationId.slice(0, 8)})`);
    }
    return parts.filter(Boolean).join(" ");
  }
  if (err instanceof Error && err.message.trim()) {
    return err.message;
  }
  return fallback;
}

async function parseApiError(res: Response, path: string): Promise<ApiError> {
  let body: ApiErrorBody | string | null = null;
  try {
    const text = await res.text();
    if (text) {
      try {
        body = JSON.parse(text) as ApiErrorBody;
      } catch {
        body = text;
      }
    }
  } catch {
    body = null;
  }
  return new ApiError(path, res.status, body);
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${HARNESS_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw await parseApiError(res, path);
  return res.json() as Promise<T>;
}

export interface ChatAttachmentPayload {
  type: "image" | "video" | "document";
  filename: string;
  media_type: string;
  data: string;
}

export async function sendChatMessage(
  message: string,
  sessionId?: string,
  attachments?: ChatAttachmentPayload[],
): Promise<ChatResponse> {
  const path = "/chat";
  const res = await fetch(`${HARNESS_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: message || "",
      session_id: sessionId,
      attachments: attachments?.length ? attachments : undefined,
    }),
  });
  if (!res.ok) throw await parseApiError(res, path);
  return res.json() as Promise<ChatResponse>;
}

export async function getChatHistory(sessionId: string): Promise<ChatMessage[]> {
  return get<ChatMessage[]>(`/chat/history/${sessionId}`);
}

export async function getChatSessions(): Promise<ChatSession[]> {
  return get<ChatSession[]>("/chat/sessions");
}

export async function recordOutcome(
  judgmentId: string,
  outcome: OutcomeRecord,
): Promise<Judgment> {
  const path = `/judgments/${judgmentId}/outcome`;
  const res = await fetch(`${HARNESS_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(outcome),
  });
  if (!res.ok) throw await parseApiError(res, path);
  return res.json() as Promise<Judgment>;
}

export function connectObserverStream(
  onEvent: (event: AuditEvent) => void,
): EventSource {
  return createReconnectingObserverStream(onEvent);
}

export const OUTCOME_BADGE_STYLES: Record<JudgmentOutcome, string> = {
  PROCEED: "border-success/40 bg-success/10 text-success",
  STAGED_PROCEED: "border-warning/40 bg-warning/10 text-warning",
  REQUEST_MORE_EVIDENCE: "border-blue-400/40 bg-blue-400/10 text-blue-400",
  HOLD: "border-error/40 bg-error/10 text-error",
};

export const api = {
  submitIdea: async (text: string, wait = false) => {
    const path = "/intake";
    const res = await fetch(`${HARNESS_URL}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, wait }),
    });
    if (!res.ok) throw await parseApiError(res, path);
    return res.json();
  },
  brains: () => get<Brain[]>("/brains"),
  pipelines: () => get<Pipeline[]>("/pipelines"),
  pipeline: (id: string) => get<Pipeline>(`/pipelines/${id}`),
  ledger: (brainId?: string) =>
    get<Judgment[]>(`/ledger${brainId ? `?brain_id=${brainId}` : ""}`),
  doctrine: () => get<Judgment[]>("/doctrine"),
  events: () => get<AuditEvent[]>("/observer/events"),
  streamUrl: () => `${HARNESS_URL}/observer/stream`,
  memoryNotes: () => get<MemoryNote[]>("/memory/notes"),
  opinions: (includeRetired = false) =>
    get<Opinion[]>(`/memory/opinions${includeRetired ? "?include_retired=true" : ""}`),
  searchMemory: (q: string) =>
    get<MemorySearchResult>(`/memory/search?q=${encodeURIComponent(q)}`),
  approvals: () => get<Approval[]>("/approvals"),
  leads: () => get<Lead[]>("/leads"),
  submitFiverrLead: async (payload: FiverrLeadPayload) => {
    const path = "/leads/fiverr";
    const res = await fetch(`${HARNESS_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await parseApiError(res, path);
    return res.json() as Promise<Lead>;
  },
  sendChatMessage,
  getChatHistory,
  getChatSessions,
  recordOutcome,
  connectObserverStream,
};
