-- Migration 0007: Positions for open/closed holdings with TP/SL/trailing
CREATE TABLE IF NOT EXISTS positions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  token_mint TEXT NOT NULL REFERENCES tokens(mint),
  strategy_id TEXT REFERENCES strategies(id),
  entry_price_sol REAL NOT NULL,
  amount_token REAL NOT NULL,
  amount_sol_invested REAL NOT NULL,
  current_price_sol REAL DEFAULT 0,
  unrealized_pnl_sol REAL DEFAULT 0,
  realized_pnl_sol REAL DEFAULT 0,
  stop_loss_price REAL,
  take_profit_price REAL,
  trailing_stop_percent REAL DEFAULT 0,
  status TEXT DEFAULT 'open' CHECK(status IN ('open', 'closed', 'partial')),
  opened_at TEXT DEFAULT CURRENT_TIMESTAMP,
  closed_at TEXT,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS positions_user_id_idx ON positions(user_id);
CREATE INDEX IF NOT EXISTS positions_token_mint_idx ON positions(token_mint);
CREATE INDEX IF NOT EXISTS positions_status_idx ON positions(status);
