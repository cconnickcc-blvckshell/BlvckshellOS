export type BrainStatus =
  | "idle"
  | "thinking"
  | "executing"
  | "error"
  | "offline";

export interface BrainInfo {
  brain_id: string;
  name: string;
  description: string;
  capabilities: string[];
  model: string;
  status: BrainStatus;
  current_task_id: string | null;
  last_heartbeat: string;
}

export interface JudgmentEntry {
  id: string;
  brain_id: string;
  context_id: string;
  timestamp: string;
  belief: string;
  confidence: number;
  evidence: string[];
  assumptions: string[];
  outcome: string | null;
  was_correct: boolean | null;
  doctrine_promoted: boolean;
  retired: boolean;
}

export interface DoctrineRecord {
  id: string;
  brain_id: string;
  belief: string;
  confidence: number;
  promoted_at: string;
}

export interface ObserverEvent {
  id: string;
  timestamp: string;
  event_type: string;
  source: string;
  context_id: string | null;
  message: string;
  data: Record<string, unknown>;
}

export interface IntakeAck {
  pipeline_id: string;
  status: string;
  message: string;
}

export interface PipelineView {
  pipeline_id: string;
  working: Record<string, unknown>;
  result: Record<string, unknown> | null;
  events: ObserverEvent[];
}
