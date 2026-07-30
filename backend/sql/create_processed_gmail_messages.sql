-- Migration: create processed_gmail_messages table
-- Run this once in your Supabase SQL editor.
-- This table tracks which Gmail message IDs have been processed so that
-- the ingestion pipeline never re-uploads or re-processes the same email.

CREATE TABLE IF NOT EXISTS processed_gmail_messages (
    message_id   TEXT        PRIMARY KEY,
    owner_email  TEXT        NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    skipped      BOOLEAN     NOT NULL DEFAULT FALSE,
    skip_reason  TEXT
);

-- Index for fast look-ups by owner
CREATE INDEX IF NOT EXISTS idx_pgm_owner_email
    ON processed_gmail_messages (owner_email);

-- Allow the service role (used by Supabase client) full access
-- Adjust to match your RLS policy if needed.
ALTER TABLE processed_gmail_messages ENABLE ROW LEVEL SECURITY;

-- Policy: allow service role unrestricted access (backend uses service key)
CREATE POLICY "service_role_all" ON processed_gmail_messages
    FOR ALL
    USING (true)
    WITH CHECK (true);
