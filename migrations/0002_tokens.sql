CREATE TABLE IF NOT EXISTS tokens (
mint TEXT PRIMARY KEY,
name TEXT,
symbol TEXT,
pumpfun_id TEXT,
creator_address TEXT,
created_at_chain DATETIME,
first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
score REAL DEFAULT 0,
volume_24h REAL DEFAULT 0,
holder_count INTEGER DEFAULT 0,
buy_count INTEGER DEFAULT 0,
sell_count INTEGER DEFAULT 0,
buy_volume_24h REAL DEFAULT 0,
sell_volume_24h REAL DEFAULT 0,
scam_score REAL DEFAULT 0,
rsi REAL,
macd REAL,
macd_signal REAL,
volume_spike REAL,
pattern TEXT,
chart_data TEXT
);

CREATE INDEX idx_tokens_score ON tokens(score DESC);
CREATE INDEX idx_tokens_volume ON tokens(volume_24h DESC);
CREATE INDEX idx_tokens_first_seen ON tokens(first_seen DESC);