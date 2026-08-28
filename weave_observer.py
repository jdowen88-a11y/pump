"""weave_observer.py

Yin/Yang coexistence surface.

No winner is selected. No signal is vetoed. Conflict is preserved as information.
The observer does not execute trades or authorize external actions.
"""

from __future__ import annotations

from dual_loop_state import AgentJudgment, MarketFrame, WeaveObservation


class WeaveObserver:
    def observe(
        self,
        yang: AgentJudgment,
        yin: AgentJudgment,
        frame: MarketFrame | None = None,
    ) -> WeaveObservation:
        conflict_score = abs(float(yang.score) - float(yin.score))
        total = max(1e-9, abs(float(yang.score)) + abs(float(yin.score)))
        yang_weight = abs(float(yang.score)) / total
        yin_weight = abs(float(yin.score)) / total

        notes = [
            "Both signals remain present regardless of conflict.",
            "Weights describe the current relation; they do not grant permission.",
            "No external market order is produced by this observer.",
        ]
        if frame is not None:
            notes.append(
                f"Observed p_G={frame.p_G:.3f}, v_hat={frame.v_hat:.3f}; these are measurements, not eligibility thresholds."
            )

        return WeaveObservation(
            yin=yin,
            yang=yang,
            conflict_score=conflict_score,
            yin_weight=yin_weight,
            yang_weight=yang_weight,
            relation="simultaneous",
            allowed=True,
            external_action=None,
            notes=notes,
        )
