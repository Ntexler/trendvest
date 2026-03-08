-- TrendVest AI — Expense Receipt Bot Schema

-- ══════════════════════════════════════
-- EXPENSE RECEIPT TABLES
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS expense_receipts (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(64),

    -- Receipt data
    vendor_name VARCHAR(255) NOT NULL DEFAULT '',
    amount FLOAT NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'ILS',
    receipt_date DATE,
    receipt_number VARCHAR(100) DEFAULT '',
    description TEXT DEFAULT '',

    -- Classification
    category VARCHAR(50) NOT NULL DEFAULT 'other',
    tax_deductible BOOLEAN NOT NULL DEFAULT false,
    deduction_category VARCHAR(50) DEFAULT NULL,
    confidence_score FLOAT NOT NULL DEFAULT 0,

    -- Source
    source_type VARCHAR(20) NOT NULL DEFAULT 'manual'
        CHECK (source_type IN ('screenshot', 'email', 'manual', 'upload')),
    source_ref TEXT DEFAULT '',
    original_filename VARCHAR(255) DEFAULT '',

    -- Image data (base64 or path)
    image_data TEXT DEFAULT '',

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'verified', 'rejected', 'exported')),
    exported_at TIMESTAMPTZ DEFAULT NULL,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Email scan tracking
CREATE TABLE IF NOT EXISTS expense_email_configs (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(64),
    email_address VARCHAR(255) NOT NULL,
    imap_server VARCHAR(255) NOT NULL DEFAULT 'imap.gmail.com',
    imap_port INT NOT NULL DEFAULT 993,
    -- Encrypted credentials stored here
    encrypted_password TEXT NOT NULL DEFAULT '',
    last_scan_at TIMESTAMPTZ DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(session_id, email_address)
);

-- Scan schedule config
CREATE TABLE IF NOT EXISTS expense_scan_schedules (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(64) UNIQUE,
    scan_interval_hours INT NOT NULL DEFAULT 24,
    scan_screenshots BOOLEAN NOT NULL DEFAULT true,
    scan_emails BOOLEAN NOT NULL DEFAULT true,
    screenshot_folder TEXT DEFAULT '',
    last_auto_scan_at TIMESTAMPTZ DEFAULT NULL,
    next_scan_at TIMESTAMPTZ DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ══════════════════════════════════════
-- INDEXES
-- ══════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_expense_receipts_session ON expense_receipts(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_expense_receipts_user ON expense_receipts(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_expense_receipts_status ON expense_receipts(status);
CREATE INDEX IF NOT EXISTS idx_expense_receipts_category ON expense_receipts(category);
CREATE INDEX IF NOT EXISTS idx_expense_receipts_date ON expense_receipts(receipt_date DESC);
CREATE INDEX IF NOT EXISTS idx_expense_receipts_deductible ON expense_receipts(tax_deductible, category);
