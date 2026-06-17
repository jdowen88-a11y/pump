"""orchestrator.py

Evo2 Orchestrator — multi-provider router with agent runtime integration.

Routes:
  fast    → Perplexity Sonar + OpenAI mini  (speed)
  search  → Perplexity web + xAI Grok       (current info)
  code    → Anthropic Sonnet + OpenAI deep   (code/debug)
  deep    → OpenAI deep + xAI + Gemini       (architecture/strategy)
  agent   → Yin/Yang/Arbitration runtime     (self-model/flow/simulate)

Agent route:
  Builds a MarketFrame from the active inference state + flowstate memory,
  runs YinAgent and YangAgent independently, passes both judgments through
  the ArbitrationGate, and returns a structured decision.
  Rehab trigger is surfaced to the caller if fired.
"""

from __future__ import annotations

import os
import re
import asyncio
import logging
from typing import Any, Dict, List

log = logging.getLogger("orchestrator")

# ── Provider imports ─────────────────────────────────────────────────
from providers.openai_provider      import call_openai
from providers.anthropic_provider   import call_anthropic
from providers.google_provider      import call_gemini
from providers.xai_provider         import call_xai
from providers.perplexity_provider  import call_perplexity

# ── Agent runtime imports ────────────────────────────────────────────
from dual_loop_state                import MarketFrame
from yin_agent                      import YinAgent
from yang_agent                     import YangAgent
from arbitration_gate               import ArbitrationGate
from agents.active_inference_agent  import INFERENCE_STATE, get_inference_fields, observe
from flowstate_agent                import FLOW_STATE, get_memory_fields

# Singletons
_yin_agent  = YinAgent()
_yang_agent = YangAgent()
_gate       = ArbitrationGate()


# ── Route classifier ─────────────────────────────────────────────────
def classify(user_text: str) -> str:
    t = user_text.lower()

    # Explicit mode hints always win
    m = re.search(r"\bmode\s*:\s*(fast|deep|code|search|agent)\b", t)
    if m:
        return m.group(1)

    # Agent route keywords — self-model, flow, simulation, dual-loop
    if any(k in t for k in [
        "agent", "flow state", "flowstate", "simulate", "simulation",
        "yin", "yang", "arbitration", "belief", "inference",
        "dual loop", "self model", "self-model", "vault", "memory loop",
    ]):
        return "agent"

    # Code route
    if any(k in t for k in [
        "debug", "compile", "stack trace", "unit test", "refactor",
        "class ", "def ", "import ",
    ]):
        return "code"

    # Search route
    if any(k in t for k in [
        "latest", "today", "news", "according to", "cite", "source", "url",
    ]):
        return "search"

    # Deep route
    if len(t) > 400 or any(k in t for k in [
        "prove", "derive", "theorem", "strategy", "plan", "architecture",
    ]):
        return "deep"

    return "fast"


