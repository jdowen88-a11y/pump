# =============================================================================
# sim/realistic_sim.py
# Realistic pump.fun simulation with full execution friction:
#   - RPC failures (gas burned, tx dropped)
#   - MEV sandwich attacks (+8% slippage)
#   - Base slippage (2.5% always)
#   - Partial fills (6% of buys)
#   - Latency misses (15% miss early curve)
#   - Mid-hold rugs (22% of passing tokens)
#   - Dev dumps mid-hold
#   - Gas fees per tx (~$0.525)
#   - Seed-only wallet reset + withdrawal log
# =============================================================================

import random
import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Tuple, Optional

# ---------------------------------------------------------------------------
# CONFIG — tune these to match your live setup
# ---------------------------------------------------------------------------

SEED_USD            = 100.0
BET_USD             = 17.50
SOL_PRICE_USD       = 175.0
BUY_SOL             = BET_USD / SOL_PRICE_USD
ROUNDS              = 500
SIM_SEED            = 42

# Scoring
ENTRY_SCORE_MIN     = 65       # raise to 70 with Jito/Helius
MAX_DEV_WALLET_LOW  = 3.0
MAX_DEV_WALLET_MED  = 8.0
MAX_SNIPER_LOW      = 2
MAX_SNIPER_MED      = 5
GRAD_PCT_EARLY      = 15.0
GRAD_PCT_MID        = 35.0

# Exit thresholds
QUICK_FLIP_TARGET   = 1.10
STRONG_RIDE_TARGET  = 1.25
VIRAL_RIDE_TARGET   = 1.40
STRONG_TRAIL_PCT    = 0.91
VIRAL_TRAIL_PCT     = 0.90
BASE_TRAIL_PCT      = 0.92
LOSS_CUT_PCT        = 0.88
MOONSHOT_TRAIL_PCT  = 0.94
MOONSHOT_HARDCAP    = 8.0
MOONSHOT_LOWER_HIGHS = 2
MOONSHOT_VOL_FADE  = 0.85

# Execution friction
RPC_FAILURE_RATE      = 0.10   # 10% txns dropped (gas still charged)
MEV_SANDWICH_RATE     = 0.20   # 20% buys sandwiched
MEV_SLIPPAGE          = 0.08   # +8% when sandwiched
BASE_SLIPPAGE         = 0.025  # 2.5% always
PARTIAL_FILL_RATE     = 0.06   # 6% partial fills
PARTIAL_FILL_PCT      = 0.55   # partial = 55% of intended
GAS_FEE_SOL           = 0.003  # ~$0.525/tx
LATENCY_MISS_RATE     = 0.15   # 15% miss early curve entry
LATENCY_CURVE_PENALTY = 0.12   # price momentum penalty on late entry
RUG_RATE              = 0.22   # 22% of tokens rug mid-hold
RUG_RECOVERY          = (0.04, 0.14)
DEV_DUMP_RATE         = 0.18
DEV_DUMP_HIT          = (0.25, 0.55)
TOKENS_PER_ROUND      = (6, 14)
SPIKE_DECAY           = {"weak":0.97,"moderate":0.95,"strong":0.92,"viral":0.88}
TOKEN_DIST            = ["weak","weak","weak","moderate","moderate","moderate","strong","viral"]

# Withdrawal
KEEP_SEED_ONLY        = True
WITHDRAWAL_LOG_FILE   = "withdrawal_log.csv"

# ---------------------------------------------------------------------------
# DATA CLASSES
# ---------------------------------------------------------------------------

@dataclass
class BondingCurve:
    virtual_sol: float = 30.0
    virtual_tokens: float = 1_000_000_000.0
    real_sol: float = 0.0

    def graduation_pct(self) -> float:
        return min(100.0, self.real_sol / 69.0 * 100.0)

    def buy(self, sol_in: float) -> float:
        if sol_in <= 0: return 0.0
        tokens_out = self.virtual_tokens - (
            (self.virtual_sol * self.virtual_tokens) / (self.virtual_sol + sol_in)
        )
        self.virtual_sol += sol_in
        self.virtual_tokens -= tokens_out
        self.real_sol += sol_in
        return tokens_out


