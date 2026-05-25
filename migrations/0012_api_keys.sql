-- Migration 0012: API keys for programmatic access and integrations
CREATE TABLE IF NOT EXISTS api_keys (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  key_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  permissions TEXT,
  last_used_at TEXT,
  expires_at TEXT,
  is_active INTEGER DEFAULT 1,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS apikeys_user_id_idx ON api_keys(user_id);
