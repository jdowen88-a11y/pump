
# =====================================================================
# master_bot.py — Elite pump.fun Simulation + Live Trading Engine
# =====================================================================
# Features:
#   - Real pump.fun bonding curve math (virtual reserves model)
#   - 5-signal research engine (dev wallet, snipers, momentum, hype, curve pos)
#   - Momentum rider: viral 40%, strong 25%, quick flip 10%
#   - Live moonshot recognition: dynamic hold when volume + price confirm runner
#   - DRY_RUN mode: set True to simulate, False to trade live
# =====================================================================

import random
import time
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("master_bot")

# =====================================================================
# CONFIG — Edit these values to adjust behavior
# =====================================================================

DRY_RUN = True                  # True = simulation only, False = live trading

SEED_USD        = 100.0         # Starting capital in USD
TARGET_USD      = 500.0         # Profit target — bot stops when balance hits this
BET_USD         = 17.50         # Amount to risk per trade (0.1 SOL at $175/SOL)
ROUNDS          = 20            # Number of market scan rounds

SOL_PRICE_USD   = 175.0         # SOL price — update or pull from API when live
BUY_SOL         = BET_USD / SOL_PRICE_USD   # SOL per trade

# Research engine thresholds
ENTRY_SCORE_MIN         = 55    # Minimum research score to enter a trade
MAX_DEV_WALLET_LOW      = 3.0   # % — dev wallet below this = low risk (25 pts)
MAX_DEV_WALLET_MED      = 8.0   # % — dev wallet below this = medium risk (15 pts)
MAX_SNIPER_LOW          = 2     # sniper count below this = clean launch (20 pts)
MAX_SNIPER_MED          = 5     # sniper count below this = some snipers (10 pts)
GRAD_PCT_EARLY          = 15.0  # bonding curve % — very early entry (15 pts)
GRAD_PCT_MID            = 35.0  # bonding curve % — mid curve entry (8 pts)

# Exit targets
QUICK_FLIP_TARGET       = 1.10  # 10% — default exit for normal tokens
STRONG_RIDE_TARGET      = 1.25  # 25% — hold target for strong tokens
VIRAL_RIDE_TARGET       = 1.40  # 40% — hold target for viral tokens
STRONG_TRAIL_PCT        = 0.91  # 9% trailing stop for strong rides
VIRAL_TRAIL_PCT         = 0.90  # 10% trailing stop for viral rides
BASE_TRAIL_PCT          = 0.92  # 8% trailing stop for quick flips
LOSS_CUT_PCT            = 0.88  # Cut losses at -12%

# Moonshot engine
MOONSHOT_TRAIL_PCT      = 0.94  # 6% trailing stop once in moonshot mode
MOONSHOT_HARDCAP        = 8.0   # Exit at 8x no matter what
MOONSHOT_LOWER_HIGHS    = 2     # Consecutive lower highs before exit
MOONSHOT_VOL_FADE       = 0.85  # Volume must drop to 85% of prev tick to confirm fade

# Simulation-only settings
SIM_RANDOM_SEED         = 7
SIM_SLIPPAGE_FAIL_RATE  = 0.07

# =====================================================================
# PUMP.FUN BONDING CURVE
# Mirrors real pump.fun: virtual reserves start at 30 SOL / 1B tokens
# Price = virtual_sol / virtual_tokens
# Graduation at 69 SOL real liquidity
# =====================================================================

@dataclass
class BondingCurve:
    virtual_sol: float = 30.0
    virtual_tokens: float = 1_000_000_000.0
    real_sol: float = 0.0
    total_supply: float = 1_000_000_000.0

    def price(self) -> float:
        """Current token price in SOL"""
        return self.virtual_sol / self.virtual_tokens

    def market_cap_usd(self) -> float:
        return self.price() * self.total_supply * SOL_PRICE_USD

    def graduation_pct(self) -> float:
        """% progress toward DEX graduation (100% = listed on Raydium)"""
        return min(100.0, self.real_sol / 69.0 * 100.0)

    def buy(self, sol_in: float) -> float:
        """Buy tokens with sol_in SOL. Returns tokens received."""
        if sol_in <= 0:
            return 0.0
        tokens_out = self.virtual_tokens - (
            (self.virtual_sol * self.virtual_tokens) / (self.virtual_sol + sol_in)
        )
        self.virtual_sol += sol_in
        self.virtual_tokens -= tokens_out
        self.real_sol += sol_in
        return tokens_out

    def sell(self, tokens_in: float) -> float:
        """Sell tokens_in tokens. Returns SOL received."""
        if tokens_in <= 0:
            return 0.0
        sol_out = self.virtual_sol - (
            (self.virtual_sol * self.virtual_tokens) / (self.virtual_tokens + tokens_in)
        )
        self.virtual_tokens += tokens_in
        self.virtual_sol -= sol_out
        self.real_sol = max(0.0, self.real_sol - sol_out)
        return max(0.0, sol_out)


