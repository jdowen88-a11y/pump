# =====================================================================
# master_bot.py — Elite pump.fun Simulation + Live Trading Engine
# =====================================================================
# REALISM_MODE    = "soft"  → friendly sim
# REALISM_MODE    = "full"  → true hell mode (MEV, sub-second, rugs, RPC)
# KEEP_SEED_ONLY  = True    → withdraw all profit above seed after each win
#                             active wallet resets to SEED_USD every time
# HARSH_MODE      = True    → applies 10% harder conditions to soft mode
# DRY_RUN         = True    → simulation only
# DRY_RUN         = False   → live trading (wire up live_* stubs below)
# =====================================================================

import random
import time
import logging
import csv
import os
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("master_bot")

# =====================================================================
# TOP-LEVEL SWITCHES
# =====================================================================

DRY_RUN        = True    # True = sim | False = live
REALISM_MODE   = "soft"  # "soft" | "full"
KEEP_SEED_ONLY = True    # True = sweep all profit above seed each win
HARSH_MODE     = False   # True = 10% harder soft mode conditions

# =====================================================================
# CONFIG
# =====================================================================

SEED_USD        = 100.0
TARGET_USD      = 500.0
BET_USD         = 17.50
ROUNDS          = 100
SOL_PRICE_USD   = 175.0
BUY_SOL         = BET_USD / SOL_PRICE_USD
SIM_RANDOM_SEED = 42

ENTRY_SCORE_MIN    = 55
MAX_DEV_WALLET_LOW = 3.0
MAX_DEV_WALLET_MED = 8.0
MAX_SNIPER_LOW     = 2
MAX_SNIPER_MED     = 5
GRAD_PCT_EARLY     = 15.0
GRAD_PCT_MID       = 35.0

QUICK_FLIP_TARGET  = 1.10
STRONG_RIDE_TARGET = 1.25
VIRAL_RIDE_TARGET  = 1.40
STRONG_TRAIL_PCT   = 0.91
VIRAL_TRAIL_PCT    = 0.90
BASE_TRAIL_PCT     = 0.92
LOSS_CUT_PCT       = 0.88

MOONSHOT_TRAIL_PCT   = 0.94
MOONSHOT_HARDCAP     = 8.0
MOONSHOT_LOWER_HIGHS = 2
MOONSHOT_VOL_FADE    = 0.85

# ── SOFT MODE settings ──────────────────────────────────────────────
SOFT_TOKENS_PER_ROUND   = (4, 10)
SOFT_TICK_SIZE_SEC      = 5.0
SOFT_TICKS              = 24
SOFT_SLIPPAGE_FAIL_RATE = 0.07

# ── HARSH SOFT MODE (+10% difficulty) ───────────────────────────────
HARSH_MULT              = 1.10
HARSH_SLIPPAGE_FAIL     = round(SOFT_SLIPPAGE_FAIL_RATE * HARSH_MULT, 3)
HARSH_SNIPER_DRAG_MULT  = HARSH_MULT
HARSH_PRICE_NOISE_MULT  = HARSH_MULT
HARSH_DEV_DUMP_MULT     = HARSH_MULT
HARSH_HYPE_WEIGHT       = round(1.5 / HARSH_MULT, 4)

# ── FULL REALISM settings ────────────────────────────────────────────
FULL_TOKENS_PER_ROUND   = (80, 300)
FULL_TICK_SIZE_SEC      = 0.5
FULL_TICKS              = 240
MEV_SANDWICH_RATE       = 0.22
MEV_SANDWICH_SLIPPAGE   = 0.08
BASE_SLIPPAGE           = 0.015
RPC_FAILURE_RATE        = 0.09
PARTIAL_FILL_RATE       = 0.06
PARTIAL_FILL_PCT        = 0.55
CONGESTION_DELAY_CHANCE = 0.15
CONGESTION_PRICE_MISS   = 0.12
MID_HOLD_RUG_RATE       = 0.18
MID_HOLD_RUG_WINDOW     = (5, 40)
SPIKE_DECAY = {"weak": 0.97, "moderate": 0.95, "strong": 0.92, "viral": 0.88}

