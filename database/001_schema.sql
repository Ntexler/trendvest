-- TrendVest AI — Database Schema
-- Run this on a fresh PostgreSQL database (Supabase / Neon / local)

-- ══════════════════════════════════════
-- TABLES
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(50) UNIQUE NOT NULL,
    name_en VARCHAR(100) NOT NULL,
    name_he VARCHAR(100) NOT NULL,
    sector VARCHAR(50) NOT NULL,
    sector_en VARCHAR(50) NOT NULL,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    subreddits TEXT[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS topic_stocks (
    id SERIAL PRIMARY KEY,
    topic_id INT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    company_name VARCHAR(100) NOT NULL,
    relevance_note TEXT,
    priority INT NOT NULL DEFAULT 0,
    UNIQUE(topic_id, ticker)
);

CREATE TABLE IF NOT EXISTS topic_mentions (
    id SERIAL PRIMARY KEY,
    topic_id INT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    source VARCHAR(20) NOT NULL CHECK (source IN ('reddit', 'news', 'google_trends')),
    mention_count INT NOT NULL DEFAULT 0,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS momentum_scores (
    id SERIAL PRIMARY KEY,
    topic_id INT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    score FLOAT NOT NULL DEFAULT 0,
    mention_count_today INT NOT NULL DEFAULT 0,
    mention_avg_7d FLOAT NOT NULL DEFAULT 0,
    direction VARCHAR(10) NOT NULL DEFAULT 'stable' CHECK (direction IN ('rising', 'stable', 'falling')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(topic_id)
);

-- Phase 5: Auth tables (create later, included for reference)
-- CREATE TABLE IF NOT EXISTS users (
--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--     email VARCHAR(255) UNIQUE NOT NULL,
--     display_name VARCHAR(100),
--     tier VARCHAR(10) NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'api')),
--     created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
-- );
--
-- CREATE TABLE IF NOT EXISTS watchlist_items (
--     id SERIAL PRIMARY KEY,
--     user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
--     ticker VARCHAR(10) NOT NULL,
--     added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
--     UNIQUE(user_id, ticker)
-- );

-- ══════════════════════════════════════
-- INDEXES
-- ══════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_mentions_topic_date ON topic_mentions(topic_id, collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_mentions_source ON topic_mentions(source, collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_momentum_score ON momentum_scores(score DESC);
CREATE INDEX IF NOT EXISTS idx_topic_stocks_ticker ON topic_stocks(ticker);

-- ══════════════════════════════════════
-- SEED DATA FUNCTION
-- Call: SELECT seed_topics_from_json();
-- (Or use the Python seed script instead)
-- ══════════════════════════════════════

-- Initial momentum scores (zeros, will be populated by pipeline)
CREATE OR REPLACE FUNCTION init_momentum_scores()
RETURNS void AS $$
BEGIN
    INSERT INTO momentum_scores (topic_id, score, mention_count_today, mention_avg_7d, direction)
    SELECT id, 0, 0, 0, 'stable' FROM topics
    ON CONFLICT (topic_id) DO NOTHING;
END;
$$ LANGUAGE plpgsql;