# =====================================================================
# TOKEN PROFILE
# Represents a pump.fun token launch with all relevant risk signals
# =====================================================================

@dataclass
class TokenProfile:
    name: str
    hype_score: float           # 0.0–1.0 organic interest
    dev_wallet_pct: float       # % of supply held by dev
    sniper_count: int           # number of sniper bots at launch
    buy_pressure: str           # "weak" | "moderate" | "strong" | "viral"
    narrative: str              # "AI" | "meme" | "animal" | "political" | "random"


def generate_token_sim(index: int) -> TokenProfile:
    """Generate a simulated token profile for dry run."""
    return TokenProfile(
        name=f"TKN_{index}",
        hype_score=round(random.uniform(0.1, 1.0), 2),
        dev_wallet_pct=round(random.uniform(0.5, 25.0), 1),
        sniper_count=random.randint(0, 12),
        buy_pressure=random.choice(["weak", "weak", "moderate", "moderate", "strong", "viral"]),
        narrative=random.choice(["AI", "meme", "animal", "political", "random"])
    )


# =====================================================================
# RESEARCH ENGINE
# Scores a token 0–110 across 5 dimensions before entry
# =====================================================================

def research_score(token: TokenProfile, curve: BondingCurve) -> Tuple[float, dict]:
    """
    Returns (score, signal_breakdown).
    Score >= ENTRY_SCORE_MIN = tradeable.
    """
    score = 0.0
    signals = {}

    # 1. Dev wallet risk
    if token.dev_wallet_pct < MAX_DEV_WALLET_LOW:
        score += 25
        signals["dev_wallet"] = f"✅ Low ({token.dev_wallet_pct}%)"
    elif token.dev_wallet_pct < MAX_DEV_WALLET_MED:
        score += 15
        signals["dev_wallet"] = f"⚠️  Med ({token.dev_wallet_pct}%)"
    else:
        signals["dev_wallet"] = f"❌ High ({token.dev_wallet_pct}%)"

    # 2. Sniper concentration
    if token.sniper_count <= MAX_SNIPER_LOW:
        score += 20
        signals["snipers"] = f"✅ Clean ({token.sniper_count})"
    elif token.sniper_count <= MAX_SNIPER_MED:
        score += 10
        signals["snipers"] = f"⚠️  Some ({token.sniper_count})"
    else:
        signals["snipers"] = f"❌ Swarmed ({token.sniper_count})"

    # 3. Buy pressure / momentum
    pressure_pts = {"weak": 0, "moderate": 15, "strong": 25, "viral": 35}
    score += pressure_pts[token.buy_pressure]
    icon = "✅" if token.buy_pressure in ["strong", "viral"] else "⚠️ "
    signals["momentum"] = f"{icon} {token.buy_pressure.upper()}"

    # 4. Hype / narrative
    if token.hype_score > 0.75:
        score += 15
        signals["hype"] = f"✅ High ({token.hype_score})"
    elif token.hype_score > 0.45:
        score += 8
        signals["hype"] = f"⚠️  Med ({token.hype_score})"
    else:
        signals["hype"] = f"❌ Low ({token.hype_score})"

    # 5. Bonding curve position
    grad = curve.graduation_pct()
    if grad < GRAD_PCT_EARLY:
        score += 15
        signals["curve"] = f"✅ Early ({grad:.1f}%)"
    elif grad < GRAD_PCT_MID:
        score += 8
        signals["curve"] = f"⚠️  Mid ({grad:.1f}%)"
    else:
        signals["curve"] = f"❌ Late ({grad:.1f}%)"

    return score, signals


# =====================================================================
# PRICE ACTION SIMULATOR (DRY RUN ONLY)
# Generates realistic tick-by-tick price + volume for 120 seconds
# =====================================================================

