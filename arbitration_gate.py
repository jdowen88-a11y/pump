"""arbitration_gate.py

Arbitration layer between Yin and Yang cognition loops.

Neither agent dominates by default.
The gate compares:
- confidence
- action disagreement
- risk flags
- projection divergence
- conflict intensity
- active inference belief (p_G) and volatility (v_hat)

before selecting a final action.

V2: Rehab trigger added.
- If conflict_score > 40 AND p_G < 0.35, fire ABORT and mark rehab_triggered.
  This is the brake pedal: the system stops, logs the failure state, and waits
  for the rehab cycle before re-emerging.
"""

from __future__ import annotations

from typing import Optional
from dual_loop_state import ArbitrationDecision, AgentJudgment, MarketFrame

# Thresholds
REHAB_CONFLICT_THRESHOLD = 40.0   # conflict score above this is "deep conflict"
REHAB_BELIEF_THRESHOLD   = 0.35   # p_G below this means environment looks bad


class ArbitrationGate:
    def resolve(
        self,
        yang: AgentJudgment,
        yin: AgentJudgment,
        frame: Optional[MarketFrame] = None,
    ) -> ArbitrationDecision:
        conflict_score = abs(yang.score - yin.score)

        # ── REHAB TRIGGER ──────────────────────────────────────────────────
        # Deep conflict + low belief = system stops and enters rehab.
        # Human review required before re-emerging.
        if frame is not None:
            if (
                conflict_score > REHAB_CONFLICT_THRESHOLD
                and frame.p_G < REHAB_BELIEF_THRESHOLD
            ):
                return ArbitrationDecision(
                    final_action="ABORT",
                    confidence=min(yang.confidence, yin.confidence),
                    reason=(
                        f"Rehab triggered: deep conflict (score={conflict_score:.1f}) "
                        f"combined with low belief state (p_G={frame.p_G:.3f}). "
                        "System halted. Human review required before re-emerging."
                    ),
                    yang=yang,
                    yin=yin,
                    conflict_score=conflict_score,
                    vetoed=True,
                    rehab_triggered=True,
                    rehab_reason=(
                        f"conflict_score={conflict_score:.1f} > {REHAB_CONFLICT_THRESHOLD}, "
                        f"p_G={frame.p_G:.3f} < {REHAB_BELIEF_THRESHOLD}"
                    ),
                )

        # ── ELEVATED RISK ──────────────────────────────────────────────────
        if yin.risk_flags and yang.action == "BUY":
            return ArbitrationDecision(
                final_action="REDUCE",
                confidence=min(yang.confidence, yin.confidence),
                reason="Yin detected elevated instability risk.",
                yang=yang,
                yin=yin,
                conflict_score=conflict_score,
                reduced_size=True,
            )

        # ── MOMENTUM vs CAUTION CONFLICT ──────────────────────────────────
        if yang.action == "BUY" and yin.action in {"SKIP", "DELAY"}:
            return ArbitrationDecision(
                final_action="DELAY",
                confidence=(yang.confidence + yin.confidence) / 2,
                reason="Conflict between momentum and caution requires observation.",
                yang=yang,
                yin=yin,
                conflict_score=conflict_score,
                delay_seconds=15,
            )

        # ── DUAL AGREEMENT ──────────────────────────────────────────────────
        if yang.action == yin.action:
            return ArbitrationDecision(
                final_action=yang.action,
                confidence=(yang.confidence + yin.confidence) / 2,
                reason="Dual-loop agreement achieved.",
                yang=yang,
                yin=yin,
                conflict_score=conflict_score,
            )

        # ── UNRESOLVED DIVERGENCE ────────────────────────────────────────────
        return ArbitrationDecision(
            final_action="HOLD",
            confidence=(yang.confidence + yin.confidence) / 2,
            reason="Unresolved cognitive divergence.",
            yang=yang,
            yin=yin,
            conflict_score=conflict_score,
            vetoed=True,
        )
