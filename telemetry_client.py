"""telemetry_client.py

Small authenticated client for sending bot runtime telemetry to the dashboard
backend. It is dependency-free and safe to import from wrappers.

Environment variables:
  PUMP_DASHBOARD_API  Backend base URL, e.g. https://worker.example.workers.dev
  PUMP_API_TOKEN      Bearer token accepted by /api/protected/*
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class TelemetryClient:
    def __init__(self, api_base: Optional[str] = None, token: Optional[str] = None) -> None:
        self.api_base = (api_base or os.getenv("PUMP_DASHBOARD_API", "")).rstrip("/")
        self.token = token or os.getenv("PUMP_API_TOKEN", "")
        self.enabled = bool(self.api_base and self.token)

    def send(self, payload: Dict[str, Any], event_type: str = "telemetry") -> bool:
        if not self.enabled:
            return False

        body = json.dumps({
            "type": event_type,
            "ts": int(time.time() * 1000),
            "payload": payload,
        }).encode("utf-8")

        request = urllib.request.Request(
            f"{self.api_base}/api/protected/telemetry/ingest",
            data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return 200 <= response.status < 300
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            print(f"telemetry send failed: HTTP {exc.code}: {error_body}")
            return False
        except Exception as exc:
            print(f"telemetry send failed: {exc}")
            return False