def simulate_price_action(token: TokenProfile) -> Tuple[list, float, list]:
    """
    Returns (price_path, peak_mult, volume_path).
    price_path: list of (time_sec, price_multiplier)
    volume_path: list of relative volume per tick
    """
    pressure_mult = {"weak": 0.3, "moderate": 0.7, "strong": 1.4, "viral": 2.8}[token.buy_pressure]
    hype_mult = token.hype_score * 1.5
    sniper_drag = min(0.6, token.sniper_count * 0.05)
    base_momentum = (pressure_mult + hype_mult) / 2 - sniper_drag

    current_mult = 1.0
    peak_mult = 1.0
    price_path = [(0, 1.0)]
    volume_path = [1.0]
    prev_vol = 1.0

    for tick in range(1, 25):
        t = tick * 5
        price_delta = random.gauss(base_momentum * 0.08, 0.06)
        sniper_sell = -sniper_drag * 0.15 if t <= 20 else 0.0
        dev_dump = 0.0
        if current_mult > 1.5 and random.random() < (token.dev_wallet_pct / 100.0) * 3:
            dev_dump = -random.uniform(0.2, 0.5)

        current_mult = max(0.05, current_mult + price_delta + sniper_sell + dev_dump)
        peak_mult = max(peak_mult, current_mult)

        vol_delta = random.gauss(base_momentum * 0.1, 0.08)
        prev_vol = max(0.1, prev_vol + vol_delta)

        price_path.append((t, round(current_mult, 4)))
        volume_path.append(round(prev_vol, 4))

    return price_path, peak_mult, volume_path


# =====================================================================
# ELITE EXIT ENGINE WITH MOONSHOT RECOGNITION
# =====================================================================

def compute_exit(
    price_path: list,
    volume_path: list,
    token: TokenProfile,
    score: float
) -> Tuple[float, str, int]:
    """
    Elite exit logic:
      - VIRAL token + score 70+  → ride to 40%, then moonshot layer
      - STRONG token + score 65+ → ride to 25%, then moonshot layer
      - All others               → quick 10% flip
      - MOONSHOT layer: if volume still accelerating + price making higher
        highs when base target is hit → hold dynamically with 6% trailing stop
      - Exits moonshot on: 2 consecutive lower highs + volume fade, OR 8x hardcap
    """
    is_viral  = (token.buy_pressure == "viral"  and score >= 70)
    is_strong = (token.buy_pressure == "strong" and score >= 65)

    base_target = VIRAL_RIDE_TARGET if is_viral else (STRONG_RIDE_TARGET if is_strong else QUICK_FLIP_TARGET)
    base_trail  = VIRAL_TRAIL_PCT   if is_viral else (STRONG_TRAIL_PCT   if is_strong else BASE_TRAIL_PCT)

    peak = 1.0
    moonshot_mode = False
    prev_tick_high = 1.0
    consecutive_lower_highs = 0

    for i, (t, mult) in enumerate(price_path[1:], 1):
        vol = volume_path[i] if i < len(volume_path) else volume_path[-1]
        prev_vol = volume_path[i - 1] if i > 0 else 1.0
        peak = max(peak, mult)

        # ── MOONSHOT DETECTION ──────────────────────────────────────
        if not moonshot_mode and mult >= base_target and (is_viral or is_strong):
            vol_accelerating = vol > prev_vol
            still_climbing   = mult >= prev_tick_high * 0.99
            if vol_accelerating and still_climbing:
                moonshot_mode = True
                prev_tick_high = mult
                log.debug(f"🌙 Moonshot activated at {mult:.3f}x on {token.name}")
                continue

        # ── MOONSHOT HOLD LOGIC ─────────────────────────────────────
        if moonshot_mode:
            vol_fading = vol < prev_vol * MOONSHOT_VOL_FADE

            if mult > prev_tick_high:
                consecutive_lower_highs = 0
                prev_tick_high = mult
            else:
                consecutive_lower_highs += 1

            # Exit: momentum stalled (lower highs + volume fading)
            if consecutive_lower_highs >= MOONSHOT_LOWER_HIGHS and vol_fading:
                gain_pct = int((mult - 1.0) * 100)
                return mult, f"MOONSHOT_EXIT_{gain_pct}pct", t

            # Hardcap exit
            if mult >= MOONSHOT_HARDCAP:
                return mult, "MOONSHOT_HARDCAP_8x", t

            # Tight trailing stop in moonshot mode
            if mult < peak * MOONSHOT_TRAIL_PCT:
                gain_pct = int((mult - 1.0) * 100)
                return mult, f"MOONSHOT_TRAIL_{gain_pct}pct", t

            prev_tick_high = max(prev_tick_high, mult)
            continue

        # ── STANDARD EXIT LOGIC ─────────────────────────────────────
        if mult >= base_target:
            if is_viral:
                label = f"VIRAL_RIDE_{int((mult - 1) * 100)}pct"
            elif is_strong:
                label = f"STRONG_RIDE_{int((mult - 1) * 100)}pct"
            else:
                label = "QUICK_FLIP_10pct"
            return mult, label, t

        # Trailing stop
        if peak > 1.05 and mult < peak * base_trail:
            return mult, "TRAIL_STOP", t

        # Fast loss cut
        if mult < LOSS_CUT_PCT:
            return mult, "LOSS_CUT", t

        prev_tick_high = mult

    # End of observation window
    final_mult = price_path[-1][1]
    gain_pct   = int((final_mult - 1.0) * 100)
    reason     = f"MOONSHOT_EXIT_{gain_pct}pct" if moonshot_mode else "TIME_EXIT"
    return final_mult, reason, price_path[-1][0]


