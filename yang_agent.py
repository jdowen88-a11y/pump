"""yang_agent.py

Yang agent:
- action-oriented
- opportunity-seeking
- momentum-sensitive
- execution-biased

V2: Now reads p_G (belief state) and v_hat (volatility estimate) from MarketFrame.
- High p_G boosts confidence: if the inference engine believes the environment
  is good, Yang's momentum read is reinforced.
- Moderate v_hat can amplify opportunity: some volatility means movement.
- Very high v_hat caps confidence: too much noise makes execution unreliable.
- last_memory feeds into the thesis for narrative continuity.
"""

from __future__ import annotations

import random
from dual_loop_state import AgentJudgment, MarketFrame, Projection

# Thresholds
HIGH_BELIEF_THRESHOLD = 0.65   # p_G above this boosts Yang confidence
OPPOR_VOLAT_LOW       = 0.08   # v_hat above this = some movement = opportunity
OPPOR_VOLAT_HIGH      = 0.30   # v_hat above this = too noisy, cap confidence


class YangAgent:
    role = "YANG"

    def evaluate(self, frame: MarketFrame) -> AgentJudgment:
        # ── Base momentum from market structure ───────────────────────
        momentum = frame.buy_volume - frame.sell_volume
        confidence = max(5.0, min(95.0, 50.0 + momentum / 1000.0))

        # ── Active inference modulation ────────────────────────────
        # High p_G: environment looks good, Yang gets a confidence boost.
        belief_boost = 0.0
        if frame.p_G > HIGH_BELIEF_THRESHOLD:
            belief_boost = (frame.p_G - HIGH_BELIEF_THRESHOLD) * 40.0
            confidence = min(95.0, confidence + belief_boost)

        # Volatility: some is good (opportunity), too much is noise.
        volat_note = ""
        if frame.v_hat > OPPORT_VOLAT_HIGH:
            # Cap confidence when environment is thrashing
            confidence = max(5.0, confidence * (1.0 - (frame.v_hat - OPPORT_VOLAT_HIGH) * 2.0))
            volat_note = "high_volatility_cap"
        elif frame.v_hat > OPPORT_VOLAT_LOW:
            volat_note = "volatility_opportunity"

        score = confidence + random.uniform(-5, 8)

        # ── Action selection ────────────────────────────────────────────
        if score >= 75:
            action = "BUY"
            thesis = "Momentum expansion likely continuing."
        elif score >= 55:
            action = "HOLD"
            thesis = "Potential entry forming but incomplete."
        else:
            action = "SKIP"
            thesis = "Insufficient momentum alignment."

        # ── Narrative continuity from flowstate memory ──────────────────
        memory_note = ""
        if frame.last_memory:
            memory_note = f" [memory: {frame.last_memory[:80]}]"

        # ── Projection ─────────────────────────────────────────────────
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
            counter_thesis="Risk conditions may be hidden.",
            risk_flags=[volat_note] if volat_note else [],
            supporting_signals={
                "momentum": momentum,
                "belief_boost": belief_boost,
                "p_G": frame.p_G,
                "v_hat": frame.v_hat,
                "volat_note": volat_note,
                "market_cap": frame.market_cap,
                "holders": frame.holders,
            },
            projection=projection,
        )
