-- Migration 0008: Backtests for strategy validation and optimization
CREATE TABLE IF NOT EXISTS backtests (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  strategy_id TEXT REFERENCES strategies(id),
  config TEXT,
  results TEXT,
  total_return REAL DEFAULT 0,
  sharpe REAL DEFAULT 0,
  sortino REAL DEFAULT 0,
  max_drawdown REAL DEFAULT 0,
  win_rate REAL DEFAULT 0,
  profit_factor REAL DEFAULT 0,
  status TEXT DEFAULT 'running' CHECK(status IN ('running', 'completed', 'failed')),
  started_at TEXT DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT
);

CREATE INDEX IF NOT EXISTS backtests_user_id_idx ON backtests(user_id);
