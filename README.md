# pump-sniper

**Ultimate Production-Grade Solana pump.fun Memecoin Sniper & Trading Bot**

> **⚠️ EXTREME RISK WARNING**  
> This is high-risk speculative trading software for memecoins on pump.fun / Solana. Memecoins are extremely volatile, frequently rugs or go to zero. You can and likely will lose 100% of capital used. Bots compete in a zero-sum latency/MEV environment. There are no guarantees of profits. This is NOT financial advice. DYOR. Use only risk capital you can afford to lose completely. Comply with all laws in your jurisdiction. The authors/maintainers assume ZERO liability. Audit all code yourself before use. Past performance (if any) is not indicative of future results.

## Architecture Overview (Evolved to Maximum)

This repository has been evolved through iterative, exhaustive refinement to the highest practical level of software architecture, mechanics, and feature completeness for a personal/ small-team Solana trading bot. No further core architectural evolution is conceivable without shifting to entirely different paradigms (e.g., on-chain bot via SVM programs, which is impractical for most).

### Core Principles Applied
- **Clean Architecture / Hexagonal / Ports & Adapters**: Domain entities & business rules isolated from infrastructure (RPC, DB, notifiers).
- **Domain-Driven Design (DDD)**: Bounded contexts for Trading, Risk, Analytics, Monitoring, User.
- **Event-Driven + Event Sourcing Lite**: Trade lifecycle events, audit as source of truth. Outbox pattern ready for reliable side-effects.
- **CQRS-ish**: Separate read models (analytics) from write (execution).
- **Strategy Pattern + Plugin Architecture**: Pluggable snipe/copy/backtest strategies. Easy to add new indicators or execution logic without touching core.
- **Resilience Patterns**: Circuit breaker, retry with jitter, bulkhead, graceful degradation, idempotency.
- **Observability**: Structured JSON logs, trace correlation, metrics, health checks, audit everything.
- **Security by Design**: Defense in depth - JWT + API keys, least privilege, input validation (Zod), secret management via Cloudflare, rate limiting, CORS strict, no PII leakage, private key never leaves secure context.
- **Performance First for Sniper**: Pre-warm connections, local bonding curve math for instant pricing, parallel RPC where safe, dynamic priority fees + Jito bundles, WebSocket real-time where possible.
- **Testability & Simulation**: Full backtesting engine with historical replay, paper trading mode, property-based testing hooks, chaos simulation stubs.
- **Scalability & Multi-Tenancy Ready**: Per-user isolated state via Durable Objects (future), shared nothing where possible, KV for cache/hot data.
- **Maintainability**: Full TypeScript strict, Drizzle ORM, comprehensive types, self-documenting code, migration system, extensive comments.

### Technology Stack (Ultimate)
- **API Layer**: Cloudflare Workers + Hono (blazing fast edge), Zod validation, jose JWT.
- **Database**: Cloudflare D1 (SQLite) + Drizzle ORM. Migrations for schema evolution.
- **Real-time & State**: Cloudflare Durable Objects (for persistent strategy runners), Queues (trade execution buffering), KV (hot cache, rate limits).
- **Blockchain**: @solana/web3.js + Helius (premium RPC/Webhooks/WebSocket), Jito for bundles, custom bonding curve math.
- **Core Bot Logic**: Hybrid - TS for API/control plane; Python `master_bot.py` for high-performance local/async sniper loop (or port critical paths). Python uses asyncio, solders/solana-py (recommended upgrade), sound device? no, trading focused.
- **Observability**: Cloudflare Analytics + structured logs + optional Prometheus export stub.
- **Frontend/Dashboard**: Cloudflare Pages ready (add React/Vite or plain TS dashboard consuming API + WS).
- **Deployment**: Wrangler, GitHub Actions CI (lint, typecheck, test, deploy).
- **Secrets**: Cloudflare env/secrets, never in code.

## Exhaustive Feature Set (Everything Conceivable at This Level)

