-- Migration: Add 'x' (Twitter) to topic_mentions source CHECK constraint
-- Run this if the database was created with 001_schema.sql before this change

-- Drop old constraint and add new one
DO $$
BEGIN
    -- Drop existing check constraint on source column
    ALTER TABLE topic_mentions DROP CONSTRAINT IF EXISTS topic_mentions_source_check;
    -- Add updated constraint including 'x'
    ALTER TABLE topic_mentions ADD CONSTRAINT topic_mentions_source_check
        CHECK (source IN ('reddit', 'news', 'google_trends', 'x'));
EXCEPTION
    WHEN others THEN
        RAISE NOTICE 'Constraint update skipped: %', SQLERRM;
END $$;