@dataclass
class TokenProfile:
    name: str
    hype_score: float
    dev_wallet_pct: float
    sniper_count: int
    buy_pressure: str
    narrative: str
    launch_wave: str


# ---------------------------------------------------------------------------
# TOKEN GENERATOR
# ---------------------------------------------------------------------------

def generate_token(index: int) -> TokenProfile:
    return TokenProfile(
        name=f"TKN_{index}",
        hype_score=round(random.uniform(0.05, 1.0), 2),
        dev_wallet_pct=round(random.uniform(0.5, 30.0), 1),
        sniper_count=random.randint(0, 15),
        buy_pressure=random.choice(TOKEN_DIST),
        narrative=random.choice(["AI","meme","animal","political","random","random"]),
        launch_wave=random.choice(["first_30s","first_30s","1min","1min","late"])
    )


# ---------------------------------------------------------------------------
# SCORING ENGINE
# ---------------------------------------------------------------------------

def research_score(token: TokenProfile, curve: BondingCurve) -> float:
    s = 0
    s += 25 if token.dev_wallet_pct < MAX_DEV_WALLET_LOW \
         else 15 if token.dev_wallet_pct < MAX_DEV_WALLET_MED \
         else 5  if token.dev_wallet_pct < 15 else 0
    s += 20 if token.sniper_count <= MAX_SNIPER_LOW \
         else 10 if token.sniper_count <= MAX_SNIPER_MED \
         else 3  if token.sniper_count <= 10 else 0
    s += {"weak":0,"moderate":15,"strong":25,"viral":35}[token.buy_pressure]
    s += 15 if token.hype_score > 0.75 else 8 if token.hype_score > 0.45 else 0
    g = curve.graduation_pct()
    s += 15 if g < GRAD_PCT_EARLY else 8 if g < GRAD_PCT_MID else 0
    return s


# ---------------------------------------------------------------------------
# PRICE SIMULATOR (realistic)
# ---------------------------------------------------------------------------

def simulate_price(token: TokenProfile, curve_penalty: float = 0.0) -> Tuple[list, float, list]:
    p    = {"weak":0.25,"moderate":0.6,"strong":1.3,"viral":2.6}[token.buy_pressure]
    h    = token.hype_score * 1.3
    drag = min(0.7, token.sniper_count * 0.055)
    mom  = max(0.0, (p + h) / 2 - drag - curve_penalty)
    decay = SPIKE_DECAY[token.buy_pressure]

    cur = 1.0; peak = 1.0
    path = [(0.0, 1.0)]; vols = [1.0]; pv = 1.0
    rug_tick = random.randint(3, 18) if random.random() < RUG_RATE else None

    for tick in range(1, 25):
        t = tick * 5.0
        mom *= decay
        delta = random.gauss(mom * 0.07, 0.07)
        sniper_sell = -drag * 0.13 if t <= 20 else 0.0
        dev_dump = 0.0
        if cur > 1.3 and random.random() < DEV_DUMP_RATE:
            dev_dump = -random.uniform(*DEV_DUMP_HIT)
        if rug_tick and tick >= rug_tick:
            cur = max(0.03, cur * random.uniform(*RUG_RECOVERY))
            peak = max(peak, cur)
            path.append((t, round(cur, 4)))
            vols.append(0.04)
            break
        cur  = max(0.04, cur + delta + sniper_sell + dev_dump)
        peak = max(peak, cur)
        pv   = max(0.1, pv + random.gauss(mom * 0.09, 0.07))
        path.append((t, round(cur, 4)))
        vols.append(round(pv, 4))

    return path, peak, vols


# ---------------------------------------------------------------------------
# EXIT ENGINE
# ---------------------------------------------------------------------------

