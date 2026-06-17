"""agents/active_inference_agent.py

Active inference perception module.

Role in the stack:
- Runs as a background async task alongside the flowstate loop.
- Observes a stream of signals (price ticks, scores, events).
- Maintains a running belief P(state=Good) = p_G using a simple Bayesian update.
- Tracks volatility v_hat as an exponential moving average of absolute changes.
- Writes p_G, v_hat, and surprise into a shared InferenceState object.
- MarketFrame reads from that state each cycle before the yin/yang evaluation.

This is the perception layer. It tells the dual-loop agents what the
environment feels like — not just what the raw numbers say.
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional

log = logging.getLogger("active_inference")

# ── Config ────────────────────────────────────────────────────────────────
DEFAULT_P_G         = 0.50    # prior: neutral
DEFAULT_V_HAT       = 0.10    # prior: low volatility
ALPHA_VOLAT         = 0.20    # EMA smoothing for volatility
BELIEF_LEARN_RATE   = 0.15    # how fast belief updates per observation
SURPRISE_THRESHOLD  = 0.40    # surprise above this is salient
SLEEP_SEC           = 5       # seconds between perception ticks


# ── Shared state object ────────────────────────────────────────────────
@dataclass
class InferenceState:
    """Singleton-style shared state. MarketFrame reads p_G, v_hat, surprise."""
    p_G: float              = DEFAULT_P_G
    v_hat: float            = DEFAULT_V_HAT
    surprise: Optional[float] = None
    last_observation: Optional[float] = None
    last_updated: Optional[datetime]  = None
    tick_count: int         = 0
    salient_events: List[dict] = field(default_factory=list)


# Module-level singleton — import this wherever MarketFrame is built
INFERENCE_STATE = InferenceState()


# ── Core update functions ───────────────────────────────────────────────
def _compute_surprise(observation: float, p_G: float) -> float:
    """
    Surprise = -log P(observation | current belief).
    Observation is normalised to [0,1] where 1.0 = fully consistent with Good.
    """
    # P(obs | Good) = observation, P(obs | Bad) = 1 - observation
    p_obs = p_G * observation + (1.0 - p_G) * (1.0 - observation)
    p_obs = max(1e-9, p_obs)  # avoid log(0)
    return -math.log(p_obs)


def _update_belief(p_G: float, observation: float) -> float:
    """
    Simple Bayesian-style belief update.
    observation: float in [0,1], 1.0 = strong evidence for Good state.
    """
    # Likelihood ratio update
    p_good = p_G * observation
    p_bad  = (1.0 - p_G) * (1.0 - observation)
    total  = p_good + p_bad
    if total < 1e-9:
        return p_G  # degenerate case, no update
    new_p_G = p_good / total
    # Blend with learning rate to avoid hard jumps
    return p_G + BELIEF_LEARN_RATE * (new_p_G - p_G)


def _update_volatility(v_hat: float, prev_obs: Optional[float], obs: float) -> float:
    """EMA of absolute change between consecutive observations."""
    if prev_obs is None:
        return v_hat
    change = abs(obs - prev_obs)
    return ALPHA_VOLAT * change + (1.0 - ALPHA_VOLAT) * v_hat


# ── Single tick update ──────────────────────────────────────────────────
def observe(raw_score: float, state: InferenceState = INFERENCE_STATE) -> InferenceState:
    """
    Feed a new observation into the inference engine.

    Args:
        raw_score: float in [0, 100] — e.g. research_score() output from master_bot
                   or any normalised signal quality score.
        state:     shared InferenceState to update in-place.

    Returns the updated state.
    """
    obs = max(0.0, min(1.0, raw_score / 100.0))  # normalise to [0,1]

    surprise = _compute_surprise(obs, state.p_G)
    state.v_hat         = _update_volatility(state.v_hat, state.last_observation, obs)
    state.p_G           = _update_belief(state.p_G, obs)
    state.surprise      = surprise
    state.last_observation = obs
    state.last_updated  = datetime.utcnow()
    state.tick_count   += 1

    if surprise > SURPRISE_THRESHOLD:
        event = {
            "tick":      state.tick_count,
            "timestamp": state.last_updated.isoformat(),
            "obs":        obs,
            "surprise":   surprise,
            "p_G":        state.p_G,
            "v_hat":      state.v_hat,
        }
        state.salient_events.append(event)
        log.info(f"[inference] ⚡ salient event: {event}")

    return state


# ── Convenience: build MarketFrame-ready dict from current state ──────────
def get_inference_fields(state: InferenceState = INFERENCE_STATE) -> dict:
    """Return dict ready to unpack into MarketFrame(**get_inference_fields())."""
    return {
        "p_G":      state.p_G,
        "v_hat":    state.v_hat,
        "surprise": state.surprise,
    }


# ── Async background loop (optional: auto-feed from a signal source) ───────
async def run_inference_loop(
    signal_fn: Optional[Callable[[], float]] = None,
    sleep_sec: int = SLEEP_SEC,
    state: InferenceState = INFERENCE_STATE,
) -> None:
    """
    Run the inference loop indefinitely.

    Args:
        signal_fn: callable() -> float in [0,100]  (e.g. latest research_score)
                   If None, loop idles and waits for manual observe() calls.
        sleep_sec: seconds between ticks
        state:     shared InferenceState instance
    """
    log.info("🧠 Active inference loop starting...")
    while True:
        try:
            if signal_fn is not None:
                raw = signal_fn()
                observe(raw, state)
                log.info(
                    f"[inference] tick={state.tick_count} "
                    f"p_G={state.p_G:.3f} v_hat={state.v_hat:.3f} "
                    f"surprise={state.surprise:.3f}"
                )
        except Exception as e:
            log.error(f"[inference] loop error: {e}")
        await asyncio.sleep(sleep_sec)
