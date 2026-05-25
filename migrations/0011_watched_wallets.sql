-- Migration 0011: Watched wallets for copy-trading functionality
CREATE TABLE IF NOT EXISTS watched_wallets (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  wallet_address TEXT NOT NULL,
  label TEXT,
  min_trade_size_sol REAL DEFAULT 0.05,
  min_success_rate REAL DEFAULT 0.6,
  max_copy_amount_sol REAL DEFAULT 0.5,
  is_active INTEGER DEFAULT 1,
  added_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS watched_user_id_idx ON watched_wallets(user_id);
CREATE INDEX IF NOT EXISTS watched_wallet_idx ON watched_wallets(wallet_address);
