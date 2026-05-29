"""bot_runtime_telemetry.py

Telemetry-enabled runner for the existing pump bot.

This file does not edit master_bot.py. It imports the existing bot runtime,
starts config watching, starts telemetry snapshots, then calls master_bot.run_bot().

Environment:
  PUMP_DASHBOARD_API       Backend base URL
  PUMP_API_TOKEN           Auth token for protected telemetry/config routes
  PUMP_RUNTIME_CONFIG      runtime_config.json path
  PUMP_RUNTIME_POLL_SECONDS
  PUMP_TELEMETRY_SECONDS
"""

from __future__ import annotations

import random
import threading
import time
from typing import Any, Dict

import bot_runtime_controller as controller
import master_bot
from telemetry_client import TelemetryClient

TELEMETRY_SECONDS = float(__import__("os").getenv("PUMP_TELEMETRY_SECONDS", "3"))
telemetry = TelemetryClient()


def build_runtime_snapshot() -> Dict[str, Any]:
    score = getattr(master_bot, "ENTRY_SCORE_MIN", 0)
    price_path = [[i, round(random.uniform(0.7, 1.7), 4)] for i in range(32)]
    volume_path = [round(random.uniform(1, 9), 4) for _ in range(32)]

    return {
        "mode": "DRY" if getattr(master_bot, "DRY_RUN", True) else "LIVE",
        "decision": "RUNTIME_ACTIVE",
        "score": score,
        "token": "BOT_RUNTIME",
        "pnlUsd": "$0",
        "signals": {
            "realism_mode": getattr(master_bot, "REALISM_MODE", "unknown"),
            "harsh_mode": getattr(master_bot, "HARSH_MODE", False),
            "keep_seed_only": getattr(master_bot, "KEEP_SEED_ONLY", False),
            "entry_score_min": score,
        },
        "pressure": "runtime",
        "exitReason": "telemetry heartbeat",
        "exitMult": 1,
        "activeWallet": "runtime",
        "withdrawn": 0,
        "holders": "-",
        "snipers": getattr(master_bot, "MAX_SNIPER_MED", "-"),
        "devWalletPercent": getattr(master_bot, "MAX_DEV_WALLET_MED", "-"),
        "topTenPercent": "-",
        "marketCap": "runtime",
        "volume": "heartbeat",
        "pricePath": price_path,
        "volumePath": volume_path,
    }


def telemetry_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        telemetry.send(build_runtime_snapshot())
        stop_event.wait(max(1.0, TELEMETRY_SECONDS))


def main() -> int:
    stop_event = threading.Event()

    controller.apply_config_once()

    config_thread = threading.Thread(
        target=controller.watch_runtime_config,
        args=(stop_event,),
        daemon=True,
    )
    config_thread.start()

    telemetry_thread = threading.Thread(
        target=telemetry_loop,
        args=(stop_event,),
        daemon=True,
    )
    telemetry_thread.start()

    try:
        master_bot.run_bot()
    finally:
        stop_event.set()
        config_thread.join(timeout=2)
        telemetry_thread.join(timeout=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
