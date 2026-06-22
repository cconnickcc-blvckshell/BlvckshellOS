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

-- Outcome capture extensions (OutcomeRecord metadata mirrors changelog + query columns)
alter table judgment_ledger add column if not exists outcome_data jsonb;
alter table judgment_ledger add column if not exists outcome_quality float;
alter table judgment_ledger add column if not exists outcome_recorded_at timestamptz;

-- ============================================================================
-- Conversations: persistent Blvckbot operator dialogue
-- ============================================================================
create table if not exists conversations (
    id          uuid primary key,
    session_id  text        not null,
    role        text        not null,
    brain_id    text,
    content     text        not null,
    metadata    jsonb       not null default '{}'::jsonb,
    created_at  timestamptz not null default now()
);

create index if not exists conversations_session_idx on conversations (session_id);
create index if not exists conversations_created_idx on conversations (created_at desc);

-- ============================================================================
-- Memory Notes: durable, semantically searchable summaries distilled from
-- conversations. Embeddings are stored as plain jsonb float arrays — no
-- pgvector dependency. Similarity ranking happens in Python over a bounded
-- recent-rows candidate set, the same fallback shape as the ilike keyword
-- search above.
-- Schema mirrors harness.schemas.memory.MemoryNote.
-- ============================================================================
create table if not exists memory_notes (
    id               uuid primary key,
    session_id       text        not null,
    operator_id      text,
    content          text        not null,
    topics           jsonb       not null default '[]'::jsonb,
    embedding        jsonb       not null default '[]'::jsonb,
    created_at       timestamptz not null default now(),
    source_entry_ids jsonb       not null default '[]'::jsonb
);

create index if not exists idx_notes_operator on memory_notes (operator_id);
create index if not exists idx_notes_created  on memory_notes (created_at desc);

-- ============================================================================
-- Memory Opinions: synthesized, explicitly revisable standing positions.
-- Unlike doctrine, never validated against outcomes — revised in place by
-- retiring the old row (retired = true, superseded_by = new id) and
-- inserting the replacement (supersedes = old id), so the full arc of how a
-- view changed is preserved.
-- Schema mirrors harness.schemas.memory.Opinion.
-- ============================================================================
create table if not exists memory_opinions (
    id              uuid primary key,
    operator_id     text,
    topic           text        not null,
    statement       text        not null,
    reasoning       text        not null,
    confidence      double precision not null check (confidence >= 0 and confidence <= 1),
    embedding       jsonb       not null default '[]'::jsonb,
    source_note_ids jsonb       not null default '[]'::jsonb,
    supersedes      uuid,
    superseded_by   uuid,
    retired         boolean     not null default false,
    created_at      timestamptz not null default now(),
    changelog       jsonb       not null default '[]'::jsonb
);

create index if not exists idx_opinions_operator on memory_opinions (operator_id);
create index if not exists idx_opinions_retired  on memory_opinions (retired);
create index if not exists idx_opinions_created  on memory_opinions (created_at desc);