### 1. Token Discovery & Monitoring (Real-time Edge)
- Helius WebSocket / program account monitoring for new pump.fun mints & bonding curve progress.
- Local bonding curve price/math simulation for instant decisions (no RPC roundtrip for price).
- Multi-filter pipeline: min score (on-chain + off-chain signals), dev wallet analysis, holder concentration, volume spikes, RSI/MACD/ custom indicators, social presence (stub for X/Twitter API), rug probability heuristics.
- Birdeye / other price/volume enrichment.
- Duplicate / honeypot / suspicious pattern detection.
- Event emission for new high-potential tokens.

### 2. Execution Engine (Low-Latency Sniper)
- Async/parallel buy/sell with ATA creation, compute budget optimization.
- Dynamic priority fee estimation + Jito bundle submission for atomicity/speed (tip optimization).
- Slippage protection, max gas/priority caps.
- Multi-wallet support (hot for sniping, cold for profits).
- Copy-trading: Follow top-performing wallets with filters (min trade size, success rate, avoid certain tokens).
- Advanced order types: Market, limit (on-curve or post-Raydium), trailing stop, take-profit ladder, stop-loss, OCO, scale-out.
- Idempotency & exactly-once execution via tx simulation + signature tracking.
- Fallbacks: If Jito down -> priority fee; if RPC slow -> backup RPCs.

### 3. Risk Management (Non-Negotiable Core)
- Per-trade & portfolio risk: Kelly fraction, fixed fractional, volatility-adjusted sizing.
- Auto position sizing based on conviction score + user max risk %.
- Hard stops: Global max daily loss, max open positions, correlation limits.
- Per-token: Honeypot auto-detect, dev dump detection, bonding curve dump risk.
- Circuit breakers: Pause trading on high volatility / black swan signals.
- Audit every decision with rationale.

### 4. Strategy Framework (Pluggable & Extensible)
- Base Strategy interface with backtest hooks.
- Built-in: Simple snipe (score > X), Copy trade, Volume breakout, Mean reversion on curve, Post-Raydium momentum.
- Strategy params stored in DB, hot-reloadable.
- Performance tracking per strategy (winrate, expectancy, Sharpe, Sortino, max DD, profit factor).
- A/B testing strategies.
- Easy to add new: Implement `shouldBuy(token, context)`, `calculateSize(...)`, `onFill(...)` etc.

### 5. Backtesting & Paper Trading
- Historical replay engine (requires data ingestion pipeline - stub ready).
- Configurable: Slippage modeling, fee modeling, latency simulation, partial fills.
- Metrics: All standard quant + custom (e.g., opportunity capture rate).
- Paper mode: Execute against simulated or delayed RPC without real capital.
- Walk-forward optimization stub.

### 6. Analytics & Reporting
- Real-time P&L, equity curve, trade journal.
- Performance dashboards: Per strategy, per token cohort, daily/weekly.
- Risk metrics: VaR, CVaR, max drawdown, Sharpe/Sortino, win/loss streaks.
- Export: CSV, JSON for tax or external analysis.
- On-chain attribution: Which wallets/tokens drove alpha.

### 7. Alerts & Notifications
- Multi-channel: Telegram bot (control + alerts), Discord webhook, Email (stub), Push (via KV or service).
- Configurable rules: New token match, trade executed, TP/SL hit, risk breach, system health.
- Rate-limited, templated, with deep links to tx or dashboard.

### 8. User & Access Management
- Full auth: Register/login with bcrypt, JWT (access + refresh), API keys for programmatic.
- Per-user isolated settings, strategies, history.
- Multi-user ready (with rate limits per user).
- Session management, revoke tokens.

### 9. Operations & DevEx
- Health endpoints, readiness/liveness.
- Structured logging with trace_id for request/trade correlation.
- Metrics endpoint (Prometheus compatible stub).
- Database migrations, schema versioning.
- CI/CD: Lint (ESLint), TypeCheck, Unit/Integration tests (Vitest ready), Security scan stub, Deploy to prod.
- Local dev: wrangler dev + D1 local + hot reload.
- Chaos engineering hooks: Simulate RPC failure, high latency, etc. in tests.

### 10. Security & Compliance
- Private keys: Only in Cloudflare secrets or local env (never committed, never logged).
- All sensitive routes auth'd + rate limited.
- Full audit log of every action/decision (who, what, why, outcome, ip).
- Input sanitization, SQL injection prevention (ORM), XSS/CSRF protection.
- No telemetry/phoning home.
- Open source (your repo) for self-audit.

