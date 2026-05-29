"""yin_agent.py

Yin agent:
- reflective
- contradiction-seeking
- risk-sensitive
- coherence-oriented

The Yin agent receives the same market frame as the Yang agent but forms
its own independent thesis and projection.
"""

from __future__ import annotations

import random
from dual_loop_state import AgentJudgment, MarketFrame, Projection


class YinAgent:
    role = "YIN"

    def evaluate(self, frame: MarketFrame) -> AgentJudgment:
        instability = (
            frame.dev_wallet_percent * 2
            + frame.snipers * 3
            + frame.top_ten_percent
        )

        confidence = max(5.0, min(95.0, 85.0 - instability / 2.0))
        score = confidence - random.uniform(0, 12)

        risk_flags = []

        if frame.dev_wallet_percent > 10:
            risk_flags.append("high_dev_wallet")

        if frame.snipers > 8:
            risk_flags.append("high_sniper_activity")

        if frame.top_ten_percent > 35:
            risk_flags.append("holder_concentration")

        if risk_flags:
            action = "DELAY"
            thesis = "Observed instability requires additional confirmation."
        elif score >= 70:
            action = "HOLD"
            thesis = "Conditions stable enough for observation."
        else:
            action = "SKIP"
            thesis = "Risk-adjusted confidence too low."

        projection = Projection(
            bull_case="Controlled sustained growth.",
            bear_case="Liquidity collapse and confidence evaporation.",
            base_case="Choppy uncertain expansion.",
            confidence=confidence,
            price_path=[[i, random.uniform(0.7, 1.3)] for i in range(24)],
            volume_path=[random.uniform(1, 5) for _ in range(24)],
        )

        return AgentJudgment(
            role=self.role,
            action=action,
            confidence=confidence,
            score=score,
            thesis=thesis,
            counter_thesis="Momentum conditions could overpower current caution.",
            risk_flags=risk_flags,
            supporting_signals={
                "instability": instability,
                "risk_flags": risk_flags,
                "top_ten_percent": frame.top_ten_percent,
            },
            projection=projection,
        )
