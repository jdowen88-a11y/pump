CREATE TABLE IF NOT EXISTS user_settings (
user_id TEXT PRIMARY KEY REFERENCES users(id),
auto_trade BOOLEAN DEFAULT 1,
max_buy_sol REAL DEFAULT 0.1,
min_score INTEGER DEFAULT 60,
slippage_percent INTEGER DEFAULT 10,
max_slippage_percent INTEGER DEFAULT 25,
take_profit_percent REAL DEFAULT 50,
stop_loss_percent REAL DEFAULT 20,
notifications_enabled BOOLEAN DEFAULT 1,
push_token TEXT,
created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);