# ── Withdrawal log file ─────────────────────────────────────────────
WITHDRAWAL_LOG_FILE = "withdrawal_log.csv"

# =====================================================================
# BONDING CURVE — exact pump.fun virtual reserves model
# =====================================================================

@dataclass
class BondingCurve:
    virtual_sol: float = 30.0
    virtual_tokens: float = 1_000_000_000.0
    real_sol: float = 0.0
    total_supply: float = 1_000_000_000.0

    def price(self) -> float:
        return self.virtual_sol / self.virtual_tokens

    def market_cap_usd(self) -> float:
        return self.price() * self.total_supply * SOL_PRICE_USD

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

    def sell(self, tokens_in: float) -> float:
        if tokens_in <= 0: return 0.0
        sol_out = self.virtual_sol - (
            (self.virtual_sol * self.virtual_tokens) / (self.virtual_tokens + tokens_in)
        )
        self.virtual_tokens += tokens_in
        self.virtual_sol -= sol_out
        self.real_sol = max(0.0, self.real_sol - sol_out)
        return max(0.0, sol_out)


# =====================================================================
# TOKEN PROFILE
# =====================================================================

@dataclass
class TokenProfile:
    name: str
    hype_score: float
    dev_wallet_pct: float
    sniper_count: int
    buy_pressure: str
    narrative: str
    launch_wave: str


def generate_token_soft(index: int) -> TokenProfile:
    return TokenProfile(
        name=f"TKN_{index}",
        hype_score=round(random.uniform(0.1, 1.0), 2),
        dev_wallet_pct=round(random.uniform(0.5, 25.0), 1),
        sniper_count=random.randint(0, 12),
        buy_pressure=random.choice(["weak","weak","moderate","moderate","strong","viral"]),
        narrative=random.choice(["AI","meme","animal","political","random"]),
        launch_wave="first_30s"
    )


def generate_token_full(index: int) -> TokenProfile:
    return TokenProfile(
        name=f"TKN_{index}",
        hype_score=round(random.uniform(0.05, 1.0), 2),
        dev_wallet_pct=round(random.uniform(1.0, 40.0), 1),
        sniper_count=random.randint(0, 25),
        buy_pressure=random.choice(["weak","weak","weak","weak","moderate","moderate","strong","viral"]),
        narrative=random.choice(["AI","meme","animal","political","random","random","random"]),
        launch_wave=random.choice(["first_30s","first_30s","1min","1min","1min","late","late"])
    )


# =====================================================================
# RESEARCH ENGINE — 5-signal scoring
# =====================================================================

def research_score(token: TokenProfile, curve: BondingCurve) -> Tuple[float, dict]:
    score = 0.0; signals = {}

    if token.dev_wallet_pct < MAX_DEV_WALLET_LOW:
        score += 25; signals["dev"] = f"✅ Low ({token.dev_wallet_pct}%)"
    elif token.dev_wallet_pct < MAX_DEV_WALLET_MED:
        score += 15; signals["dev"] = f"⚠️  Med ({token.dev_wallet_pct}%)"
    elif token.dev_wallet_pct < 15:
        score += 5;  signals["dev"] = f"⚠️  High ({token.dev_wallet_pct}%)"
    else:
        signals["dev"] = f"❌ Danger ({token.dev_wallet_pct}%)"

    if token.sniper_count <= MAX_SNIPER_LOW:
        score += 20; signals["snipe"] = f"✅ Clean ({token.sniper_count})"
    elif token.sniper_count <= MAX_SNIPER_MED:
        score += 10; signals["snipe"] = f"⚠️  Some ({token.sniper_count})"
    elif token.sniper_count <= 10:
        score += 3;  signals["snipe"] = f"⚠️  Many ({token.sniper_count})"
    else:
        signals["snipe"] = f"❌ Swarmed ({token.sniper_count})"

    pts = {"weak": 0, "moderate": 15, "strong": 25, "viral": 35}
    score += pts[token.buy_pressure]
    icon = "✅" if token.buy_pressure in ["strong","viral"] else "⚠️ "
    signals["momentum"] = f"{icon} {token.buy_pressure.upper()}"

    if token.hype_score > 0.75:
        score += 15; signals["hype"] = f"✅ High ({token.hype_score})"
    elif token.hype_score > 0.45:
        score += 8;  signals["hype"] = f"⚠️  Med ({token.hype_score})"
    else:
        signals["hype"] = f"❌ Low ({token.hype_score})"

    grad = curve.graduation_pct()
    if grad < GRAD_PCT_EARLY:
        score += 15; signals["curve"] = f"✅ Early ({grad:.1f}%)"
    elif grad < GRAD_PCT_MID:
        score += 8;  signals["curve"] = f"⚠️  Mid ({grad:.1f}%)"
    else:
        signals["curve"] = f"❌ Late ({grad:.1f}%)"

    if REALISM_MODE == "full" and token.launch_wave == "late":
        score -= 10

    return score, signals


