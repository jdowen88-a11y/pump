-- Migration 0006: Add strategies table for pluggable trading strategies
CREATE TABLE IF NOT EXISTS strategies (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('snipe', 'copy_trade', 'volume_breakout', 'mean_reversion', 'post_raydium_momentum', 'custom')),
  params TEXT,
  is_active INTEGER DEFAULT 1,
  priority INTEGER DEFAULT 0,
  win_rate REAL DEFAULT 0,
  expectancy REAL DEFAULT 0,
  sharpe REAL DEFAULT 0,
  max_drawdown REAL DEFAULT 0,
  total_trades INTEGER DEFAULT 0,
  total_profit_sol REAL DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS strategies_user_id_idx ON strategies(user_id);
CREATE INDEX IF NOT EXISTS strategies_type_idx ON strategies(type);
