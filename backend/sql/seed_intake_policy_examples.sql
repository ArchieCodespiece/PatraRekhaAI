-- Optional seed data: example intake policies for common corporate workgroups.
--
-- OPTIONAL: run this only if you want ready-made examples to start from.
-- These rows are configuration DATA, not application logic.  Every one is
-- created with enabled = false, so the gatekeeper stays OFF (current
-- behavior is preserved) until an administrator flips a policy on.
--
-- Workspace ids are placeholders — replace them with the user_id / owner
-- email / 'default' key of the workspace you actually want to configure.
--
-- Sandbox runs:
--   psql "$SUPABASE_DB_URL" -f backend/sql/seed_intake_policy_examples.sql

insert into public.intake_policies
    (workspace_id, name, allowed_categories, blocked_categories, review_categories, sender_rules, keyword_rules, enabled, default_decision)
values
    -- -----------------------------------------------------------------------
    -- Legal: contracts/NDAs/notices flow; bank statements and identity
    -- documents are quarantined for manual review.
    -- -----------------------------------------------------------------------
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

    -- -----------------------------------------------------------------------
    -- Finance: financial records are expected and allowed.
    -- -----------------------------------------------------------------------
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

    -- -----------------------------------------------------------------------
    -- HR: people documents expected; unrelated financial documents blocked.
    -- -----------------------------------------------------------------------
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

    -- -----------------------------------------------------------------------
    -- Procurement: vendor/commercial documents expected.
    -- -----------------------------------------------------------------------
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