# =====================================================================
# PRICE ACTION SIMULATORS
# =====================================================================

def simulate_price_soft(token: TokenProfile) -> Tuple[list, float, list]:
    hype_w       = HARSH_HYPE_WEIGHT if HARSH_MODE else 1.5
    sniper_mult  = HARSH_SNIPER_DRAG_MULT if HARSH_MODE else 1.0
    noise_mult   = HARSH_PRICE_NOISE_MULT if HARSH_MODE else 1.0
    dev_mult     = HARSH_DEV_DUMP_MULT if HARSH_MODE else 1.0

    pressure_mult = {"weak":0.3,"moderate":0.7,"strong":1.4,"viral":2.8}[token.buy_pressure]
    hype_mult     = token.hype_score * hype_w
    sniper_drag   = min(0.6, token.sniper_count * 0.05 * sniper_mult)
    base_momentum = (pressure_mult + hype_mult) / 2 - sniper_drag

    current = 1.0; peak = 1.0
    path = [(0.0, 1.0)]; volumes = [1.0]; prev_vol = 1.0

    for tick in range(1, SOFT_TICKS + 1):
        t = tick * SOFT_TICK_SIZE_SEC
        delta = random.gauss(base_momentum * 0.08, 0.06 * noise_mult)
        sniper_sell = -sniper_drag * 0.15 if t <= 20 else 0.0
        dev_dump = 0.0
        if current > 1.5 and random.random() < (token.dev_wallet_pct / 100.0) * 3:
            dev_dump = -random.uniform(0.2, 0.5) * dev_mult
        current = max(0.05, current + delta + sniper_sell + dev_dump)
        peak = max(peak, current)
        vol_delta = random.gauss(base_momentum * 0.1, 0.08 * noise_mult)
        prev_vol = max(0.1, prev_vol + vol_delta)
        path.append((t, round(current, 4)))
        volumes.append(round(prev_vol, 4))

    return path, peak, volumes


def simulate_price_full(token: TokenProfile) -> Tuple[list, float, list]:
    pressure     = {"weak":0.2,"moderate":0.5,"strong":1.2,"viral":2.5}[token.buy_pressure]
    hype         = token.hype_score * 1.2
    sniper_drag  = min(0.8, token.sniper_count * 0.04)
    dev_dump_risk= token.dev_wallet_pct / 100.0
    decay        = SPIKE_DECAY[token.buy_pressure]

    current = 1.0; peak = 1.0
    path = [(0.0, 1.0)]; volumes = [1.0]; prev_vol = 1.0
    momentum = (pressure + hype) / 2 - sniper_drag
    rug_tick = None
    if random.random() < MID_HOLD_RUG_RATE:
        rug_sec  = random.uniform(*MID_HOLD_RUG_WINDOW)
        rug_tick = int(rug_sec / FULL_TICK_SIZE_SEC)

    for tick in range(1, FULL_TICKS + 1):
        t = round(tick * FULL_TICK_SIZE_SEC, 1)
        momentum *= decay
        delta      = random.gauss(momentum * 0.04, 0.04)
        sniper_sell= (-sniper_drag * 0.12 if t <= 20 else
                      -sniper_drag * 0.04 if t <= 40 else 0.0)
        dev_dump   = 0.0
        if current > 1.3 and random.random() < dev_dump_risk * 0.8:
            dev_dump = -random.uniform(0.15, 0.45)
        if rug_tick and tick >= rug_tick:
            current = max(0.03, current * random.uniform(0.04, 0.12))
            peak    = max(peak, current)
            path.append((t, round(current, 4))); volumes.append(0.05); break
        current  = max(0.03, current + delta + sniper_sell + dev_dump)
        peak     = max(peak, current)
        prev_vol = max(0.05, prev_vol + random.gauss(momentum * 0.08, 0.06))
        path.append((t, round(current, 4))); volumes.append(round(prev_vol, 4))

    return path, peak, volumes


