# sim/

Realistic pump.fun simulation engine with full execution friction.

## Files

| File | Purpose |
|---|---|
| `realistic_sim.py` | Full sim engine — run standalone or import |
| `__init__.py` | Package exports |

## Usage

```bash
# Run 500 rounds from CLI
python -m sim.realistic_sim
```

```python
# Import in your own script
from sim.realistic_sim import run

result = run(
    rounds=500,
    seed=2026,
    keep_seed_only=True,
    bet_usd=17.50,
    entry_score_min=65
)
print(f"Net PnL: ${result['net_pnl']}")
print(f"Withdrawn: ${result['withdrawn']} across {result['resets']} resets")
```

## Friction Parameters

| Parameter | Default | What it models |
|---|---|---|
| `RPC_FAILURE_RATE` | 10% | Txns dropped, gas still charged |
| `MEV_SANDWICH_RATE` | 20% | Buy sandwiched, +8% slippage |
| `BASE_SLIPPAGE` | 2.5% | Always present |
| `PARTIAL_FILL_RATE` | 6% | Only 55% of buy fills |
| `GAS_FEE_SOL` | 0.003 | ~$0.525/tx at $175 SOL |
| `LATENCY_MISS_RATE` | 15% | Late entry, worse curve position |
| `RUG_RATE` | 22% | Mid-hold rug collapse |
| `DEV_DUMP_RATE` | 18% | Dev sells into your hold |

## Recommendations to Improve Live Results

- **Raise `bet_usd` to $35–50** — cuts gas overhead from 3% to 1.5%
- **Use Jito bundles** — eliminates MEV sandwiching entirely
- **Use Helius/Triton RPC** — cuts RPC failure rate from 10% to ~2%
- **Raise `entry_score_min` to 70** — fewer but cleaner entries
- **Start with $250–500 seed** — survives gas bleed long enough for moonshots
