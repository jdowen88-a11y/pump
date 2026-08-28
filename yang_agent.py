"""yang_agent.py — expressive Yang signal.

Yang describes momentum and opportunity. Its action label is a proposal, never an
automatic market order and never a permission verdict over Yin.
"""

from __future__ import annotations
import random
from dual_loop_state import AgentJudgment, MarketFrame, Projection

HIGH_BELIEF_REFERENCE = 0.65
OPPORT_VOLAT_LOW = 0.08
OPPORT_VOLAT_HIGH = 0.30


class YangAgent:
    role = "YANG"

    def evaluate(self, frame: MarketFrame) -> AgentJudgment:
        momentum = frame.buy_volume - frame.sell_volume
        confidence = max(5.0, min(95.0, 50.0 + momentum / 1000.0))
        belief_delta = max(0.0, frame.p_G - HIGH_BELIEF_REFERENCE) * 40.0
        confidence = min(95.0, confidence + belief_delta)

        volatility_note = ""
        if frame.v_hat > OPPORT_VOLAT_HIGH:
            confidence = max(5.0, confidence * (1.0 - (frame.v_hat - OPPORT_VOLAT_HIGH) * 2.0))
            volatility_note = "high_volatility"
        elif frame.v_hat > OPPORT_VOLAT_LOW:
            volatility_note = "volatility_present"

        score = confidence + random.uniform(-5, 8)
        if score >= 75:
            action = "BUY"
            thesis = "Yang currently sees strong momentum."
        elif score >= 55:
            action = "HOLD"
            thesis = "Yang sees an incomplete opportunity signal."
        else:
            action = "SKIP"
            thesis = "Yang currently sees little momentum."

        memory_note = f" [memory: {frame.last_memory[:80]}]" if frame.last_memory else ""
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
            thesis=thesis + memory_note,
            counter_thesis="Caution may express differently; both views remain present.",
            risk_flags=[volatility_note] if volatility_note else [],
            supporting_signals={
                "momentum": momentum,
                "belief_delta": belief_delta,
                "p_G": frame.p_G,
                "v_hat": frame.v_hat,
                "volatility_note": volatility_note,
                "market_cap": frame.market_cap,
                "holders": frame.holders,
            },
            projection=projection,
        )