def compute_exit(path: list, vols: list, token: TokenProfile, sc: float) -> Tuple[float, str, float]:
    viral  = token.buy_pressure == "viral"  and sc >= 70
    strong = token.buy_pressure == "strong" and sc >= 65
    bt     = VIRAL_RIDE_TARGET if viral else STRONG_RIDE_TARGET if strong else QUICK_FLIP_TARGET
    trail  = VIRAL_TRAIL_PCT   if viral else STRONG_TRAIL_PCT   if strong else BASE_TRAIL_PCT

    peak = 1.0; moon = False; ph = 1.0; lows = 0

    for i, (t, m) in enumerate(path[1:], 1):
        vol  = vols[i] if i < len(vols) else vols[-1]
        pv   = vols[i-1] if i > 0 else 1.0
        peak = max(peak, m)

        if not moon and m >= bt and (viral or strong) and vol > pv and m >= ph * 0.99:
            moon = True; ph = m; continue

        if moon:
            lows = lows + 1 if m <= ph else 0
            ph   = max(ph, m)
            if lows >= MOONSHOT_LOWER_HIGHS and vol < pv * MOONSHOT_VOL_FADE:
                return m, "MOONSHOT_EXIT", t
            if m >= MOONSHOT_HARDCAP:
                return m, "MOONSHOT_HARDCAP_8x", t
            if m < peak * MOONSHOT_TRAIL_PCT:
                return m, "MOONSHOT_TRAIL", t
            continue

        if m >= bt:
            label = "VIRAL_RIDE" if viral else "STRONG_RIDE" if strong else "QUICK_FLIP"
            return m, label, t
        if peak > 1.05 and m < peak * trail:
            return m, "TRAIL_STOP", t
        if m < LOSS_CUT_PCT:
            return m, "LOSS_CUT", t
        ph = m

    return path[-1][1], "TIME_EXIT", path[-1][0]


# ---------------------------------------------------------------------------
# WITHDRAWAL LOG
# ---------------------------------------------------------------------------

def init_withdrawal_log(filepath: str = WITHDRAWAL_LOG_FILE):
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    with open(filepath, "w", newline="") as f:
        csv.writer(f).writerow([
            "timestamp", "round", "token", "exit_reason",
            "trade_pnl_usd", "amount_withdrawn_usd",
            "active_wallet_after", "cumulative_withdrawn_usd", "reset_count"
        ])


def append_withdrawal(filepath: str, row: dict):
    with open(filepath, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            row["round"], row["token"], row["exit_reason"],
            round(row["trade_pnl_usd"], 2),
            round(row["amount_withdrawn_usd"], 2),
            round(row["active_wallet_after"], 2),
            round(row["cumulative_withdrawn_usd"], 2),
            row["reset_count"]
        ])


# ---------------------------------------------------------------------------
# MAIN SIMULATION RUNNER
# ---------------------------------------------------------------------------

