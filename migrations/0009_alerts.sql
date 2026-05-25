-- Migration 0009: Alerts and notifications history
CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  type TEXT NOT NULL CHECK(type IN ('new_token', 'trade_fill', 'tp_hit', 'sl_hit', 'risk_breach', 'system', 'copy_trade_signal')),
  condition TEXT,
  message TEXT NOT NULL,
  triggered_at TEXT DEFAULT CURRENT_TIMESTAMP,
  is_read INTEGER DEFAULT 0,
  channel TEXT DEFAULT 'in_app' CHECK(channel IN ('telegram', 'discord', 'email', 'push', 'in_app'))
);

CREATE INDEX IF NOT EXISTS alerts_user_id_idx ON alerts(user_id);
CREATE INDEX IF NOT EXISTS alerts_triggered_at_idx ON alerts(triggered_at);
