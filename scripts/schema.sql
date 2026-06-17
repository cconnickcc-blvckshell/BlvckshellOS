-- ─────────────────────────────────────────────────────────────────────────────
-- Blvckshell Agent Harness — Supabase / PostgreSQL schema
--
-- Persistent memory: the Judgment Ledger, doctrine store, episodic memory, and
-- the observer audit log. Apply this in the Supabase SQL editor (or via the
-- Supabase MCP `apply_migration`) before pointing the harness at Supabase.
-- ─────────────────────────────────────────────────────────────────────────────

-- Judgment Ledger v1 (LOCKED) — the system's record of belief and outcome.
create table if not exists judgment_ledger (
    id                  text primary key,
    brain_id            text not null,
    context_id          text not null,
    timestamp           timestamptz not null default now(),
    belief              text not null,
    confidence          double precision not null check (confidence >= 0 and confidence <= 1),
    evidence            jsonb not null default '[]'::jsonb,
    assumptions         jsonb not null default '[]'::jsonb,
    contradicts         jsonb not null default '[]'::jsonb,
    outcome             text,
    outcome_timestamp   timestamptz,
    was_correct         boolean,
    doctrine_promoted   boolean not null default false,
    retired             boolean not null default false,
    changelog           jsonb not null default '[]'::jsonb
);
create index if not exists idx_ledger_context on judgment_ledger (context_id);
create index if not exists idx_ledger_brain on judgment_ledger (brain_id);

-- Doctrine store — append-only, validated wisdom promoted from the ledger.
create table if not exists doctrine (
    id              text primary key,
    brain_id        text not null,
    context_id      text not null,
    belief          text not null,
    confidence      double precision not null,
    evidence        jsonb not null default '[]'::jsonb,
    promoted_at     timestamptz not null default now(),
    superseded_by   text references doctrine (id)
);
create index if not exists idx_doctrine_active on doctrine (superseded_by);

-- Episodic memory — completed pipeline runs and interaction history.
create table if not exists episodic_memory (
    id              text primary key,
    context_id      text not null,
    objective       text not null,
    result          jsonb not null default '{}'::jsonb,
    recorded_at     timestamptz not null default now()
);
create index if not exists idx_episodic_recorded on episodic_memory (recorded_at desc);

-- Observer audit log — every event in the harness.
create table if not exists observer_events (
    id              text primary key,
    timestamp       timestamptz not null default now(),
    event_type      text not null,
    source          text not null,
    context_id      text,
    message         text,
    data            jsonb not null default '{}'::jsonb
);
create index if not exists idx_observer_context on observer_events (context_id);
create index if not exists idx_observer_type on observer_events (event_type);
create index if not exists idx_observer_ts on observer_events (timestamp desc);