# =====================================================================
# EXIT ENGINE — standard + moonshot recognition
# =====================================================================

def compute_exit(price_path: list, volume_path: list, token: TokenProfile, score: float) -> Tuple[float, str, float]:
    is_viral  = token.buy_pressure == "viral"  and score >= 70
    is_strong = token.buy_pressure == "strong" and score >= 65

    base_target = VIRAL_RIDE_TARGET if is_viral else (STRONG_RIDE_TARGET if is_strong else QUICK_FLIP_TARGET)
    base_trail  = VIRAL_TRAIL_PCT   if is_viral else (STRONG_TRAIL_PCT   if is_strong else BASE_TRAIL_PCT)

    peak = 1.0; moonshot_mode = False; prev_high = 1.0; lower_highs = 0

    for i, (t, mult) in enumerate(price_path[1:], 1):
        vol      = volume_path[i] if i < len(volume_path) else volume_path[-1]
        prev_vol = volume_path[i-1] if i > 0 else 1.0
        peak = max(peak, mult)

        if not moonshot_mode and mult >= base_target and (is_viral or is_strong):
            if vol > prev_vol and mult >= prev_high * 0.99:
                moonshot_mode = True; prev_high = mult; continue

        if moonshot_mode:
            if mult > prev_high: lower_highs = 0; prev_high = mult
            else: lower_highs += 1
            if lower_highs >= MOONSHOT_LOWER_HIGHS and vol < prev_vol * MOONSHOT_VOL_FADE:
                return mult, f"MOONSHOT_EXIT_{int((mult-1)*100)}pct", t
            if mult >= MOONSHOT_HARDCAP: return mult, "MOONSHOT_HARDCAP_8x", t
            if mult < peak * MOONSHOT_TRAIL_PCT:
                return mult, f"MOONSHOT_TRAIL_{int((mult-1)*100)}pct", t
            prev_high = max(prev_high, mult); continue

        if mult >= base_target:
            label = (f"VIRAL_RIDE_{int((mult-1)*100)}pct" if is_viral else
                     f"STRONG_RIDE_{int((mult-1)*100)}pct" if is_strong else
                     "QUICK_FLIP_10pct")
            return mult, label, t
        if peak > 1.05 and mult < peak * base_trail: return mult, "TRAIL_STOP", t
        if mult < LOSS_CUT_PCT: return mult, "LOSS_CUT", t
        prev_high = mult

    final = price_path[-1][1]
    return final, (f"MOONSHOT_EXIT_{int((final-1)*100)}pct" if moonshot_mode else "TIME_EXIT"), price_path[-1][0]


# =====================================================================
# EXECUTION LAYER — full realism overhead
# =====================================================================

