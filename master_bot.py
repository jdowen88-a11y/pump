#!/usr/bin/env python3
"""
MASTER SOLANA BOT v6.3 — Pump.fun Sniper + Portfolio Manager (with DRY_RUN safety mode)

DRY_RUN=true in .env → Full strategy runs (scoring, risk, dashboard, CSV logging)
                    but NO real transactions are sent. Perfect for testing logic safely.
"""

import os
import asyncio
import json
import csv
import base64
import time
import logging
import random
from datetime import datetime, date
from typing import Dict, Optional
from dataclasses import dataclass, field
import aiohttp
import websockets
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from dotenv import load_dotenv

load_dotenv()
console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("master")

# ===================== DUAL CONFIGS (1 SOL + 0.5 SOL) =====================

@dataclass
class ConfigMain:
    rpc_url: str = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    pumpportal_ws: str = os.getenv("PUMPPORTAL_WS", "wss://pumpportal.fun/api/data")
    pumpportal_api_key: str = os.getenv("PUMPPORTAL_API_KEY", "")
    jupiter_url: str = os.getenv("JUPITER_URL", "https://quote-api.jup.ag/v6")
    private_key: str = os.getenv("PRIVATE_KEY", "")
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat: str = os.getenv("TELEGRAM_CHAT_ID", "")
    x_bearer_token: str = os.getenv("X_BEARER_TOKEN", "")

    max_daily_loss: float = float(os.getenv("MAX_DAILY_LOSS", 1.0))
    max_position_sol: float = float(os.getenv("MAX_POSITION_SOL", 0.2))
    cooldown_min: int = int(os.getenv("COOLDOWN_MIN", 20))
    circuit_breaker_streak: int = int(os.getenv("CIRCUIT_STREAK", 3))

    default_buy_sol: float = float(os.getenv("BUY_SOL", 0.1))
    slippage_bps: int = int(os.getenv("SLIPPAGE", 1200))
    priority_fee: int = int(os.getenv("PRIORITY_FEE", 50000))
    tp_pct: float = float(os.getenv("TP_PCT", 60.0))
    sl_pct: float = float(os.getenv("SL_PCT", 25.0))
    trailing_pct: float = float(os.getenv("TRAILING", 18.0))
    min_rug_score: int = int(os.getenv("MIN_RUG_SCORE", 55))


@dataclass
class ConfigMini:
    rpc_url: str = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    pumpportal_ws: str = os.getenv("PUMPPORTAL_WS", "wss://pumpportal.fun/api/data")
    pumpportal_api_key: str = os.getenv("PUMPPORTAL_API_KEY", "")
    jupiter_url: str = os.getenv("JUPITER_URL", "https://quote-api.jup.ag/v6")
    private_key: str = os.getenv("PRIVATE_KEY_MINI", "")
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat: str = os.getenv("TELEGRAM_CHAT_ID", "")
    x_bearer_token: str = os.getenv("X_BEARER_TOKEN", "")

    max_daily_loss: float = float(os.getenv("MAX_DAILY_LOSS_MINI", 0.5))
    max_position_sol: float = float(os.getenv("MAX_POSITION_SOL_MINI", 0.1))
    cooldown_min: int = int(os.getenv("COOLDOWN_MIN_MINI", 25))
    circuit_breaker_streak: int = int(os.getenv("CIRCUIT_STREAK_MINI", 3))

    default_buy_sol: float = float(os.getenv("BUY_SOL_MINI", 0.05))
    slippage_bps: int = int(os.getenv("SLIPPAGE", 1200))
    priority_fee: int = int(os.getenv("PRIORITY_FEE", 50000))
    tp_pct: float = float(os.getenv("TP_PCT", 60.0))
    sl_pct: float = float(os.getenv("SL_PCT", 25.0))
    trailing_pct: float = float(os.getenv("TRAILING", 18.0))
    min_rug_score: int = int(os.getenv("MIN_RUG_SCORE_MINI", 60))


# Choose which config to use
CONFIG_MODE = os.getenv("CONFIG_MODE", "MAIN")  # "MAIN" or "MINI"
config = ConfigMain() if CONFIG_MODE == "MAIN" else ConfigMini()

# ===================== DRY RUN SAFETY (re-implemented cleanly) =====================
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")
if DRY_RUN:
    logger.warning("\n" + "="*60)
    logger.warning("DRY_RUN MODE ACTIVE — No real transactions will be broadcast.")
    logger.warning("Full strategy, risk engine, scoring, dashboard and CSV logging still run.")
    logger.warning("Set DRY_RUN=false (or remove) to go live. Default is SAFE (live).")
    logger.warning("="*60 + "\n")
