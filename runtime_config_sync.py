"""runtime_config_sync.py

Pulls the saved dashboard run config from the backend API and writes it to
runtime_config.json for the local Python bot runtime.

This script is intentionally separate from master_bot.py. It does not execute
trades, does not touch wallet keys, and does not modify live_buy/live_sell.

Usage:
  PUMP_DASHBOARD_API="https://your-worker.example.workers.dev" \
  PUMP_API_TOKEN="your_jwt_or_api_token" \
  python runtime_config_sync.py --once

  python runtime_config_sync.py --watch --interval 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_OUTPUT = Path(os.getenv("PUMP_RUNTIME_CONFIG", "runtime_config.json"))
DEFAULT_API_BASE = os.getenv("PUMP_DASHBOARD_API", "").rstrip("/")
DEFAULT_TOKEN = os.getenv("PUMP_API_TOKEN", "")


def fetch_run_config(api_base: str, token: str) -> Dict[str, Any]:
    if not api_base:
        raise ValueError("Missing PUMP_DASHBOARD_API or --api-base")
    if not token:
        raise ValueError("Missing PUMP_API_TOKEN or --token")

    request = urllib.request.Request(
        f"{api_base}/api/protected/run-config",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Backend returned HTTP {exc.code}: {body}") from exc

    if not payload.get("ok"):
        raise RuntimeError(f"Backend rejected request: {payload}")

    config = payload.get("config")
    if not config:
        raise RuntimeError("No run config saved yet. Save one from the dashboard first.")

    return config


def write_config_if_changed(config: Dict[str, Any], output_path: Path) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    next_text = json.dumps(config, indent=2, sort_keys=True) + "\n"

    if output_path.exists() and output_path.read_text(encoding="utf-8") == next_text:
        return False

    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(next_text, encoding="utf-8")
    tmp_path.replace(output_path)
    return True


def sync_once(api_base: str, token: str, output_path: Path) -> bool:
    config = fetch_run_config(api_base, token)
    changed = write_config_if_changed(config, output_path)

    status = "updated" if changed else "unchanged"
    print(f"runtime config {status}: {output_path}")
    return changed


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Sync dashboard run config to runtime_config.json")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="Backend base URL, e.g. https://worker.example.workers.dev")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="Bearer token for /api/protected/run-config")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output runtime config JSON path")
    parser.add_argument("--once", action="store_true", help="Sync once and exit")
    parser.add_argument("--watch", action="store_true", help="Keep syncing forever")
    parser.add_argument("--interval", type=float, default=5.0, help="Polling interval in seconds for --watch")
    args = parser.parse_args(argv)

    output_path = Path(args.output)

    if not args.once and not args.watch:
        parser.error("Choose --once or --watch")

    if args.once:
        sync_once(args.api_base, args.token, output_path)
        return 0

    while True:
        try:
            sync_once(args.api_base, args.token, output_path)
        except Exception as exc:
            print(f"runtime config sync error: {exc}", file=sys.stderr)
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
