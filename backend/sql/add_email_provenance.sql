-- Add email provenance columns to the files table.
-- Captures where an ingested document came from (Gmail message/thread) so
-- documents can be grouped into thread-families and cited back to source.

ALTER TABLE public.files
ADD COLUMN IF NOT EXISTS source_email_id text,
ADD COLUMN IF NOT EXISTS thread_id text,
ADD COLUMN IF NOT EXISTS source_sender text,
ADD COLUMN IF NOT EXISTS source_subject text,
ADD COLUMN IF NOT EXISTS email_intent varchar(40);

-- Used by document-families clustering to group replies/amendments in one thread.
CREATE INDEX IF NOT EXISTS files_thread_id_idx
ON public.files (thread_id);

COMMENT ON COLUMN public.files.thread_id IS 'Gmail threadId the document arrived in';
COMMENT ON COLUMN public.files.source_email_id IS 'Gmail message id the document arrived in';
COMMENT ON COLUMN public.files.email_intent IS 'Inferred email intent: NOTICE, AMENDMENT, DEADLINE_CHANGE, REMINDER, RESULT, APPEAL, INFORMATIONAL, OTHER';