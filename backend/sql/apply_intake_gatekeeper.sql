-- ============================================================================
-- PatraRekhaAI — Document Intake Gatekeeper (apply once)
--
-- Creates public.intake_policies + public.intake_decisions and seeds optional
-- example policies.  Run this in the Supabase Dashboard -> SQL Editor, then
-- reload the Intake Policies page. All statements are idempotent.
--
-- Order:
--   1. intake_policies (config)
--   2. intake_decisions (audit / quarantine)
--   3. example seed policies (all disabled / opt-in)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. intake_policies
-- ----------------------------------------------------------------------------

create table if not exists public.intake_policies (
    id              uuid primary key default gen_random_uuid(),
    workspace_id    text not null,
    name            text not null default 'Intake policy',
    allowed_categories  text[] not null default '{}',
    blocked_categories  text[] not null default '{}',
    review_categories   text[] not null default '{}',
    sender_rules    jsonb not null default '[]',
    keyword_rules   jsonb not null default '[]',
    min_confidence  numeric not null default 0,
    default_decision text not null default 'REVIEW'
                    check (default_decision in ('ALLOW', 'REVIEW', 'BLOCK')),
    enabled         boolean not null default false,
    policy_version  integer not null default 1,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    constraint intake_policies_workspace_unique unique (workspace_id)
);

create index if not exists idx_intake_policies_enabled
    on public.intake_policies (enabled);

comment on table public.intake_policies is
    'Per-workspace document intake gatekeeper configuration.';
comment on column public.intake_policies.workspace_id is
    'user_id, owner_email, or the reserved ''default'' workspace key.';
comment on column public.intake_policies.sender_rules is
    '[{"match":"domain","value":"@vendor.com","action":"allow|block"},...]';
comment on column public.intake_policies.keyword_rules is
    '[{"match":"regex","value":"confidential","action":"block"},...]';

alter table public.intake_policies enable row level security;

drop policy if exists "intake_policies_select_own" on public.intake_policies;
create policy "intake_policies_select_own"
    on public.intake_policies
    for select
    using (
        workspace_id = auth.uid()::text
        or workspace_id = (
            select email from auth.users where id = auth.uid()
        )
        or workspace_id = 'default'
    );

drop policy if exists "intake_policies_insert_own" on public.intake_policies;
create policy "intake_policies_insert_own"
    on public.intake_policies
    for insert
    with check (
        workspace_id = auth.uid()::text
        or workspace_id = (
            select email from auth.users where id = auth.uid()
        )
    );

drop policy if exists "intake_policies_update_own" on public.intake_policies;
create policy "intake_policies_update_own"
    on public.intake_policies
    for update
    using (
        workspace_id = auth.uid()::text
        or workspace_id = (
            select email from auth.users where id = auth.uid()
        )
    );

drop policy if exists "intake_policies_delete_own" on public.intake_policies;
create policy "intake_policies_delete_own"
    on public.intake_policies
    for delete
    using (
        workspace_id = auth.uid()::text
        or workspace_id = (
            select email from auth.users where id = auth.uid()
        )
    );

-- ----------------------------------------------------------------------------
-- 2. intake_decisions
-- ----------------------------------------------------------------------------

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

-- ----------------------------------------------------------------------------
-- 3. Example seed policies (all disabled / opt-in; replace workspace ids
-- ----------------------------------------------------------------------------

insert into public.intake_policies
    (workspace_id, name, allowed_categories, blocked_categories, review_categories, sender_rules, keyword_rules, enabled, default_decision)
values
    (
        'legal-team',
        'Legal',
        array['contract', 'legal_notice', 'purchase_order', 'policy'],
        array['bank_statement', 'identity_document'],
        array['tax_document', 'salary_slip'],
        jsonb_build_array(
            jsonb_build_object('match', 'domain', 'value', '@courtdomain.gov', 'action', 'allow')
        ),
        jsonb_build_array(),
        false,
        'REVIEW'
    ),
    (
        'finance-team',
        'Finance',
        array['invoice', 'purchase_order', 'tax_document', 'bank_statement', 'quotation'],
        array['identity_document', 'resume'],
        array['salary_slip'],
        jsonb_build_array(),
        jsonb_build_array(),
        false,
        'REVIEW'
    ),
    (
        'hr-team',
        'HR',
        array['resume', 'salary_slip', 'policy', 'identity_document'],
        array['invoice', 'bank_statement', 'tax_document'],
        array['contract', 'technical_document'],
        jsonb_build_array(),
        jsonb_build_array(),
        false,
        'REVIEW'
    ),
    (
        'procurement-team',
        'Procurement',
        array['contract', 'quotation', 'purchase_order', 'invoice', 'legal_notice'],
        array['identity_document'],
        array['technical_document', 'tax_document'],
        jsonb_build_array(
            jsonb_build_object('match', 'domain', 'value', '@vendor-suspicious.com', 'action', 'block')
        ),
        jsonb_build_array(),
        false,
        'REVIEW'
    );