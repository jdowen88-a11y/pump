"""yang_agent.py

Yang agent:
- action-oriented
- opportunity-seeking
- momentum-sensitive
- execution-biased

The Yang agent generates its own independent thesis and projection.
"""

from __future__ import annotations

import random
from dual_loop_state import AgentJudgment, MarketFrame, Projection


class YangAgent:
    role = "YANG"

    def evaluate(self, frame: MarketFrame) -> AgentJudgment:
        momentum = frame.buy_volume - frame.sell_volume
        confidence = max(5.0, min(95.0, 50.0 + momentum / 1000.0))
        score = confidence + random.uniform(-5, 8)

        if score >= 75:
            action = "BUY"
            thesis = "Momentum expansion likely continuing."
        elif score >= 55:
            action = "HOLD"
            thesis = "Potential entry forming but incomplete."
        else:
            action = "SKIP"
            thesis = "Insufficient momentum alignment."

        projection = Projection(
            bull_case="Rapid momentum continuation.",
            bear_case="Sharp liquidity reversal.",
            base_case="Short-term volatility before trend selection.",
            confidence=confidence,
            price_path=[[i, random.uniform(0.8, 1.9)] for i in range(24)],
            volume_path=[random.uniform(1, 8) for _ in range(24)],
        )

        return AgentJudgment(
            role=self.role,
            action=action,
            confidence=confidence,
            score=score,
            thesis=thesis,
            counter_thesis="Risk conditions may be hidden.",
            risk_flags=[],
            supporting_signals={
                "momentum": momentum,
                "market_cap": frame.market_cap,
                "holders": frame.holders,
            },
            projection=projection,
        )
