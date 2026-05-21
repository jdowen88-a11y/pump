CREATE TABLE IF NOT EXISTS trades (
id TEXT PRIMARY KEY,
user_id TEXT NOT NULL REFERENCES users(id),
token_mint TEXT NOT NULL REFERENCES tokens(mint),
action TEXT NOT NULL CHECK(action IN ('buy', 'sell')),
amount_sol REAL NOT NULL,
amount_token REAL,
price_sol REAL,
slippage REAL,
tx_signature TEXT,
profit_sol REAL,
status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'failed')),
executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_user ON trades(user_id, executed_at DESC);
CREATE INDEX idx_trades_token ON trades(token_mint, executed_at DESC);