// Thin client for the Blvckshell harness HTTP API.

export const HARNESS_URL =
  process.env.NEXT_PUBLIC_HARNESS_URL || "http://localhost:8000";

export type BrainState =
  | "IDLE"
  | "THINKING"
  | "EXECUTING"
  | "ERROR"
  | "OFFLINE";

export interface Brain {
  brain_id: string;
  name: string;
  description: string;
  capabilities: string[];
  model: string;
  tools: string[];
  state: BrainState;
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

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${HARNESS_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  submitIdea: async (text: string, wait = false) => {
    const res = await fetch(`${HARNESS_URL}/intake`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, wait }),
    });
    if (!res.ok) throw new Error(`intake → ${res.status}`);
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
};
