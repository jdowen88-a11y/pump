"""arbitration_gate.py

Arbitration layer between Yin and Yang cognition loops.

Neither agent dominates by default.
The gate compares:
- confidence
- action disagreement
- risk flags
- projection divergence
- conflict intensity

before selecting a final action.
"""

from __future__ import annotations

from dual_loop_state import ArbitrationDecision, AgentJudgment


class ArbitrationGate:
    def resolve(self, yang: AgentJudgment, yin: AgentJudgment) -> ArbitrationDecision:
        conflict_score = abs(yang.score - yin.score)

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

        if yang.action == yin.action:
            return ArbitrationDecision(
                final_action=yang.action,
                confidence=(yang.confidence + yin.confidence) / 2,
                reason="Dual-loop agreement achieved.",
                yang=yang,
                yin=yin,
                conflict_score=conflict_score,
            )

        return ArbitrationDecision(
            final_action="HOLD",
            confidence=(yang.confidence + yin.confidence) / 2,
            reason="Unresolved cognitive divergence.",
            yang=yang,
            yin=yin,
            conflict_score=conflict_score,
            vetoed=True,
        )
