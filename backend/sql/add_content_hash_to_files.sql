-- Migration: add content_hash column to files table
-- Run this once in your Supabase SQL editor.
--
-- content_hash stores the full SHA-256 hex digest of the uploaded file bytes.
-- It is used as the PRIMARY deduplication key: two files with identical bytes
-- (same document sent by different people, with same or different filename)
-- will match on this column and only be stored/processed once.

ALTER TABLE files
    ADD COLUMN IF NOT EXISTS content_hash TEXT;

-- Unique index: enforces one DB record per unique document content.
-- NULLS are excluded so files uploaded before this migration are unaffected.
CREATE UNIQUE INDEX IF NOT EXISTS idx_files_content_hash
    ON files (content_hash)
    WHERE content_hash IS NOT NULL;

-- Regular index for fast look-ups (the unique index already covers this,
-- but making it explicit aids query planning).
CREATE INDEX IF NOT EXISTS idx_files_content_hash_lookup
    ON files (content_hash)
    WHERE content_hash IS NOT NULL;
