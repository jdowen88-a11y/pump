# Simulation Data

## 500-Round Soft Mode — Seed-Only Wallet Strategy

| File | Description |
|---|---|
| `500_rounds_withdrawal_log.csv` | Full per-sweep withdrawal log (1,199 events) |
| `500_rounds_summary.csv` | High-level summary stats |
| `500_rounds_detail.csv` | Per-round breakdown |

### Key Results
- **Rounds:** 500
- **Trades:** 1,483 | **Win rate:** 85.64%
- **Moonshots:** 411
- **Total withdrawn:** $8,804.75
- **Wallet resets:** 1,199
- **Net PnL:** +$8,804.75

### Strategy
`KEEP_SEED_ONLY = True` — after every profitable trade, all gains above the $100 seed are swept to the withdrawal wallet. The active trading wallet resets to $100.00 every time.
