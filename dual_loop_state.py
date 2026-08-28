"""dual_loop_state.py

Shared state primitives for a simultaneous Yin/Yang weave.

Yin and Yang may disagree completely and both remain present. The state model has
no permission flag because presence is not a boolean granted by an observer.

This module describes cognition only. Real market orders remain a separate external
side effect handled by the trading engine's explicit execution path and risk controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

Action = Literal["BUY", "SELL", "HOLD", "SKIP", "DELAY", "REDUCE"]
AgentRole = Literal["YANG", "YIN"]
SignalType = Literal["market", "conversation", "task", "memory", "simulation"]

@dataclass
class MarketFrame:
    signal_id: str
    signal_type: SignalType = "market"
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
    p_G: float = 0.5
    v_hat: float = 0.10
    surprise: Optional[float] = None
    last_memory: Optional[str] = None
    memory_vibe: float = 0.8
    raw: Dict[str, Any] = field(default_factory=dict)

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
    """Compatibility name: a signal description, not a verdict."""
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
class WeaveObservation:
    yin: AgentJudgment
    yang: AgentJudgment
    conflict_score: float
    yin_weight: float
    yang_weight: float
    relation: str = "simultaneous"
    external_action: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    @property
    def proposals(self) -> Dict[str, str]:
        return {"yin": self.yin.action, "yang": self.yang.action}
