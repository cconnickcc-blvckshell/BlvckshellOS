import type {
  BrainInfo,
  DoctrineRecord,
  IntakeAck,
  JudgmentEntry,
  ObserverEvent,
  PipelineView,
} from "./types";

const API_URL =
  process.env.NEXT_PUBLIC_HARNESS_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function submitIdea(text: string): Promise<IntakeAck> {
  const res = await fetch(`${API_URL}/intake`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    throw new Error(`intake failed: ${res.status}`);
  }
  return (await res.json()) as IntakeAck;
}

export async function getBrains(): Promise<BrainInfo[]> {
  const data = await get<{ brains: BrainInfo[] }>("/brains");
  return data.brains;
}

export async function getPipeline(id: string): Promise<PipelineView> {
  return get<PipelineView>(`/pipelines/${id}`);
}

export async function getJudgments(): Promise<JudgmentEntry[]> {
  const data = await get<{ judgments: JudgmentEntry[] }>("/judgments");
  return data.judgments;
}

export async function getDoctrine(): Promise<DoctrineRecord[]> {
  const data = await get<{ doctrine: DoctrineRecord[] }>("/doctrine");
  return data.doctrine;
}

export async function getEvents(limit = 200): Promise<ObserverEvent[]> {
  const data = await get<{ events: ObserverEvent[] }>(
    `/observer?limit=${limit}`,
  );
  return data.events;
}

export function observerStreamUrl(): string {
  return `${API_URL}/observer/stream`;
}

export { API_URL };
