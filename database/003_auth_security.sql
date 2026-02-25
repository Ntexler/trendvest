-- TrendVest — Auth & Security Migration
-- Adds role-based access, 2FA (TOTP), rate limiting, audit logging

-- ══════════════════════════════════════
-- USER ROLE & 2FA
-- ══════════════════════════════════════

ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user'
    CHECK (role IN ('user', 'admin', 'moderator'));

ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret VARCHAR(64) DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INT DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ DEFAULT NULL;

-- Index for role-based queries
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ══════════════════════════════════════
-- AUDIT LOG
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(200),
    ip_address VARCHAR(45),
    user_agent TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);

-- ══════════════════════════════════════
-- RATE LIMIT TRACKING
-- ══════════════════════════════════════

CREATE TABLE IF NOT EXISTS rate_limit_hits (
    id BIGSERIAL PRIMARY KEY,
    key VARCHAR(200) NOT NULL,
    hit_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_key ON rate_limit_hits(key, hit_at);
