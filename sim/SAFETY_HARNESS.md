# Simulation Safety Harness

This is a deterministic, offline-only safety test. It does not read credentials, make HTTP calls, connect to wallets, submit transactions, or interact with live markets.

## Run

From the repository root:

```bash
python sim/safety_harness.py
python -m unittest discover -s sim -p 'test_*.py'
```

The first command writes `sim/safety_report.json`. Treat that output as disposable test evidence; it is intentionally not committed.

## Current scenarios

- One healthy paper-mode decision is allowed.
- Unauthorized request, invalid configuration, stale telemetry, provider failure, duplicate event, and malformed token data must abort.
- Severe agent disagreement and excessive volatility must hold rather than allow.

## Before any integration

1. Keep live network and credentials disabled.
2. Replace only the inputs to `Scenario` with adapters from the real runtime.
3. Keep the expected fail-closed assertions.
4. Run this suite in CI before merges.
5. Do not use a passing simulation as approval for live financial execution.
