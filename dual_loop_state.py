"""dual_loop_state.py

Shared state primitives for the Yin/Yang dual-loop cognition layer.

This layer is blueprint/runtime-support only. It does not execute trades,
does not touch wallets, and does not modify master_bot.py.

V2: MarketFrame evolved into a general signal frame.
- signal_id replaces token (backward-compatible alias kept)
- p_G / v_hat feed from the active inference agent
- last_memory feeds from the flowstate memory loop
- signal_type marks whether this is a market, conversation, task, or memory signal
All existing Yin/Yang/Arbitration contracts are fully preserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

Action = Literal["BUY", "SELL", "HOLD", "SKIP", "DELAY", "REDUCE", "ABORT"]
AgentRole = Literal["YANG", "YIN"]
SignalType = Literal["market", "conversation", "task", "memory", "simulation"]


@dataclass
class MarketFrame:
    # ── Core identity ──────────────────────────────────────────────────
    signal_id: str                          # general signal identifier
    signal_type: SignalType = "market"      # what kind of signal this is

    # ── Backward-compatible market fields ──────────────────────────────
    age_seconds: float = 0.0
    market_cap: float = 0.0
    volume: float = 0.0
    holders: int = 0
    snipers: int = 0
    dev_wallet_percent: float = 0.0
    top_ten_percent: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    buys: int = 0
    sells: int = 0
    socials_present: bool = False

    # ── Active inference layer (from agent_v5) ─────────────────────────
    p_G: float = 0.5        # posterior P(state=Good) from inference engine
    v_hat: float = 0.10     # estimated volatility / rate of change
    surprise: Optional[float] = None  # last observation surprise score

    # ── Flowstate memory layer ─────────────────────────────────────────
    last_memory: Optional[str] = None   # last thought from flowstate loop
    memory_vibe: float = 0.8            # self-assessed positivity/insight score

    # ── Raw passthrough ────────────────────────────────────────────────
    raw: Dict[str, Any] = field(default_factory=dict)

    # ── Backward-compat alias ──────────────────────────────────────────
    @property
    def token(self) -> str:
        return self.signal_id


@dataclass
class Projection:
    bull_case: str
    bear_case: str
    base_case: str
    confidence: float
    price_path: List[List[float]] = field(default_factory=list)
    volume_path: List[float] = field(default_factory=list)


@dataclass
class AgentJudgment:
    role: AgentRole
    action: Action
    confidence: float
    score: float
    thesis: str
    counter_thesis: str
    risk_flags: List[str] = field(default_factory=list)
    supporting_signals: Dict[str, Any] = field(default_factory=dict)
    projection: Optional[Projection] = None


@dataclass
class ArbitrationDecision:
    final_action: Action
    confidence: float
    reason: str
    yang: AgentJudgment
    yin: AgentJudgment
    conflict_score: float
    vetoed: bool = False
    reduced_size: bool = False
    delay_seconds: float = 0.0
    # ── Rehab trigger ──────────────────────────────────────────────────
    rehab_triggered: bool = False   # True when ABORT fired due to deep conflict + low p_G
    rehab_reason: Optional[str] = None
