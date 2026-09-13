-- Migration: create email_records table
-- Run this once in your Supabase SQL editor.
--
-- Purpose:
--   Store plain Gmail messages that have NO processable document attachments.
--   These should NOT enter the AI pipeline (chunking / embeddings / Pinecone).
--   They are displayed in a dedicated "Emails" section in the Documents UI.

CREATE TABLE IF NOT EXISTS email_records (
    email_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    gmail_message_id  TEXT        NOT NULL,
    user_id           UUID        NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    owner_email       TEXT        NOT NULL,
    subject           TEXT,
    sender            TEXT,
    thread_id         TEXT,
    received_at       TIMESTAMPTZ,
    body_text         TEXT,
    email_intent      TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_email_records_gmail_message_id UNIQUE (gmail_message_id)
);

-- Fast look-ups by user
CREATE INDEX IF NOT EXISTS idx_email_records_user_id
    ON email_records (user_id);

CREATE INDEX IF NOT EXISTS idx_email_records_owner_email
    ON email_records (owner_email);

CREATE INDEX IF NOT EXISTS idx_email_records_received_at
    ON email_records (received_at DESC);

-- Row-level security
ALTER TABLE email_records ENABLE ROW LEVEL SECURITY;

-- Allow the service role (backend service key) unrestricted access.
-- Adjust if your project uses a more restrictive RLS setup.
CREATE POLICY "service_role_all" ON email_records
    FOR ALL
    USING (true)
    WITH CHECK (true);
