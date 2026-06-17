-- Blvckshell Harness — persistent memory schema (Supabase / PostgreSQL).
-- Apply via the Supabase SQL editor or psql before running in persistent mode.

-- ============================================================================
-- Judgment Ledger (episodic memory): every belief a brain has held.
-- Schema mirrors harness.schemas.judgment.JudgmentEntry (LOCKED V1).
-- ============================================================================
create table if not exists judgment_ledger (
    id                 uuid primary key,
    brain_id           text        not null,
    context_id         text        not null,
    timestamp          timestamptz not null default now(),
    belief             text        not null,
    confidence         double precision not null check (confidence >= 0 and confidence <= 1),
    evidence           jsonb       not null default '[]'::jsonb,
    assumptions        jsonb       not null default '[]'::jsonb,
    contradicts        jsonb       not null default '[]'::jsonb,
    outcome            text,
    outcome_timestamp  timestamptz,
    was_correct        boolean,
    doctrine_promoted  boolean     not null default false,
    retired            boolean     not null default false,
    changelog          jsonb       not null default '[]'::jsonb
);

create index if not exists idx_ledger_context  on judgment_ledger (context_id);
create index if not exists idx_ledger_brain    on judgment_ledger (brain_id);
create index if not exists idx_ledger_time     on judgment_ledger (timestamp desc);

-- ============================================================================
-- Doctrine Store (append-only): validated beliefs promoted from the ledger.
-- Never deleted, only superseded (retired = true).
-- ============================================================================
create table if not exists doctrine (
    id                 uuid primary key,
    brain_id           text        not null,
    context_id         text        not null,
    timestamp          timestamptz not null default now(),
    belief             text        not null,
    confidence         double precision not null,
    evidence           jsonb       not null default '[]'::jsonb,
    assumptions        jsonb       not null default '[]'::jsonb,
    contradicts        jsonb       not null default '[]'::jsonb,
    outcome            text,
    outcome_timestamp  timestamptz,
    was_correct        boolean,
    doctrine_promoted  boolean     not null default true,
    retired            boolean     not null default false,
    changelog          jsonb       not null default '[]'::jsonb
);

create index if not exists idx_doctrine_retired on doctrine (retired);
create index if not exists idx_doctrine_time    on doctrine (timestamp desc);

-- ============================================================================
-- Audit Log (Observer): every event in the harness.
-- Schema mirrors harness.schemas.audit.AuditEvent.
-- ============================================================================
create table if not exists audit_log (
    id          uuid primary key,
    timestamp   timestamptz not null default now(),
    event_type  text        not null,
    source      text        not null,
    context_id  text,
    message     text        not null default '',
    data        jsonb       not null default '{}'::jsonb
);

create index if not exists idx_audit_context on audit_log (context_id);
create index if not exists idx_audit_time    on audit_log (timestamp desc);
create index if not exists idx_audit_type    on audit_log (event_type);