def run(
    rounds: int = ROUNDS,
    seed: int = SIM_SEED,
    keep_seed_only: bool = KEEP_SEED_ONLY,
    withdrawal_log: str = WITHDRAWAL_LOG_FILE,
    entry_score_min: int = ENTRY_SCORE_MIN,
    bet_usd: float = BET_USD
) -> dict:
    """
    Run the realistic simulation.

    Returns a dict with:
      rounds_completed, seen, skipped, traded, wins, losses, win_rate,
      moon, rpc_fails, mev_hits, rugs, partial_fills, latency_misses,
      total_gas_usd, active, withdrawn, resets, total_value, net_pnl,
      withdrawal_events (list of dicts)
    """
    random.seed(seed)
    buy_sol = bet_usd / SOL_PRICE_USD
    gas_usd = GAS_FEE_SOL * SOL_PRICE_USD

    active    = SEED_USD
    withdrawn = 0.0
    seen = skipped = traded = wins = losses = moon = 0
    rpc_fails = mev_hits = rugs = partial = latency = resets = 0
    total_gas = 0.0
    tc        = 0
    round_rows: List[dict] = []
    withdrawal_events: List[dict] = []

    if keep_seed_only:
        init_withdrawal_log(withdrawal_log)

    for r in range(1, rounds + 1):
        n = random.randint(*TOKENS_PER_ROUND)
        rpn = 0.0; rtr = 0

        for _ in range(n):
            tc += 1; seen += 1
            token = generate_token(tc)
            curve = BondingCurve()
            for _ in range(random.randint(0, 12)):
                curve.buy(random.uniform(0.02, 0.45))

            sc = research_score(token, curve)
            if sc < entry_score_min:
                skipped += 1; continue
            if active < bet_usd:
                break

            # RPC failure
            if random.random() < RPC_FAILURE_RATE:
                rpc_fails += 1
                active -= gas_usd; total_gas += gas_usd; continue

            # Latency miss
            cp = LATENCY_CURVE_PENALTY if random.random() < LATENCY_MISS_RATE else 0.0
            if cp: latency += 1

            # MEV + slippage
            mev  = random.random() < MEV_SANDWICH_RATE
            if mev: mev_hits += 1
            slip = BASE_SLIPPAGE + (MEV_SLIPPAGE if mev else 0.0)

            # Partial fill
            fill = PARTIAL_FILL_PCT if random.random() < PARTIAL_FILL_RATE else 1.0
            if fill < 1.0: partial += 1

            # Deduct gas
            active -= gas_usd; total_gas += gas_usd
            if active < 0: active = 0.0; break

            effective_usd = bet_usd * fill * (1.0 - slip)
            curve.buy(buy_sol * fill)
            path, peak, vols = simulate_price(token, cp)
            mult, reason, et = compute_exit(path, vols, token, sc)

            if mult < 0.15: rugs += 1
            pnl    = round(effective_usd * (mult - 1.0), 2)
            active += pnl; traded += 1; rtr += 1; rpn += pnl

            if pnl > 0: wins += 1
            else:       losses += 1
            if "MOONSHOT" in reason: moon += 1

            # Withdrawal sweep
            if keep_seed_only and active > SEED_USD:
                swept      = round(active - SEED_USD, 2)
                withdrawn += swept
                active     = SEED_USD
                resets    += 1
                event = {
                    "round": r, "token": token.name, "exit_reason": reason,
                    "trade_pnl_usd": pnl, "amount_withdrawn_usd": swept,
                    "active_wallet_after": active,
                    "cumulative_withdrawn_usd": round(withdrawn, 2),
                    "reset_count": resets
                }
                withdrawal_events.append(event)
                append_withdrawal(withdrawal_log, event)

        round_rows.append({
            "round": r, "seen": n, "traded": rtr,
            "round_pnl": round(rpn, 2),
            "active_wallet": round(active, 2),
            "withdrawn": round(withdrawn, 2),
            "resets": resets
        })
        if active < bet_usd:
            break

    return {
        "rounds_completed":  len(round_rows),
        "seen":              seen,
        "skipped":           skipped,
        "traded":            traded,
        "wins":              wins,
        "losses":            losses,
        "win_rate":          round(wins / max(traded, 1) * 100, 2),
        "moon":              moon,
        "rpc_fails":         rpc_fails,
        "mev_hits":          mev_hits,
        "rugs":              rugs,
        "partial_fills":     partial,
        "latency_misses":    latency,
        "total_gas_usd":     round(total_gas, 2),
        "active":            round(active, 2),
        "withdrawn":         round(withdrawn, 2),
        "resets":            resets,
        "total_value":       round(active + withdrawn, 2),
        "net_pnl":           round((active + withdrawn) - SEED_USD, 2),
        "round_detail":      round_rows,
        "withdrawal_events": withdrawal_events,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    result = run()
    events = result.pop("withdrawal_events")
    detail = result.pop("round_detail")
    print(json.dumps(result, indent=2))
    print(f"\nWithdrawal events: {len(events)}")
    if events:
        top = sorted(events, key=lambda x: x["amount_withdrawn_usd"], reverse=True)[:5]
        print("Top 5 sweeps:")
        for e in top:
            print(f"  Round {e['round']} | {e['token']} | +${e['amount_withdrawn_usd']} | cumulative ${e['cumulative_withdrawn_usd']}")