else:
    logger.info("LIVE MODE — Real capital at risk. DRY_RUN=true for safe testing.")

keypair = Keypair.from_base58_string(config.private_key) if config.private_key else None

TRADE_CSV = "master_trades.csv"
if not os.path.exists(TRADE_CSV):
    with open(TRADE_CSV, "w", newline="") as f:
        csv.writer(f).writerow(["ts", "mint", "action", "sol", "pnl", "sig", "reason"])


async def log_trade(mint: str, action: str, sol: float, pnl: float, sig: str, reason: str):
    prefix = "[DRY] " if DRY_RUN else ""
    with open(TRADE_CSV, "a", newline="") as f:
        csv.writer(f).writerow([datetime.utcnow().isoformat(), mint, prefix + action, sol, pnl, sig, reason])


async def alert(msg: str):
    if config.telegram_token and config.telegram_chat:
        prefix = "[DRY-RUN] " if DRY_RUN else ""
        url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"
        async with aiohttp.ClientSession() as s:
            await s.post(url, json={"chat_id": config.telegram_chat, "text": prefix + msg})


# ===================== RISK ENGINE =====================
@dataclass
class RiskEngine:
    daily_loss: float = 0.0
    loss_streak: int = 0
    last_loss: Optional[datetime] = None
    positions: Dict[str, dict] = field(default_factory=dict)
    total_pnl: float = 0.0
    last_reset_date: date = field(default_factory=date.today)

    def check_daily_reset(self):
        today = date.today()
        if today != self.last_reset_date:
            self.daily_loss = 0.0
            self.loss_streak = 0
            self.last_reset_date = today
            logger.info("Daily risk counters reset")

    def can_trade(self, buy_sol: float) -> bool:
        self.check_daily_reset()
        if self.daily_loss >= config.max_daily_loss: return False
        if len(self.positions) >= 5: return False
        if self.loss_streak >= config.circuit_breaker_streak: return False
        if self.last_loss and (datetime.utcnow() - self.last_loss).total_seconds() < config.cooldown_min * 60: return False
        if buy_sol > config.max_position_sol: return False
        return True

    def record(self, mint: str, sol: float, success: bool, pnl: float = 0.0):
        if success:
            self.positions[mint] = {
                "size_sol": sol,
                "entry_price_sol": 0.0,
                "peak_price": 0.0,
                "unrealized_pnl": 0.0
            }
            self.loss_streak = 0
        else:
            self.daily_loss += abs(pnl)
            self.total_pnl += pnl
            self.loss_streak += 1
            self.last_loss = datetime.utcnow()
            self.positions.pop(mint, None)

risk = RiskEngine()

# ===================== JUPITER =====================
class Jupiter:
    def __init__(self, client: AsyncClient):
        self.session = aiohttp.ClientSession()
        self.client = client

    async def quote(self, input_mint: str, output_mint: str, amount: int, slippage_bps: int):
        params = {"inputMint": input_mint, "outputMint": output_mint, "amount": amount, "slippageBps": slippage_bps}
        async with self.session.get(f"{config.jupiter_url}/quote", params=params) as r:
            return await r.json()

    async def execute_swap(self, quote_resp: dict) -> Optional[str]:
        if DRY_RUN:
            logger.info("[DRY-RUN] Simulating Jupiter swap execution (no on-chain tx sent)")
            # Realistic simulation: 90% success to exercise full downstream logic (position mgmt, risk, alerts)
            if random.random() < 0.90:
                fake_sig = f"DRY_{int(time.time() * 1000)}_{random.randint(10000, 99999)}"
                logger.info(f"[DRY-RUN] Simulated SUCCESS → fake sig: {fake_sig}")
                return fake_sig
            else:
                logger.warning("[DRY-RUN] Simulated FAILURE (edge case testing)")
                return None

        # ===================== REAL ON-CHAIN EXECUTION =====================
        payload = {
            "quoteResponse": quote_resp,
            "userPublicKey": str(keypair.pubkey()),
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": config.priority_fee
        }
        async with self.session.post(f"{config.jupiter_url}/swap", json=payload) as r:
            data = await r.json()
            if "swapTransaction" not in data: return None
            tx = VersionedTransaction.from_bytes(base64.b64decode(data["swapTransaction"]))
            blockhash = (await self.client.get_latest_blockhash()).value.blockhash
            tx.message.recent_blockhash = blockhash
            tx.sign([keypair])
            result = await self.client.send_transaction(tx)
            return str(result.value)

