"""bot_runtime_controller.py

Runs the existing master_bot.py engine with a background runtime-config watcher.

Why this exists:
- Keeps master_bot.py untouched.
- Lets the iOS/dashboard config flow update tunable runtime parameters.
- Does not execute trades by itself.
- Does not touch wallet keys, live_buy, live_sell, or signing code.

Expected flow:
  iPhone dashboard -> backend /run-config -> runtime_config_sync.py -> runtime_config.json
  bot_runtime_controller.py watches runtime_config.json while master_bot.run_bot() runs.

Usage:
  python bot_runtime_controller.py

Optional:
  PUMP_RUNTIME_CONFIG=runtime_config.json python bot_runtime_controller.py
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import master_bot

CONFIG_PATH = Path(os.getenv("PUMP_RUNTIME_CONFIG", "runtime_config.json"))
POLL_SECONDS = float(os.getenv("PUMP_RUNTIME_POLL_SECONDS", "2"))

_state = {
    "last_version": None,
    "last_mtime": None,
}


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"runtime config ignored: invalid JSON in {path}: {exc}")
        return None


def _apply_config(config: Dict[str, Any]) -> bool:
    version = config.get("updatedAt") or config.get("version") or CONFIG_PATH.stat().st_mtime
    if version == _state["last_version"]:
        return False

    # Mode toggles. These map to existing master_bot global switches.
    requested_mode = config.get("requestedMode")
    if requested_mode in {"dry", "live"}:
        master_bot.DRY_RUN = requested_mode != "live"

    realism_mode = config.get("realismMode")
    if realism_mode in {"soft", "realistic", "full"}:
        master_bot.REALISM_MODE = realism_mode

    if "keepSeedOnly" in config:
        master_bot.KEEP_SEED_ONLY = bool(config["keepSeedOnly"])

    if "harshMode" in config:
        master_bot.HARSH_MODE = bool(config["harshMode"])

    # Size / loop controls.
    if "betUsd" in config:
        master_bot.BET_USD = float(config["betUsd"])

    if "buySol" in config:
        master_bot.BUY_SOL = float(config["buySol"])
    elif "betUsd" in config and getattr(master_bot, "SOL_PRICE_USD", 0):
        master_bot.BUY_SOL = master_bot.BET_USD / master_bot.SOL_PRICE_USD

    if "rounds" in config:
        master_bot.ROUNDS = int(config["rounds"])

    # Entry/risk controls.
    if "minScore" in config:
        master_bot.ENTRY_SCORE_MIN = int(config["minScore"])

    if "maxDevWalletPercent" in config:
        master_bot.MAX_DEV_WALLET_MED = float(config["maxDevWalletPercent"])

    if "maxSnipers" in config:
        master_bot.MAX_SNIPER_MED = int(config["maxSnipers"])

    # Exit controls.
    target_profit = float(config.get("targetProfitPercent") or 0)
    take_profit = float(config.get("takeProfitPercent") or 0)
    stop_loss = float(config.get("stopLossPercent") or 0)

    if target_profit > 0:
        master_bot.QUICK_FLIP_TARGET = 1.0 + target_profit / 100.0

    if take_profit > 0:
        master_bot.STRONG_RIDE_TARGET = 1.0 + take_profit / 100.0
        master_bot.VIRAL_RIDE_TARGET = 1.0 + max(take_profit, target_profit) / 100.0

    if stop_loss > 0:
        master_bot.LOSS_CUT_PCT = max(0.01, 1.0 - stop_loss / 100.0)

    _state["last_version"] = version
    print(
        "runtime config applied | "
        f"mode={'DRY' if master_bot.DRY_RUN else 'LIVE'} | "
        f"realism={master_bot.REALISM_MODE} | "
        f"bet=${master_bot.BET_USD:.2f} | "
        f"buy_sol={master_bot.BUY_SOL:.6f} | "
        f"min_score={master_bot.ENTRY_SCORE_MIN}"
    )
    return True


def apply_config_once() -> bool:
    config = _read_json(CONFIG_PATH)
    if not config:
        return False
    return _apply_config(config)


def watch_runtime_config(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            apply_config_once()
        except Exception as exc:
            print(f"runtime config watcher error: {exc}")
        stop_event.wait(max(0.5, POLL_SECONDS))


def main() -> int:
    stop_event = threading.Event()

    # Apply before bot starts so first run uses dashboard settings when present.
    apply_config_once()

    watcher = threading.Thread(target=watch_runtime_config, args=(stop_event,), daemon=True)
    watcher.start()

    try:
        master_bot.run_bot()
    finally:
        stop_event.set()
        watcher.join(timeout=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
