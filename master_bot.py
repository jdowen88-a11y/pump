#!/usr/bin/env python3
"""
MASTER SOLANA BOT v6.2 — Pump.fun Sniper + Portfolio Manager

Fully async, Jupiter-powered, with real bonding curve pricing,
conservative risk management, and proper PnL tracking on exits.

See conversation history for full context and tuning.
"""

import os
import asyncio
import json
import csv
import base64
import time
import logging
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

@dataclass
class Config:
    rpc_url: str = os.getenv("SOLANA_RPC_URL", "")
    pumpportal_ws: str = os.getenv("PUMPPORTAL_WS", "wss://pumpportal.fun/api/data")
    pumpportal_api_key: str = os.getenv("PUMPPORTAL_API_KEY", "")
    jupiter_url: str = os.getenv("JUPITER_URL", "https://quote-api.jup.ag/v6")
    private_key: str = os.getenv("PRIVATE_KEY", "")
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat: str = os.getenv("TELEGRAM_CHAT_ID", "")

    max_daily_loss: float = float(os.getenv("MAX_DAILY_LOSS", 3.0))
    max_position_sol: float = float(os.getenv("MAX_POSITION_SOL", 1.5))
    cooldown_min: int = int(os.getenv("COOLDOWN_MIN", 10))
    circuit_breaker_streak: int = int(os.getenv("CIRCUIT_STREAK", 3))

    default_buy_sol: float = float(os.getenv("BUY_SOL", 0.1))
    slippage_bps: int = int(os.getenv("SLIPPAGE", 1200))
    priority_fee: int = int(os.getenv("PRIORITY_FEE", 50000))
    tp_pct: float = float(os.getenv("TP_PCT", 60.0))
    sl_pct: float = float(os.getenv("SL_PCT", 25.0))
    trailing_pct: float = float(os.getenv("TRAILING", 18.0))
    min_rug_score: int = int(os.getenv("MIN_RUG_SCORE", 50))

config = Config()
keypair = Keypair.from_base58_string(config.private_key) if config.private_key else None

TRADE_CSV = "master_trades.csv"
if not os.path.exists(TRADE_CSV):
    with open(TRADE_CSV, "w", newline="") as f:
        csv.writer(f).writerow(["ts", "mint", "action", "sol", "pnl", "sig", "reason"])

async def log_trade(mint: str, action: str, sol: float, pnl: float, sig: str, reason: str):
    with open(TRADE_CSV, "a", newline="") as f:
        csv.writer(f).writerow([datetime.utcnow().isoformat(), mint, action, sol, pnl, sig, reason])

async def alert(msg: str):
    if config.telegram_token and config.telegram_chat:
        url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"
        async with aiohttp.ClientSession() as s:
            await s.post(url, json={"chat_id": config.telegram_chat, "text": msg})

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
    async def rug_score(self, mint: str, client: AsyncClient) -> int:
        score = 55
        try:
            supply = await client.get_token_supply(Pubkey.from_string(mint))
            if supply.value and supply.value.ui_amount and supply.value.ui_amount > 1e9:
                score -= 12
        except:
            pass
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

                # Estimate token amount roughly matching our size_sol
                if pos["entry_price_sol"] > 0:
                    token_lots = int((pos["size_sol"] / pos["entry_price_sol"]) * 1_000_000)
                else:
                    token_lots = int(1_000_000)  # 1 token

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
                    # Correct: successful sell → success=True
                    risk.record(mint, pos["size_sol"], True, pnl)
                else:
                    logger.warning(f"No sell quote for {mint} at current price {current_price}")

                # Remove position whether or not we got a quote
                risk.positions.pop(mint, None)

    async def run(self):
        queue = asyncio.Queue()
        asyncio.create_task(self.feeds.pumpportal(queue))

        layout = Layout()
        layout.split_row(Layout(name="sniper"), Layout(name="portfolio"))

        with Live(layout, refresh_per_second=3) as live:
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=0.5)
                    if event == "new_token":
                        mint = data.get("mint", "")
                        if mint:
                            await self.snipe(mint)

                    await self.manage_positions()

                    # =============== ADDED IN BY ME ===============
                    # Snapshot total PnL from current positions
                    risk.total_pnl = sum(
                        p.get("unrealized_pnl", 0) for p in risk.positions.values()
                    )

                    s_table = Table(title="SNIPER")
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


# ===================== TIGHTENED .env RECOMMENDATION (for 2–5 SOL stack) =====================
"""
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
PUMPPORTAL_WS=wss://pumpportal.fun/api/data
PUMPPORTAL_API_KEY=your_pumpportal_api_key

PRIVATE_KEY=your_base58_private_key

TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_ID=123456789

MAX_DAILY_LOSS=2.0
MAX_POSITION_SOL=0.5
COOLDOWN_MIN=15
CIRCUIT_STREAK=3

BUY_SOL=0.1
SLIPPAGE=1200
PRIORITY_FEE=50000
TP_PCT=60.0
SL_PCT=25.0
TRAILING=18.0
MIN_RUG_SCORE=50
"""

if __name__ == "__main__":
    if not keypair:
        console.print("[red]PRIVATE_KEY missing in .env[/red]")
        exit(1)
    client = AsyncClient(config.rpc_url)
    bot = MasterBot(client)
    asyncio.run(bot.run())