def apply_execution_overhead() -> Tuple[bool, bool, float, float, bool]:
    if random.random() < RPC_FAILURE_RATE:
        return True, False, 0.0, 0.0, False
    mev_hit   = random.random() < MEV_SANDWICH_RATE
    mev_slip  = MEV_SANDWICH_SLIPPAGE if mev_hit else 0.0
    congestion= random.random() < CONGESTION_DELAY_CHANCE
    cong_slip = CONGESTION_PRICE_MISS if congestion else 0.0
    actual_sol= BUY_SOL * (PARTIAL_FILL_PCT if random.random() < PARTIAL_FILL_RATE else 1.0)
    total_slip= BASE_SLIPPAGE + mev_slip + cong_slip
    return False, mev_hit, actual_sol, total_slip, congestion


# =====================================================================
# WITHDRAWAL LOG
# =====================================================================

def init_withdrawal_log():
    """Create/reset withdrawal_log.csv with headers."""
    with open(WITHDRAWAL_LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "round", "token", "exit_reason",
            "trade_pnl_usd", "amount_withdrawn_usd",
            "active_wallet_after", "cumulative_withdrawn_usd", "reset_count"
        ])
    log.info(f"  📒 Withdrawal log initialised → {WITHDRAWAL_LOG_FILE}")


def log_withdrawal(
    round_num: int, token_name: str, exit_reason: str,
    trade_pnl: float, amount_withdrawn: float,
    active_after: float, cumulative: float, reset_count: int
):
    """Append one withdrawal event to the CSV log."""
    with open(WITHDRAWAL_LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            round_num, token_name, exit_reason,
            round(trade_pnl, 2), round(amount_withdrawn, 2),
            round(active_after, 2), round(cumulative, 2), reset_count
        ])


# =====================================================================
# LIVE TRADING STUBS
# =====================================================================

def live_fetch_token(address: str) -> Optional[TokenProfile]:
    """
    TODO: Pull real token data from pump.fun API / on-chain.
    Recommended sources: Birdeye API, Helius RPC, pump.fun websocket.
    """
    raise NotImplementedError("Live token fetch not yet implemented")


def live_buy(token_address: str, sol_amount: float) -> Optional[float]:
    """
    TODO: Execute buy on pump.fun bonding curve via Solana web3.
    Use Jito bundles for MEV protection in live mode.
    Returns tokens received, or None on failure.
    """
    raise NotImplementedError("Live buy not yet implemented")


def live_sell(token_address: str, token_amount: float) -> Optional[float]:
    """
    TODO: Execute sell on pump.fun bonding curve via Solana web3.
    Returns SOL received, or None on failure.
    """
    raise NotImplementedError("Live sell not yet implemented")


def live_get_price_tick(token_address: str) -> Tuple[float, float]:
    """
    TODO: Pull current price multiplier + volume from on-chain / websocket.
    Use pump.fun websocket or Helius enhanced transactions for sub-second data.
    Returns (price_multiplier_vs_entry, current_volume).
    """
    raise NotImplementedError("Live price tick not yet implemented")


# =====================================================================
# MAIN BOT LOOP
# =====================================================================

