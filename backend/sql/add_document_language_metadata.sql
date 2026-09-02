-- Add language detection metadata to document_metadata table
-- This migration adds columns for storing detected language information

-- Add language column (primary detected language)
ALTER TABLE document_metadata
ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en';

-- Add languages column (all detected languages, for multilingual documents)
ALTER TABLE document_metadata
ADD COLUMN IF NOT EXISTS languages JSONB DEFAULT '["en"]'::jsonb;

-- Add script column (primary detected script)
ALTER TABLE document_metadata
ADD COLUMN IF NOT EXISTS script VARCHAR(50) DEFAULT 'Latin';

-- Add scripts column (all detected scripts)
ALTER TABLE document_metadata
ADD COLUMN IF NOT EXISTS scripts JSONB DEFAULT '["Latin"]'::jsonb;

-- Add language confidence score
ALTER TABLE document_metadata
ADD COLUMN IF NOT EXISTS language_confidence FLOAT DEFAULT 1.0;

-- Add flag for Romanized content (Hinglish, Benglish, etc.)
ALTER TABLE document_metadata
ADD COLUMN IF NOT EXISTS is_romanized BOOLEAN DEFAULT FALSE;

-- Add flag for code-switched content (multiple languages)
ALTER TABLE document_metadata
ADD COLUMN IF NOT EXISTS is_code_switched BOOLEAN DEFAULT FALSE;

-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_document_metadata_language
ON document_metadata (language);

CREATE INDEX IF NOT EXISTS idx_document_metadata_script
ON document_metadata (script);

-- Add comments for documentation
COMMENT ON COLUMN document_metadata.language IS 'Primary detected language code (ISO 639-1)';
COMMENT ON COLUMN document_metadata.languages IS 'All detected languages as JSON array';
COMMENT ON COLUMN document_metadata.script IS 'Primary detected script name';
COMMENT ON COLUMN document_metadata.scripts IS 'All detected scripts as JSON array';
COMMENT ON COLUMN document_metadata.language_confidence IS 'Confidence score for language detection (0.0-1.0)';
COMMENT ON COLUMN document_metadata.is_romanized IS 'Whether the document contains Romanized Indic content (Hinglish, Benglish, etc.)';
COMMENT ON COLUMN document_metadata.is_code_switched IS 'Whether the document contains multiple languages';