# ===================== BONDING CURVE PRICE =====================
async def get_bonding_curve_price(client: AsyncClient, mint: str) -> float:
    try:
        bonding_curve = Pubkey.find_program_address(
            [b"bonding-curve", bytes(Pubkey.from_string(mint))],
            Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P")
        )[0]
        account = await client.get_account_info(bonding_curve)
        if not account.value or len(account.value.data) < 16:
            return 0.0
        data = account.value.data
        virtual_token_reserves = int.from_bytes(data[0:8], "little")
        virtual_sol_reserves = int.from_bytes(data[8:16], "little")
        if virtual_token_reserves == 0:
            return 0.0
        return virtual_sol_reserves / virtual_token_reserves
    except Exception:
        return 0.0

# ===================== ANALYZER =====================
class Analyzer:
    async def get_x_sentiment_bonus(self, mint: str, token_symbol: str = "") -> float:
        """
        Uses X search to generate a sentiment bonus in roughly [-10, +10].
        Heavier weight on recent activity and strong signals.
        """
        bearer_token = getattr(config, 'x_bearer_token', '')
        if not bearer_token:
            return 0.0

        query = f'"{mint}" OR "{token_symbol}" (pump OR solana OR "pump.fun")'
        url = "https://api.twitter.com/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        params = {
            "query": query,
            "max_results": 10,
            "tweet.fields": "text,created_at,public_metrics"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=10) as resp:
                    if resp.status != 200:
                        return 0.0

                    data = await resp.json()
                    tweets = data.get("data", [])
                    if not tweets:
                        return 0.0

                    # Sentiment keywords with weights
                    strong_positive = ["moon", "sending", "ape in", "alpha", "gem", "next 100x"]
                    positive = ["buy", "pump", "bullish", "loading"]
                    strong_negative = ["rug", "scam", "dev sold", "honeypot", "dumped", "avoid"]
                    negative = ["fud", "dead", "slow", "exit"]

                    score = 0
                    for tweet in tweets:
                        text = tweet.get("text", "").lower()
                        metrics = tweet.get("public_metrics", {})
                        engagement = metrics.get("retweet_count", 0) + metrics.get("like_count", 0)

                        local_score = 0
                        for word in strong_positive:
                            if word in text:
                                local_score += 3
                        for word in positive:
                            if word in text:
                                local_score += 1
                        for word in strong_negative:
                            if word in text:
                                local_score -= 4
                        for word in negative:
                            if word in text:
                                local_score -= 2

                        # Boost for high-engagement tweets
                        if engagement > 50:
                            local_score = int(local_score * 1.5)
                        elif engagement > 20:
                            local_score = int(local_score * 1.2)

                        score += local_score

                    # Normalize to -10 ~ +10
                    bonus = max(-10.0, min(10.0, score / 2))
                    return round(bonus, 1)

        except Exception as e:
            logger.warning(f"X sentiment fetch failed for {mint}: {e}")
            return 0.0

    async def rug_score(self, mint: str, client: AsyncClient) -> int:
        score = 55
        try:
            supply = await client.get_token_supply(Pubkey.from_string(mint))
            if supply.value and supply.value.ui_amount and supply.value.ui_amount > 1e9:
                score -= 12
        except Exception:
            pass

        # X / Grok sentiment hook
        sentiment_bonus = await self.get_x_sentiment_bonus(mint, mint[:6])
        score += int(sentiment_bonus)

        return max(15, min(90, score))

# ===================== FEEDS =====================
class Feeds:
    def __init__(self, client: AsyncClient):
        self.client = client

    async def pumpportal(self, queue: asyncio.Queue):
        url = config.pumpportal_ws
        if config.pumpportal_api_key:
            url += f"?api-key={config.pumpportal_api_key}"
        while True:
            try:
                async with websockets.connect(url) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if "mint" in str(data):
                            await queue.put(("new_token", data))
            except Exception as e:
                logger.warning(f"PumpPortal reconnect: {e}")
                await asyncio.sleep(5)

