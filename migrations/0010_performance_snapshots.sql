-- Migration 0010: Periodic performance snapshots for equity curves and reporting
CREATE TABLE IF NOT EXISTS performance_snapshots (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  snapshot_at TEXT DEFAULT CURRENT_TIMESTAMP,
  total_equity_sol REAL DEFAULT 0,
  realized_pnl_sol REAL DEFAULT 0,
  unrealized_pnl_sol REAL DEFAULT 0,
  open_positions_count INTEGER DEFAULT 0,
  daily_pnl_sol REAL DEFAULT 0,
  metrics TEXT
);

CREATE INDEX IF NOT EXISTS perf_user_id_idx ON performance_snapshots(user_id);
CREATE INDEX IF NOT EXISTS perf_snapshot_at_idx ON performance_snapshots(snapshot_at);
