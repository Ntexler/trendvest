-- TrendVest AI Agent — Database Schema Extension
-- Adds tables for the autonomous AI trading agent

-- ══════════════════════════════════════
-- AGENT SIGNAL TRACKING
-- ══════════════════════════════════════

-- Stores every signal the agent observes before making a decision
CREATE TABLE IF NOT EXISTS agent_signals (
    id SERIAL PRIMARY KEY,
    signal_type VARCHAR(30) NOT NULL CHECK (signal_type IN (
        'momentum', 'sentiment', 'user_herd', 'technical',
        'macro', 'supply_chain', 'cross_reference', 'nlp_sentiment', 'user_ml'
    )),
    ticker VARCHAR(10),
    topic_slug VARCHAR(50),
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('bullish', 'bearish', 'neutral')),
    strength FLOAT NOT NULL DEFAULT 0 CHECK (strength >= 0 AND strength <= 1),
    raw_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════
-- AGENT TRADES
-- ══════════════════════════════════════

-- The agent's paper trades with full signal snapshot for learning
CREATE TABLE IF NOT EXISTS agent_trades (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(4) NOT NULL CHECK (action IN ('buy', 'sell')),
    quantity INT NOT NULL,
    entry_price FLOAT NOT NULL,
    exit_price FLOAT,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    signals_snapshot JSONB NOT NULL,       -- snapshot of all signals at trade time
    outcome_1d FLOAT,                      -- P&L after 1 day
    outcome_7d FLOAT,                      -- P&L after 7 days
    outcome_30d FLOAT,                     -- P&L after 30 days
    is_open BOOLEAN NOT NULL DEFAULT true,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

-- ══════════════════════════════════════
-- AGENT PORTFOLIO STATE
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS agent_portfolio (
    id SERIAL PRIMARY KEY,
    cash_balance FLOAT NOT NULL DEFAULT 100000,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_holdings (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    quantity INT NOT NULL DEFAULT 0,
    avg_cost FLOAT NOT NULL DEFAULT 0,
    entered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════
-- SIGNAL WEIGHT LEARNING
-- ══════════════════════════════════════

-- Tracks how effective each signal type is → agent adjusts these over time
CREATE TABLE IF NOT EXISTS agent_signal_weights (
    id SERIAL PRIMARY KEY,
    signal_type VARCHAR(30) NOT NULL UNIQUE,
    weight FLOAT NOT NULL DEFAULT 1.0,
    total_predictions INT NOT NULL DEFAULT 0,
    correct_predictions INT NOT NULL DEFAULT 0,
    accuracy FLOAT NOT NULL DEFAULT 0.5,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed initial equal weights
INSERT INTO agent_signal_weights (signal_type, weight) VALUES
    ('momentum', 1.0),
    ('sentiment', 1.0),
    ('user_herd', 1.0),
    ('technical', 1.0),
    ('macro', 1.0),
    ('supply_chain', 1.0),
    ('cross_reference', 1.0),
    ('nlp_sentiment', 0.8),
    ('user_ml', 1.2)
ON CONFLICT (signal_type) DO NOTHING;

-- ══════════════════════════════════════
-- AGENT PERFORMANCE LOG
-- ══════════════════════════════════════

-- Daily snapshot of agent performance vs benchmark
CREATE TABLE IF NOT EXISTS agent_performance (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    portfolio_value FLOAT NOT NULL,
    daily_pnl FLOAT NOT NULL DEFAULT 0,
    daily_pnl_pct FLOAT NOT NULL DEFAULT 0,
    cumulative_pnl FLOAT NOT NULL DEFAULT 0,
    cumulative_pnl_pct FLOAT NOT NULL DEFAULT 0,
    benchmark_value FLOAT,                 -- SPY value on same day
    benchmark_pnl_pct FLOAT,              -- SPY cumulative return
    open_positions INT NOT NULL DEFAULT 0,
    total_trades INT NOT NULL DEFAULT 0,
    win_rate FLOAT NOT NULL DEFAULT 0,
    regime VARCHAR(20) DEFAULT 'normal' CHECK (regime IN ('bull', 'bear', 'volatile', 'normal')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════
-- INDEXES
-- ══════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_agent_signals_type ON agent_signals(signal_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_signals_ticker ON agent_signals(ticker, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_trades_open ON agent_trades(is_open, opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_trades_ticker ON agent_trades(ticker, opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_perf_date ON agent_performance(date DESC);

-- ══════════════════════════════════════
-- ML MODEL STORAGE
-- ══════════════════════════════════════

-- Stores trained ML models as pickled bytes
CREATE TABLE IF NOT EXISTS agent_ml_models (
    id SERIAL PRIMARY KEY,
    model_key VARCHAR(50) NOT NULL UNIQUE,
    model_data BYTEA NOT NULL,
    metadata JSONB,
    trained_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════
-- BREAKING NEWS ALERTS LOG
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS agent_breaking_alerts (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    headline TEXT NOT NULL,
    velocity_ratio FLOAT NOT NULL DEFAULT 0,
    urgency_score FLOAT NOT NULL DEFAULT 0,
    scan_triggered BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_breaking_created ON agent_breaking_alerts(created_at DESC);

-- Initialize agent portfolio if not exists
INSERT INTO agent_portfolio (cash_balance) VALUES (100000)
ON CONFLICT DO NOTHING;