# ===================== MASTER BOT =====================
class MasterBot:
    def __init__(self, client: AsyncClient):
        self.client = client
        self.jupiter = Jupiter(client)
        self.feeds = Feeds(client)
        self.analyzer = Analyzer()

    async def snipe(self, mint: str):
        if not risk.can_trade(config.default_buy_sol): return
        score = await self.analyzer.rug_score(mint, self.client)
        if score < config.min_rug_score: return

        amount = int(config.default_buy_sol * 1_000_000_000)
        quote = await self.jupiter.quote("So11111111111111111111111111111111111111112", mint, amount, config.slippage_bps)
        if not quote: return

        sig = await self.jupiter.execute_swap(quote)
        if sig:
            price = await get_bonding_curve_price(self.client, mint)
            await log_trade(mint, "SNIPED", config.default_buy_sol, 0, sig, f"score_{score}")
            await alert(f"SNIPED {mint[:6]} | score {score}")
            risk.record(mint, config.default_buy_sol, True)
            pos = risk.positions[mint]
            pos["entry_price_sol"] = price
            pos["peak_price"] = price
            await asyncio.sleep(1.5)

    async def manage_positions(self):
        for mint, pos in list(risk.positions.items()):
            if pos.get("entry_price_sol", 0) <= 0:
                continue

            current_price = await get_bonding_curve_price(self.client, mint)
            if current_price <= 0:
                continue

            pos["peak_price"] = max(pos.get("peak_price", current_price), current_price)

            if pos["entry_price_sol"] > 0:
                pos["unrealized_pnl"] = pos["size_sol"] * (current_price / pos["entry_price_sol"] - 1)

            drop_from_peak = (pos["peak_price"] - current_price) / pos["peak_price"] if pos["peak_price"] > 0 else 0
            tp_hit = current_price >= pos["entry_price_sol"] * (1 + config.tp_pct / 100)
            sl_hit = current_price <= pos["entry_price_sol"] * (1 - config.sl_pct / 100)

            if drop_from_peak > (config.trailing_pct / 100) or tp_hit or sl_hit:
                logger.info(f"Exit triggered on {mint}")

                if pos["entry_price_sol"] > 0:
                    token_lots = int((pos["size_sol"] / pos["entry_price_sol"]) * 1_000_000)
                else:
                    token_lots = int(1_000_000)

                sell_quote = await self.jupiter.quote(
                    mint,
                    "So11111111111111111111111111111111111111112",
                    token_lots,
                    config.slippage_bps
                )

                if sell_quote:
                    sig = await self.jupiter.execute_swap(sell_quote)
                    pnl = pos.get("unrealized_pnl", 0.0)
                    if sig:
                        await log_trade(mint, "SELL", 0.0, pnl, sig, "auto_exit")
                    risk.record(mint, pos["size_sol"], True, pnl)
                else:
                    logger.warning(f"No sell quote for {mint} at current price {current_price}")

                risk.positions.pop(mint, None)

    async def run(self):
        queue = asyncio.Queue()
        asyncio.create_task(self.feeds.pumpportal(queue))

        layout = Layout()
        layout.split_row(Layout(name="sniper"), Layout(name="portfolio"))

        mode_banner = "[DRY-RUN SIMULATION]" if DRY_RUN else "[LIVE CAPITAL]"
        with Live(layout, refresh_per_second=3) as live:
            while True:
                try:
                    risk.total_pnl = sum(
                        p.get("unrealized_pnl", 0) for p in risk.positions.values()
                    )

                    event, data = await asyncio.wait_for(queue.get(), timeout=0.5)
                    if event == "new_token":
                        mint = data.get("mint", "")
                        if mint:
                            await self.snipe(mint)

                    await self.manage_positions()

                    s_table = Table(title=f"SNIPER {mode_banner}")
                    for m in list(risk.positions.keys())[-5:]:
                        s_table.add_row(m[:8])

                    p_table = Table(title=f"POSITIONS | PnL: {risk.total_pnl:.3f} SOL")
                    for m, p in risk.positions.items():
                        p_table.add_row(m[:8], f"{p['size_sol']:.2f}", f"{p.get('unrealized_pnl', 0):.3f}")

                    layout["sniper"].update(Panel(s_table))
                    layout["portfolio"].update(Panel(p_table))

                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    logger.error(str(e))
                    await asyncio.sleep(1)


if __name__ == "__main__":
    if not keypair:
        console.print("[red]PRIVATE_KEY (or PRIVATE_KEY_MINI) missing in .env[/red]")
        exit(1)

    client = AsyncClient(config.rpc_url)
    bot = MasterBot(client)
    asyncio.run(bot.run())
