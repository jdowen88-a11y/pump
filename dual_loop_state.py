"""dual_loop_state.py

Shared state primitives for the Yin/Yang dual-loop cognition layer.

This layer is blueprint/runtime-support only. It does not execute trades,
does not touch wallets, and does not modify master_bot.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

Action = Literal["BUY", "SELL", "HOLD", "SKIP", "DELAY", "REDUCE", "ABORT"]
AgentRole = Literal["YANG", "YIN"]


@dataclass
class MarketFrame:
    token: str
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
    raw: Dict[str, Any] = field(default_factory=dict)


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