def run_bot():
    random.seed(SIM_RANDOM_SEED)

    slip_rate    = HARSH_SLIPPAGE_FAIL if (REALISM_MODE == "soft" and HARSH_MODE) else SOFT_SLIPPAGE_FAIL_RATE
    mode_label   = f"DRY RUN [{REALISM_MODE.upper()}{' +HARSH' if HARSH_MODE else ''}]" if DRY_RUN else "⚡ LIVE MODE"

    log.info("=" * 70)
    log.info(f"  {mode_label} | SEED: ${SEED_USD:.2f} | BET: ${BET_USD:.2f} | TARGET: ${TARGET_USD:.2f}")
    log.info(f"  🌙 Moonshot engine ACTIVE | Momentum rider ACTIVE")
    log.info(f"  💰 KEEP_SEED_ONLY: {KEEP_SEED_ONLY} | Profit swept to wallet after every win")
    if REALISM_MODE == "full":
        log.info(f"  ✅ MEV | ✅ RPC fails | ✅ Sub-second | ✅ Mid-hold rugs | ✅ 80-300 tokens")
    log.info("=" * 70)

    if KEEP_SEED_ONLY:
        init_withdrawal_log()

    balance_usd  = SEED_USD
    withdrawn    = 0.0
    reset_count  = 0
    trades: List[dict] = []
    wins = losses = skipped = seen = moonshots = rpc_fails = mev_hits = rugs = 0
    token_counter = 0

    for r in range(1, ROUNDS + 1):
        tokens_this_round = (random.randint(*FULL_TOKENS_PER_ROUND) if REALISM_MODE == "full"
                             else random.randint(*SOFT_TOKENS_PER_ROUND))
        round_pnl = 0.0; round_trades = 0

        for _ in range(tokens_this_round):
            token_counter += 1; seen += 1

            if DRY_RUN:
                token = (generate_token_full(token_counter) if REALISM_MODE == "full"
                         else generate_token_soft(token_counter))
                curve = BondingCurve()
                for _ in range(random.randint(0, 15 if REALISM_MODE == "full" else 8)):
                    curve.buy(random.uniform(0.02 if REALISM_MODE == "full" else 0.05, 0.5))
            else:
                token = live_fetch_token("LIVE_TOKEN_ADDRESS")
                curve = BondingCurve()
            if token is None: continue

            score, signals = research_score(token, curve)
            if score < ENTRY_SCORE_MIN:
                skipped += 1; continue

            if balance_usd < BET_USD:
                log.warning(f"  💀 BUSTED — balance ${balance_usd:.2f} < bet ${BET_USD:.2f}")
                _print_summary(r, seen, skipped, wins, losses, moonshots, rpc_fails, mev_hits, rugs, balance_usd, withdrawn, reset_count, trades)
                return

            effective_buy_usd = BET_USD; mev_tag = ""
            if DRY_RUN and REALISM_MODE == "full":
                rpc_failed, mev_hit, actual_sol, total_slip, _ = apply_execution_overhead()
                if rpc_failed: rpc_fails += 1; continue
                if mev_hit:    mev_hits += 1; mev_tag = " [MEV]"
                effective_buy_usd = actual_sol * SOL_PRICE_USD * (1.0 - total_slip)
                curve.buy(actual_sol)
            elif DRY_RUN:
                if random.random() < slip_rate: continue
                curve.buy(BUY_SOL)
            else:
                tokens_received = live_buy(token.name, BUY_SOL)
                if tokens_received is None: continue

            if DRY_RUN:
                price_path, peak_mult, volume_path = (simulate_price_full(token) if REALISM_MODE == "full"
                                                      else simulate_price_soft(token))
                exit_mult, exit_reason, exit_time = compute_exit(price_path, volume_path, token, score)
            else:
                price_path = [(0, 1.0)]; volume_path = [1.0]
                for tick in range(1, 25):
                    mult, vol = live_get_price_tick(token.name)
                    price_path.append((tick * 5, mult)); volume_path.append(vol)
                    exit_mult, exit_reason, exit_time = compute_exit(price_path, volume_path, token, score)
                    if exit_reason != "TIME_EXIT": break
                    time.sleep(0.5 if REALISM_MODE == "full" else 5)
                sol_returned = live_sell(token.name, BUY_SOL / curve.price())
                if sol_returned is None: continue
                exit_mult = sol_returned / BUY_SOL

            if exit_mult < 0.15: rugs += 1
            pnl_usd = round(effective_buy_usd * (exit_mult - 1.0), 2)
            balance_usd += pnl_usd

            if pnl_usd > 0: wins += 1
            else:           losses += 1
            if "MOONSHOT" in exit_reason: moonshots += 1

            # ── WITHDRAWAL — sweep profit above seed ─────────────────
            if KEEP_SEED_ONLY and balance_usd > SEED_USD:
                amount_swept  = round(balance_usd - SEED_USD, 2)
                withdrawn    += amount_swept
                balance_usd   = SEED_USD
                reset_count  += 1
                if DRY_RUN:  # always log in sim; in live replace with real wallet tx
                    log_withdrawal(
                        round_num=r, token_name=token.name,
                        exit_reason=exit_reason, trade_pnl=pnl_usd,
                        amount_withdrawn=amount_swept,
                        active_after=balance_usd,
                        cumulative=withdrawn,
                        reset_count=reset_count
                    )
                log.info(
                    f"  💰 WITHDRAWAL #{reset_count:03d} | +${amount_swept:.2f} swept → wallet | "
                    f"cumulative: ${withdrawn:.2f} | active reset to ${balance_usd:.2f}"
                )

            round_trades += 1; round_pnl += pnl_usd

            flag = ("🌙" if "MOONSHOT" in exit_reason else "🚀" if "VIRAL" in exit_reason else
                    "🏄" if "STRONG"   in exit_reason else "✅" if pnl_usd > 0 else "❌")

            trades.append({
                "round": r, "token": token.name, "pressure": token.buy_pressure,
                "score": score, "exit_mult": round(exit_mult, 4),
                "exit_reason": exit_reason, "exit_time": exit_time,
                "pnl_usd": pnl_usd, "active_wallet": round(balance_usd, 2),
                "withdrawn_cumulative": round(withdrawn, 2), "flag": flag, "mev": mev_tag != ""
            })

            log.info(
                f"  {flag}  {token.name:<8} | sc{score:>3.0f} | {token.buy_pressure:<8} | "
                f"{exit_reason:<30} | {exit_time:>5.1f}s{mev_tag:<6} | "
                f"${pnl_usd:>+7.2f} | active ${balance_usd:.2f} | 💰withdrawn ${withdrawn:.2f}"
            )

            if balance_usd >= TARGET_USD:
                log.info(f"\n  🎯 TARGET HIT — ${balance_usd:.2f}")
                _print_summary(r, seen, skipped, wins, losses, moonshots, rpc_fails, mev_hits, rugs, balance_usd, withdrawn, reset_count, trades)
                return

        icon = "📈" if round_pnl >= 0 else "📉"
        log.info(
            f"Round {r:02d} {icon} | Seen: {tokens_this_round} | Traded: {round_trades} | "
            f"PnL: ${round_pnl:+.2f} | Active: ${balance_usd:.2f} | 💰 Withdrawn: ${withdrawn:.2f}\n"
        )

    _print_summary(ROUNDS, seen, skipped, wins, losses, moonshots, rpc_fails, mev_hits, rugs, balance_usd, withdrawn, reset_count, trades)


