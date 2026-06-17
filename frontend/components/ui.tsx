import type { ReactNode } from "react";

/** A surface panel with the command-center treatment. */
export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-border bg-surface/70 backdrop-blur-sm ${className}`}
    >
      {children}
    </div>
  );
}

/** A page header with a display title and optional subtitle. */
export function PageHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <header className="mb-8">
      <h1 className="font-display text-2xl font-semibold tracking-tight text-text-primary">
        {title}
      </h1>
      {subtitle && (
        <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>
      )}
    </header>
  );
}

const CONFIDENCE_COLOR = (c: number): string =>
  c >= 0.75 ? "#22C55E" : c >= 0.5 ? "#A855F7" : "#F59E0B";

/** A compact confidence meter for ledger/doctrine rows. */
export function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.round(value * 100)}%`,
            background: CONFIDENCE_COLOR(value),
          }}
        />
      </div>
      <span className="font-mono text-xs text-text-secondary">
        {value.toFixed(2)}
      </span>
    </div>
  );
}

const EVENT_TONE: Record<string, string> = {
  task_failed: "text-error",
  error: "text-error",
  pipeline_completed: "text-success",
  task_completed: "text-success",
  doctrine_promoted: "text-active",
  llm_call: "text-text-secondary",
  tool_call: "text-warning",
};

/** Color-code an observer event type. */
export function eventTone(eventType: string): string {
  return EVENT_TONE[eventType] ?? "text-text-primary";
}