# ── Agent route handler ───────────────────────────────────────────────
async def _run_agent_route(user_text: str) -> Dict[str, Any]:
    """
    Build a MarketFrame from live inference + flowstate state,
    run yin/yang evaluation, arbitrate, return structured result.

    The user_text is treated as the signal_id / narrative input.
    Any numeric score embedded in the text (e.g. 'score:72') is fed
    into the inference engine as a fresh observation.
    """
    # Feed any explicit score into the inference engine first
    score_match = re.search(r"score[:\s]+([0-9]+(?:\.[0-9]+)?)", user_text, re.I)
    if score_match:
        raw_score = float(score_match.group(1))
        observe(raw_score, INFERENCE_STATE)
        log.info(f"[agent] fed score={raw_score} into inference engine")

    # Build MarketFrame from shared singletons
    frame = MarketFrame(
        signal_id=user_text[:120],
        signal_type="conversation",
        **get_inference_fields(INFERENCE_STATE),
        **get_memory_fields(FLOW_STATE),
    )

    # Run agents
    yin_judgment  = _yin_agent.evaluate(frame)
    yang_judgment = _yang_agent.evaluate(frame)

    # Arbitrate
    decision = _gate.resolve(yang_judgment, yin_judgment, frame)

    # Build response
    result = {
        "route":          "agent",
        "signal_id":      frame.signal_id,
        "final_action":   decision.final_action,
        "confidence":     round(decision.confidence, 2),
        "reason":         decision.reason,
        "conflict_score": round(decision.conflict_score, 2),
        "vetoed":         decision.vetoed,
        "rehab_triggered": decision.rehab_triggered,
        "rehab_reason":   decision.rehab_reason,
        "yin": {
            "action":     yin_judgment.action,
            "confidence": round(yin_judgment.confidence, 2),
            "score":      round(yin_judgment.score, 2),
            "thesis":     yin_judgment.thesis,
            "risk_flags": yin_judgment.risk_flags,
        },
        "yang": {
            "action":     yang_judgment.action,
            "confidence": round(yang_judgment.confidence, 2),
            "score":      round(yang_judgment.score, 2),
            "thesis":     yang_judgment.thesis,
            "risk_flags": yang_judgment.risk_flags,
        },
        "inference": {
            "p_G":      round(frame.p_G, 4),
            "v_hat":    round(frame.v_hat, 4),
            "surprise": round(frame.surprise, 4) if frame.surprise else None,
        },
        "memory": {
            "last_memory":  frame.last_memory[:200] if frame.last_memory else None,
            "memory_vibe":  frame.memory_vibe,
        },
        # Surface a plain-text summary for the chat UI
        "text": (
            f"[AGENT] {decision.final_action} — {decision.reason} "
            f"(yin={yin_judgment.action} yang={yang_judgment.action} "
            f"p_G={frame.p_G:.3f} conflict={decision.conflict_score:.1f})"
            + (f" ⚠️ REHAB: {decision.rehab_reason}" if decision.rehab_triggered else "")
        ),
        "citations": [],
    }
    return result


# ── Safe provider wrapper ────────────────────────────────────────────────
async def _safe(fn, *args, **kwargs):
    try:
        return await fn(*args, **kwargs)
    except Exception as e:
        return {"text": f"[{fn.__name__} error: {e}]", "citations": []}


# ── Main route dispatcher ───────────────────────────────────────────────
async def route(
    user_text: str,
    parallel: bool = True,
    citations: bool = True,
) -> Dict[str, Any]:
    mode = classify(user_text)

    # Agent route bypasses all LLM providers — runs the yin/yang stack directly
    if mode == "agent":
        return await _run_agent_route(user_text)

    calls: List = []
    models: List[str] = []

    if mode == "fast":
        calls  = [
            _safe(call_perplexity, user_text, model=os.getenv("PERPLEXITY_MODEL", "sonar"), search=False),
            _safe(call_openai,     user_text, model=os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini")),
        ]
        models = ["perplexity:sonar", "openai:gpt-4o-mini"]

    elif mode == "search":
        calls  = [
            _safe(call_perplexity, user_text, model=os.getenv("PERPLEXITY_MODEL", "sonar"), search=True),
            _safe(call_xai,        user_text, model=os.getenv("XAI_MODEL", "grok-2-latest")),
        ]
        models = ["perplexity:sonar(web)", "xai:grok"]

    elif mode == "code":
        calls  = [
            _safe(call_anthropic, user_text, model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")),
            _safe(call_openai,    user_text, model=os.getenv("OPENAI_MODEL_DEEP", "o3")),
        ]
        models = ["anthropic:claude-sonnet-4-5", "openai:o3"]

    else:  # deep
        calls  = [
            _safe(call_openai,    user_text, model=os.getenv("OPENAI_MODEL_DEEP", "o3")),
            _safe(call_xai,       user_text, model=os.getenv("XAI_MODEL", "grok-2-latest")),
            _safe(call_gemini,    user_text, model=os.getenv("GOOGLE_MODEL", "gemini-2.0-pro")),
        ]
        models = ["openai:o3", "xai:grok", "google:gemini-2.0-pro"]

    results = await asyncio.gather(*calls) if parallel else [await c for c in calls]

    # Pick best by length (crude but effective for MVP)
    blobs   = [r.get("text", "").strip() for r in results]
    best_i  = max(range(len(blobs)), key=lambda i: len(blobs[i]))
    best    = results[best_i] if results else {"text": "No providers responded.", "citations": []}

    merged_citations: List = []
    for r in results:
        for c in r.get("citations", []) or []:
            if c not in merged_citations:
                merged_citations.append(c)

    return {
        "route":     mode,
        "models":    models,
        "text":      best.get("text", "").strip(),
        "citations": merged_citations if citations else [],
    }
