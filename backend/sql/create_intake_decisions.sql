-- Document Intake Gatekeeper: audit / quarantine records.
--
-- Every non-trivial gatekeeper decision is recorded here.  REVIEW and BLOCK
-- documents are NOT deleted: they remain stored in the files table (with
-- is_summarized=false / is_vectored=false) and are quarantined via this
-- audit trail until an admin overrides them.
--
-- Sensitive extracted content is deliberately NOT stored.  Only category,
-- confidence, a short human-readable reason, and non-secret match signals
-- are persisted.

create table if not exists public.intake_decisions (
    id              uuid primary key default gen_random_uuid(),
    file_id         uuid references public.files (file_id) on delete cascade,
    source_email_id text,
    workspace_id    text not null,
    decision        text not null check (decision in ('ALLOW', 'REVIEW', 'BLOCK')),
    category        text,
    confidence      numeric,
    signals         jsonb not null default '[]',
    reason          text,
    policy_version  integer,
    classifier      text,
    override_decision text,
    created_at      timestamptz not null default now(),
    constraint intake_decisions_override_check
        check (override_decision is null or override_decision in ('ALLOW', 'BLOCK'))
);

create index if not exists idx_intake_decisions_file_id
    on public.intake_decisions (file_id);

create index if not exists idx_intake_decisions_workspace
    on public.intake_decisions (workspace_id, created_at desc);

create index if not exists idx_intake_decisions_decision
    on public.intake_decisions (decision);

comment on table public.intake_decisions is
    'Audit trail for document intake gatekeeper decisions (ALLOW/REVIEW/BLOCK).';
comment on column public.intake_decisions.override_decision is
    'Admin resolution: ALLOW re-processes the document, BLOCK keeps it held.';

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

alter table public.intake_decisions enable row level security;

drop policy if exists "intake_decisions_select_own" on public.intake_decisions;
create policy "intake_decisions_select_own"
    on public.intake_decisions
    for select
    using (
        workspace_id = auth.uid()::text
        or workspace_id = (
            select email from auth.users where id = auth.uid()
        )
    );

drop policy if exists "intake_decisions_insert_own" on public.intake_decisions;
create policy "intake_decisions_insert_own"
    on public.intake_decisions
    for insert
    with check (
        workspace_id = auth.uid()::text
        or workspace_id = (
            select email from auth.users where id = auth.uid()
        )
    );

drop policy if exists "intake_decisions_update_own" on public.intake_decisions;
create policy "intake_decisions_update_own"
    on public.intake_decisions
    for update
    using (
        workspace_id = auth.uid()::text
        or workspace_id = (
            select email from auth.users where id = auth.uid()
        )
    );