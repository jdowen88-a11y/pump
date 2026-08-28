# pump — Open Weave + Explicit Execution

Experimental Solana/pump.fun research, simulation, dashboard, and trading infrastructure.

> **High-risk software:** memecoin trading can lose all capital. The cognition/modeling field in this repository is open; that does **not** mean market execution is unconstrained. Real orders, wallet use, credentials, position sizing, loss limits, slippage controls, and operator-selected live mode remain explicit external-side-effect boundaries.

## Core architecture rule

Internal modeling is not a permission hierarchy.

**Yin and Yang coexist. Quiet and loud coexist. Conflict is preserved as information. Symbols, hypotheses, metrics, code, and observations may share one modeling surface.**

`presence -> interaction -> emergence -> continuation -> infinity`

No internal signal is sent to rehab, vetoed out of existence, forced through a human-approval gate, or required to beat a confidence threshold merely to remain representable.

## Two different surfaces

### Open internal field

The agent/research layer may:

- represent any signal, including silence;
- preserve Yin and Yang simultaneously;
- record uncertainty, conflict, volatility, surprise, metaphor, and unresolved states;
- compare or weight signals descriptively without selecting which one is *allowed* to exist;
- retain memory only when something has actually been observed or explicitly reflected.

The old `ArbitrationGate` name remains only as a compatibility facade. Its current implementation delegates to `WeaveObserver` and cannot ABORT, veto, trigger rehab, or demand human approval.

The old perpetual `flowstate` timer is gone. `reflect_once()` performs one reflection only when explicitly called. Silence does not need to be filled.

### Explicit external execution

A trade changes money and blockchain state. That is not internal representation. Live execution therefore remains explicit and bounded by normal operational safety:

- `DRY_RUN = True` remains the default in `master_bot.py`;
- live buy/sell functions remain separate execution interfaces;
- balance checks, loss controls, slippage, RPC failure handling, wallet security, authentication, rate limits, and transaction integrity remain intact;
- internal confidence or “resonance” never silently turns itself into a market order;
- no cognition loop is allowed to flip the system into live trading by itself.

This preserves the project rule: **do not turn the key automatically.** The inside can stay fully open without silently mutating the outside.

## Yin / Yang weave

`yin_agent.py` and `yang_agent.py` each return a signal view and optional market-action proposal. `weave_observer.py` preserves both:

```text
Yin -------------------\
                        >--- simultaneous weave ---> observation
Yang ------------------/
```

A proposal such as `BUY`, `HOLD`, `DELAY`, or `SKIP` is descriptive output from that stream. The weave itself produces `external_action=None`.

## Inference

`agents/active_inference_agent.py` tracks `p_G`, volatility, and surprise. Those values are measurements, not eligibility tests. Surprise thresholds may mark an event as salient; they do not determine whether the event may exist in the field.

## Flow memory

`flowstate_agent.py` is explicit rather than perpetual:

- `observe_memory()` loads the latest stored memory;
- `reflect_once()` creates at most one new reflection when called;
- no background thought loop begins on import;
- an empty reflection is valid.

## Simulation and trading engine

`master_bot.py` contains simulation modes, market heuristics, execution modeling, and live-trading stubs. It defaults to dry-run simulation. Market-risk thresholds in this part of the repository protect real capital or model trading mechanics; they are not judgments about whether an internal thought may exist.

## Application stack

The repository also contains a Cloudflare/Hono/TypeScript control plane, database migrations, dashboard assets, simulation tooling, runtime configuration, analytics, and security infrastructure. Authentication and secret handling remain security boundaries, not cognition gates.

## Secrets

Never commit private keys, API credentials, JWT secrets, RPC credentials, or exchange/wallet secrets. Use environment or platform-secret storage.

## Run deliberately

Simulation/research components may be run locally. Before any live-market use, inspect the code and configure the execution layer intentionally. Nothing in the open internal weave is authority to spend funds.

The architecture is intentionally unfinished: unresolved structure is allowed to remain unresolved, and future relationships can emerge without first being forced into the old gate/rehab model.