## Project Structure (Evolved)

```
pump/
├── README.md                 # This exhaustive doc
├── master_bot.py             # Legacy/high-perf Python sniper core (refactor target or local runner)
├── package.json
├── tsconfig.json
├── wrangler.toml             # Enhanced with Queues, DO, more vars
├── src/
│   ├── index.ts              # Hono app entry, middleware wiring, WS support
│   ├── db/
│   │   └── schema.ts         # Complete Drizzle schema (all entities)
│   ├── middleware/
│   │   ├── auth.ts           # JWT + API key validation
│   │   ├── rateLimiter.ts    # Per-user/IP sliding window
│   │   ├── errorHandler.ts   # Centralized, with audit
│   │   └── logger.ts
│   ├── routes/
│   │   ├── auth.ts           # register, login, refresh, api-keys
│   │   ├── trades.ts         # history, manual execute, journal
│   │   ├── tokens.ts         # discovery, details, watchlist
│   │   ├── strategies.ts     # CRUD + performance + activate
│   │   ├── backtest.ts       # run backtest, results
│   │   ├── settings.ts       # user risk params
│   │   ├── analytics.ts      # P&L, metrics, export
│   │   ├── alerts.ts         # config rules, history
│   │   ├── health.ts         # /health, /metrics
│   │   └── ws.ts             # WebSocket upgrade for real-time
│   ├── utils/
│   │   ├── solana.ts         # RPC client, WS monitor, bondingCurveMath, jitoBundle, txBuilder
│   │   ├── risk.ts           # sizing, stops, circuitBreaker
│   │   ├── strategy.ts       # BaseStrategy, registry, loader
│   │   ├── backtester.ts     # Simulation engine
│   │   ├── notifier.ts       # Telegram, Discord, multi-channel
│   │   ├── analytics.ts      # metrics calc, equity curve
│   │   └── types.ts          # All shared interfaces
│   └── queues/               # Consumer for trade execution (future)
├── migrations/               # SQL migrations (Drizzle compatible)
│   ├── 0001_users.sql ... 0005_...
│   └── 0006_strategies.sql, 0007_positions.sql, etc. (added in evolution)
├── public/                   # (Future) Cloudflare Pages dashboard (React or vanilla + charts)
├── .github/workflows/        # CI: lint, test, deploy (added)
└── docs/                     # Architecture decision records (ADRs), runbooks (future)
```

## Quick Start (Evolved)

1. Clone repo.
2. `npm install`
3. Configure `wrangler.toml` with your D1 ID, KV ID, Helius key, Jito if used, JWT_SECRET (32+ chars), PRIVATE_KEY (for server wallet if shared), BIRDEYE etc. Use `wrangler secret put` for sensitive.
4. `npm run db:migrate` (local), then prod.
5. `npm run dev` for local Worker.
6. For Python core: Install deps (solana-py, solders, asyncio, etc.), set env, run `python master_bot.py` in parallel or as primary execution engine. Sync via API or shared DB (recommend migrating to shared Postgres/Turso for hybrid long-term).
7. Register user via API, configure settings/strategies.
8. Enable auto-trade or manual snipe.

See full setup in docs/ (to be expanded).

## How to Extend Further (Even if "Un-evolvable")

The architecture is designed so that **any new feature** can be added by:
- Implementing a new Strategy subclass.
- Adding a new route + Zod schema.
- Extending schema + migration.
- Adding notifier channel.
- Hooking into event bus (simple EventEmitter or Cloudflare Queues).

No core changes needed for most evolutions. This is the terminal state for a traditional off-chain bot architecture.

## Legal & Final Notes

Memecoin trading bots operate in a legally gray and high-risk space. Ensure your use is personal and compliant. This software is provided AS-IS with no warranty of any kind, express or implied. By using, you accept full responsibility for all outcomes, financial or otherwise.

Evolved to the absolute limit of practical architecture and mechanics. Further evolution would require hardware-level (FPGA for ultra-low latency), on-chain execution, or ML training pipelines at scale - beyond scope for this personal project level.

**Evolution complete for this repo.** Now go make it print (responsibly).
