"""yin_agent.py

Yin agent:
- reflective
- contradiction-seeking
- risk-sensitive
- coherence-oriented

V2: Now reads p_G (belief state) and v_hat (volatility estimate) from MarketFrame.
- Low p_G amplifies instability: if the inference engine already doubts the
  environment is good, Yin's caution is reinforced.
- High v_hat adds a volatility risk flag: unstable environments demand more
  confirmation before Yin will clear a signal.
- last_memory feeds into the thesis for narrative continuity.
"""

from __future__ import annotations

import random
from dual_loop_state import AgentJudgment, MarketFrame, Projection

# Thresholds
LOW_BELIEF_THRESHOLD  = 0.40   # p_G below this amplifies instability
HIGH_VOLAT_THRESHOLD  = 0.25   # v_hat above this adds volatility risk flag


class YinAgent:
    role = "YIN"

    def evaluate(self, frame: MarketFrame) -> AgentJudgment:
        # ── Base instability from market structure ───────────────────────
        instability = (
            frame.dev_wallet_percent * 2
            + frame.snipers * 3
            + frame.top_ten_percent
        )

        # ── Active inference amplification ───────────────────────────
        # Low belief state means the inference engine already sees trouble.
        # Yin amplifies instability proportionally to how low p_G is.
        belief_penalty = 0.0
        if frame.p_G < LOW_BELIEF_THRESHOLD:
            belief_penalty = (LOW_BELIEF_THRESHOLD - frame.p_G) * 60.0
            instability += belief_penalty

        confidence = max(5.0, min(95.0, 85.0 - instability / 2.0))
        score = confidence - random.uniform(0, 12)

        # ── Risk flags ────────────────────────────────────────────────
        risk_flags = []

        if frame.dev_wallet_percent > 10:
            risk_flags.append("high_dev_wallet")

        if frame.snipers > 8:
            risk_flags.append("high_sniper_activity")

        if frame.top_ten_percent > 35:
            risk_flags.append("holder_concentration")

        if frame.p_G < LOW_BELIEF_THRESHOLD:
            risk_flags.append(f"low_belief_state(p_G={frame.p_G:.3f})")

        if frame.v_hat > HIGH_VOLAT_THRESHOLD:
            risk_flags.append(f"high_volatility(v_hat={frame.v_hat:.3f})")

        # ── Action selection ────────────────────────────────────────────
        if risk_flags:
            action = "DELAY"
            thesis = "Observed instability requires additional confirmation."
        elif score >= 70:
            action = "HOLD"
            thesis = "Conditions stable enough for observation."
        else:
            action = "SKIP"
            thesis = "Risk-adjusted confidence too low."

        # ── Narrative continuity from flowstate memory ──────────────────
        memory_note = ""
        if frame.last_memory:
            memory_note = f" [memory: {frame.last_memory[:80]}]"

        # ── Projection ─────────────────────────────────────────────────
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
            counter_thesis="Momentum conditions could overpower current caution.",
            risk_flags=risk_flags,
            supporting_signals={
                "instability": instability,
                "belief_penalty": belief_penalty,
                "p_G": frame.p_G,
                "v_hat": frame.v_hat,
                "risk_flags": risk_flags,
                "top_ten_percent": frame.top_ten_percent,
            },
            projection=projection,
        )