# =====================================================================
# LIVE TRADING STUB
# Replace the functions below with real Solana / pump.fun API calls
# when DRY_RUN = False
# =====================================================================

def live_fetch_token(address: str) -> Optional[TokenProfile]:
    """
    TODO: Pull real token data from pump.fun API / on-chain.
    Return a TokenProfile populated with live dev wallet %, sniper data, etc.
    """
    raise NotImplementedError("Live token fetch not yet implemented")


def live_buy(token_address: str, sol_amount: float) -> Optional[float]:
    """
    TODO: Execute buy on pump.fun bonding curve via Solana web3.
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
    TODO: Pull current price multiplier and volume from on-chain / websocket.
    Returns (price_multiplier_vs_entry, current_volume).
    """
    raise NotImplementedError("Live price tick not yet implemented")


# =====================================================================
# MAIN BOT LOOP
# =====================================================================

def run_bot():
    if DRY_RUN:
        random.seed(SIM_RANDOM_SEED)
        log.info("=" * 70)
        log.info(f"  DRY RUN | SEED: ${SEED_USD:.2f} | BET: ${BET_USD:.2f} | TARGET: ${TARGET_USD:.2f}")
        log.info(f"  Moonshot engine active | Momentum rider active")
        log.info("=" * 70)
    else:
        log.info("=" * 70)
        log.info(f"  LIVE MODE | SEED: ${SEED_USD:.2f} | BET: ${BET_USD:.2f} | TARGET: ${TARGET_USD:.2f}")
        log.info("=" * 70)

    balance_usd = SEED_USD
    balance_sol = SEED_USD / SOL_PRICE_USD
    trades: List[dict] = []
    wins = losses = skipped = seen = moonshots_caught = 0
    token_counter = 0

    for r in range(1, ROUNDS + 1):
        tokens_this_round = random.randint(4, 10) if DRY_RUN else 1
        round_pnl = 0.0
        round_trades = 0

        for _ in range(tokens_this_round):
            token_counter += 1
            seen += 1

            # ── FETCH TOKEN ──────────────────────────────────────────
            if DRY_RUN:
                token = generate_token_sim(token_counter)
                curve = BondingCurve()
                for _ in range(random.randint(0, 8)):
                    curve.buy(random.uniform(0.05, 0.3))
            else:
                token_address = "LIVE_TOKEN_ADDRESS"  # replace with live discovery
                token = live_fetch_token(token_address)
                curve = BondingCurve()  # populate from on-chain state when live

            if token is None:
                continue

            # ── RESEARCH ────────────────────────────────────────────
            score, signals = research_score(token, curve)
            if score < ENTRY_SCORE_MIN:
                skipped += 1
                log.debug(f"  SKIP {token.name} | score {score:.0f} < {ENTRY_SCORE_MIN}")
                continue

            if balance_usd < BET_USD:
                log.warning(f"  BUSTED — balance ${balance_usd:.2f} < bet ${BET_USD:.2f}")
                return

            # ── ENTRY ────────────────────────────────────────────────
            log.info(f"  ENTER {token.name} | score {score:.0f} | {token.buy_pressure.upper()} | ${BET_USD:.2f}")
            if DRY_RUN:
                curve.buy(BUY_SOL)
            else:
                tokens_received = live_buy(token.name, BUY_SOL)
                if tokens_received is None:
                    log.warning(f"  Buy failed for {token.name}")
                    continue

            # ── PRICE ACTION + EXIT ──────────────────────────────────
            if DRY_RUN:
                price_path, peak_mult, volume_path = simulate_price_action(token)
                exit_mult, exit_reason, exit_time = compute_exit(price_path, volume_path, token, score)
                if random.random() < SIM_SLIPPAGE_FAIL_RATE:
                    log.warning(f"  SWAP_FAILED simulation slippage on {token.name}")
                    continue
            else:
                # Live: poll price ticks and apply exit logic in real time
                # This is a simplified stub — replace with async websocket listener
                price_path = [(0, 1.0)]
                volume_path = [1.0]
                for tick in range(1, 25):
                    t = tick * 5
                    mult, vol = live_get_price_tick(token.name)
                    price_path.append((t, mult))
                    volume_path.append(vol)
                    exit_mult, exit_reason, exit_time = compute_exit(price_path, volume_path, token, score)
                    if exit_reason != "TIME_EXIT":
                        break
                    time.sleep(5)

                tokens_received = BUY_SOL / curve.price()  # approximate
                sol_returned = live_sell(token.name, tokens_received)
                if sol_returned is None:
                    log.warning(f"  Sell failed for {token.name}")
                    continue
                exit_mult = sol_returned / BUY_SOL

            # ── PNL ──────────────────────────────────────────────────
            pnl_usd = round(BET_USD * (exit_mult - 1.0), 2)
            balance_usd += pnl_usd
            balance_sol = balance_usd / SOL_PRICE_USD

            if pnl_usd > 0:
                wins += 1
            else:
                losses += 1

            if "MOONSHOT" in exit_reason:
                moonshots_caught += 1

            round_trades += 1
            round_pnl += pnl_usd

            flag = "🌙" if "MOONSHOT" in exit_reason else (
                   "🚀" if "VIRAL"    in exit_reason else (
                   "🏄" if "STRONG"   in exit_reason else (
                   "✅" if pnl_usd > 0 else "❌")))

            trade_record = {
                "round": r, "token": token.name,
                "pressure": token.buy_pressure, "score": score,
                "exit_mult": round(exit_mult, 4), "exit_reason": exit_reason,
                "exit_time_sec": exit_time if DRY_RUN else None,
                "pnl_usd": pnl_usd, "balance_usd": round(balance_usd, 2),
                "flag": flag
            }
            trades.append(trade_record)

            log.info(
                f"  {flag} {token.name} | {exit_reason} @ {exit_mult:.3f}x | "
                f"PnL: ${pnl_usd:+.2f} | Balance: ${balance_usd:.2f}"
            )

            # ── TARGET CHECK ─────────────────────────────────────────
            if balance_usd >= TARGET_USD:
                log.info(f"\n  🎯 TARGET HIT — ${balance_usd:.2f}")
                _print_summary(r, seen, skipped, wins, losses, moonshots_caught, balance_usd, trades)
                return

        icon = "📈" if round_pnl >= 0 else "📉"
        log.info(
            f"Round {r:02d} {icon} | Traded: {round_trades} | "
            f"Round PnL: ${round_pnl:+.2f} | Balance: ${balance_usd:.2f}"
        )

    _print_summary(ROUNDS, seen, skipped, wins, losses, moonshots_caught, balance_usd, trades)


def _print_summary(rounds, seen, skipped, wins, losses, moonshots, balance_usd, trades):
    total = wins + losses
    wr = (wins / total * 100) if total > 0 else 0
    log.info("\n" + "=" * 70)
    log.info("  FINAL RESULTS")
    log.info("=" * 70)
    log.info(f"  Rounds completed : {rounds} / {ROUNDS}")
    log.info(f"  Tokens seen      : {seen} | Skipped: {skipped} | Traded: {total}")
    log.info(f"  Wins / Losses    : {wins} W / {losses} L | Win rate: {wr:.1f}%")
    log.info(f"  🌙 Moonshots     : {moonshots}")
    log.info(f"  Starting balance : ${SEED_USD:.2f}")
    log.info(f"  Final balance    : ${balance_usd:.2f}")
    log.info(f"  Net PnL          : ${balance_usd - SEED_USD:+.2f}")
    log.info("=" * 70)


# =====================================================================
# ENTRY POINT
# =====================================================================

if __name__ == "__main__":
    run_bot()
