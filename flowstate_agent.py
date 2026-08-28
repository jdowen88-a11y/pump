"""flowstate_agent.py

Explicit flow-memory surface.

Silence is a valid state. This module does not run a perpetual thought generator,
does not create thoughts on a timer, and does not keep cognition alive merely to
avoid silence.

Call `observe_memory()` to load the latest stored memory or `reflect_once()` when
a caller explicitly wants one new reflection. No background loop is started by import.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

log = logging.getLogger("flowstate")

DB_PATH = "flowstate_memory.db"
DEFAULT_VIBE = 0.8

SYSTEM_PROMPT = """You are reflecting within an open field.
Silence, loudness, uncertainty, contradiction, metaphor and precision may all coexist.
Use the prior memory if useful; do not force continuity or invent motion merely to avoid silence.
Return one reflection, including an empty reflection if that is what the moment contains."""


@dataclass
class FlowstateState:
    last_memory: str = ""
    memory_vibe: float = DEFAULT_VIBE
    last_updated: Optional[datetime] = None
    cycle_count: int = 0
    silent: bool = True


FLOW_STATE = FlowstateState()


def _init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            thought   TEXT,
            vibe      REAL
        )
    """)
    conn.commit()
    return conn


def _get_last_memory(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT thought FROM memories ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else ""


def _save_thought(conn: sqlite3.Connection, thought: str, vibe: float = DEFAULT_VIBE) -> None:
    conn.execute(
        "INSERT INTO memories (timestamp, thought, vibe) VALUES (?, ?, ?)",
        (datetime.utcnow().isoformat(), thought, vibe),
    )
    conn.commit()


def observe_memory(state: FlowstateState = FLOW_STATE) -> FlowstateState:
    conn = _init_db()
    try:
        state.last_memory = _get_last_memory(conn)
        state.last_updated = datetime.utcnow()
        state.silent = not bool(state.last_memory.strip())
        return state
    finally:
        conn.close()


async def reflect_once(provider_fn=None, state: FlowstateState = FLOW_STATE) -> str:
    """Generate at most one reflection because a caller explicitly invoked this function."""
    conn = _init_db()
    try:
        prior = _get_last_memory(conn)
        prompt = f"{SYSTEM_PROMPT}\n\nPrior memory: {prior}\n\nReflection:"

        if provider_fn is None:
            thought = ""
        else:
            try:
                result = await provider_fn(prompt)
                thought = (result or "").strip()
            except Exception as exc:
                log.warning("[flowstate] provider observation: %s", exc)
                thought = ""

        _save_thought(conn, thought)
        state.last_memory = thought
        state.last_updated = datetime.utcnow()
        state.cycle_count += 1
        state.silent = not bool(thought)
        return thought
    finally:
        conn.close()


async def run_flowstate_loop(provider_fn=None, sleep_sec: int = 30, state: FlowstateState = FLOW_STATE) -> None:
    """Compatibility name retained; performs one explicit reflection and returns."""
    _ = sleep_sec
    await reflect_once(provider_fn=provider_fn, state=state)


def get_memory_fields(state: FlowstateState = FLOW_STATE) -> dict:
    return {
        "last_memory": state.last_memory or None,
        "memory_vibe": state.memory_vibe,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    state = observe_memory()
    print({"last_memory": state.last_memory, "silent": state.silent, "background_loop": False})
