-- ============================================================================
-- PatraRekhaAI Document Intelligence & Email Agent Upgrade Migration
-- ============================================================================

-- 1. Extend document_metadata for actions, provenance, and enriched metadata
ALTER TABLE public.document_metadata
ADD COLUMN IF NOT EXISTS actions_json JSONB;

ALTER TABLE public.document_metadata
ADD COLUMN IF NOT EXISTS provenance JSONB;

COMMENT ON COLUMN public.document_metadata.actions_json IS 'Structured grounded obligations and actionable requirements extracted from document';
COMMENT ON COLUMN public.document_metadata.provenance IS 'Email or attachment provenance (source_type, email_id, thread_id, sender, timestamp)';

-- 2. Document Families table (tracks cluster lineage: Original -> Amendment -> Corrigendum)
CREATE TABLE IF NOT EXISTS public.document_families (
    family_id TEXT NOT NULL,
    root_document_id UUID NOT NULL REFERENCES public.files(file_id) ON DELETE CASCADE,
    member_document_id UUID NOT NULL REFERENCES public.files(file_id) ON DELETE CASCADE,
    role VARCHAR(30) NOT NULL DEFAULT 'ORIGINAL', -- ORIGINAL, AMENDMENT, CORRIGENDUM, EXTENSION
    supersedes_document_id UUID NULL REFERENCES public.files(file_id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT document_families_pkey PRIMARY KEY (family_id, member_document_id)
);

CREATE INDEX IF NOT EXISTS idx_document_families_member ON public.document_families(member_document_id);
CREATE INDEX IF NOT EXISTS idx_document_families_root ON public.document_families(root_document_id);

-- 3. Deadline Reminders table (tracks scheduled reminders)
CREATE TABLE IF NOT EXISTS public.deadline_reminders (
    reminder_id TEXT NOT NULL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES public.files(file_id) ON DELETE CASCADE,
    event_label TEXT NOT NULL,
    deadline_date DATE NOT NULL,
    reminder_type VARCHAR(30) NOT NULL, -- 2_days_before, 1_day_before, same_day, weekly_digest
    recipient_email TEXT NOT NULL,
    scheduled_for DATE NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- PENDING, SENT, CANCELLED, FAILED
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deadline_reminders_status_due ON public.deadline_reminders(status, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_deadline_reminders_doc ON public.deadline_reminders(document_id);
