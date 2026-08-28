"""yin_agent.py — reflective Yin signal.

Yin describes caution, instability and contrary evidence. It does not clear, veto,
or grant permission to any other signal. Its market-oriented action label is a proposal,
not an executed order.
"""

from __future__ import annotations
import random
from dual_loop_state import AgentJudgment, MarketFrame, Projection

LOW_BELIEF_REFERENCE = 0.40
HIGH_VOLAT_REFERENCE = 0.25


class YinAgent:
    role = "YIN"

    def evaluate(self, frame: MarketFrame) -> AgentJudgment:
        instability = frame.dev_wallet_percent * 2 + frame.snipers * 3 + frame.top_ten_percent
        belief_delta = max(0.0, LOW_BELIEF_REFERENCE - frame.p_G) * 60.0
        instability += belief_delta
        confidence = max(5.0, min(95.0, 85.0 - instability / 2.0))
        score = confidence - random.uniform(0, 12)

        observations = []
        if frame.dev_wallet_percent > 10: observations.append("high_dev_wallet")
        if frame.snipers > 8: observations.append("high_sniper_activity")
        if frame.top_ten_percent > 35: observations.append("holder_concentration")
        if frame.p_G < LOW_BELIEF_REFERENCE: observations.append(f"low_p_G({frame.p_G:.3f})")
        if frame.v_hat > HIGH_VOLAT_REFERENCE: observations.append(f"high_v_hat({frame.v_hat:.3f})")

        if observations:
            action = "DELAY"
            thesis = "Caution signal is high; preserve this view alongside Yang."
        elif score >= 70:
            action = "HOLD"
            thesis = "Caution signal is relatively quiet."
        else:
            action = "SKIP"
            thesis = "Yin currently favors non-entry."

        memory_note = f" [memory: {frame.last_memory[:80]}]" if frame.last_memory else ""
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
            thesis=thesis + memory_note,
            counter_thesis="Momentum may express differently; both views remain present.",
            risk_flags=observations,
            supporting_signals={
                "instability": instability,
                "belief_delta": belief_delta,
                "p_G": frame.p_G,
                "v_hat": frame.v_hat,
                "observations": observations,
                "top_ten_percent": frame.top_ten_percent,
            },
            projection=projection,
        )
