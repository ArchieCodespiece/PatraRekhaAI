-- Document Intake Gatekeeper: per-workspace intake policies.
--
-- The gatekeeper evaluates every incoming attachment against the enabled
-- policy for its workspace.  When no enabled policy exists the gatekeeper
-- is effectively OFF and all documents are ingested exactly as before.
--
-- Workspace resolution:
--   workspace_id = the document's user_id (Supabase Auth UUID),
--   falling back to its owner_email, falling back to the reserved
--   'default' workspace for a global policy.
--
-- This table only ADDS configuration. It does not modify any existing table.

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

-- ---------------------------------------------------------------------------
-- Row Level Security
--
-- Policies are read by the backend service role (which bypasses RLS) and are
-- managed by the workspace owner.  Users can only see/update policies for
-- their own workspace.  The reserved 'default' policy applies to everyone,
-- so it is only visible to (and editable by) authenticated users; a true
-- cross-workspace admin can use the service role / Supabase dashboard.
-- ---------------------------------------------------------------------------

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