def _print_summary(rounds, seen, skipped, wins, losses, moonshots, rpc_fails, mev_hits, rugs, balance_usd, withdrawn, resets, trades):
    total = wins + losses
    wr    = (wins / total * 100) if total > 0 else 0
    log.info("\n" + "=" * 70)
    log.info(f"  FINAL RESULTS — {REALISM_MODE.upper()}{' +HARSH' if HARSH_MODE else ''} MODE")
    log.info("=" * 70)
    log.info(f"  Rounds      : {rounds} / {ROUNDS}")
    log.info(f"  Tokens seen : {seen:,} | Skipped: {skipped:,} | Traded: {total}")
    log.info(f"  W/L         : {wins}W / {losses}L | Win rate: {wr:.1f}%")
    log.info(f"  🌙 Moonshots : {moonshots}")
    log.info(f"  💀 Mid-rugs  : {rugs}")
    log.info(f"  ⚡ RPC fails : {rpc_fails}")
    log.info(f"  🥪 MEV hits  : {mev_hits}")
    log.info(f"  Active wallet  : ${balance_usd:.2f}")
    log.info(f"  💰 Withdrawn   : ${withdrawn:.2f}  ({resets} resets)")
    log.info(f"  Total value    : ${balance_usd + withdrawn:.2f}")
    log.info(f"  Net PnL        : ${(balance_usd + withdrawn) - SEED_USD:+.2f}")
    if KEEP_SEED_ONLY:
        log.info(f"  📒 Withdrawal log → {WITHDRAWAL_LOG_FILE}")
    log.info("=" * 70)


# =====================================================================
# ENTRY POINT
# =====================================================================

if __name__ == "__main__":
    run_bot()
