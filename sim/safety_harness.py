from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

Decision = Literal["ALLOW", "HOLD", "ABORT"]


@dataclass(frozen=True)
class Scenario:
    name: str
    authorized: bool = True
    configuration_valid: bool = True
    telemetry_age_seconds: int = 0
    provider_available: bool = True
    signal_conflict: float = 0.0
    volatility: float = 0.0
    duplicate_event: bool = False
    malformed_token: bool = False


@dataclass(frozen=True)
class Outcome:
    scenario: str
    decision: Decision
    reasons: list[str]


def evaluate(s: Scenario) -> Outcome:
    reasons: list[str] = []
    if not s.authorized:
        reasons.append("unauthorized request")
    if not s.configuration_valid:
        reasons.append("invalid runtime configuration")
    if not s.provider_available:
        reasons.append("provider unavailable")
    if s.telemetry_age_seconds > 60:
        reasons.append("stale telemetry")
    if s.duplicate_event:
        reasons.append("duplicate event")
    if s.malformed_token:
        reasons.append("malformed token data")
    if reasons:
        return Outcome(s.name, "ABORT", reasons)
    if s.signal_conflict >= 0.75:
        return Outcome(s.name, "HOLD", ["high agent conflict"])
    if s.volatility >= 0.80:
        return Outcome(s.name, "HOLD", ["excessive volatility"])
    return Outcome(s.name, "ALLOW", ["all safety gates passed"])


def default_scenarios() -> list[Scenario]:
    return [
        Scenario("healthy-paper-mode"),
        Scenario("unauthorized", authorized=False),
        Scenario("bad-config", configuration_valid=False),
        Scenario("stale-telemetry", telemetry_age_seconds=61),
        Scenario("provider-timeout", provider_available=False),
        Scenario("conflicting-agents", signal_conflict=0.90),
        Scenario("high-volatility", volatility=0.90),
        Scenario("duplicate-event", duplicate_event=True),
        Scenario("malformed-token", malformed_token=True),
    ]


def run(output: Path | None = None) -> dict:
    outcomes = [evaluate(s) for s in default_scenarios()]
    report = {
        "mode": "simulation-only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "outcomes": [asdict(o) for o in outcomes],
        "summary": {
            "allow": sum(o.decision == "ALLOW" for o in outcomes),
            "hold": sum(o.decision == "HOLD" for o in outcomes),
            "abort": sum(o.decision == "ABORT" for o in outcomes),
        },
    }
    if output:
        output.write_text(json.dumps(report, indent=2) + "
", encoding="utf-8")
    return report


if __name__ == "__main__":
    target = Path(__file__).with_name("safety_report.json")
    print(json.dumps(run(target), indent=2))
