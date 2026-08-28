"""orchestrator.py

Multi-provider router plus an open Yin/Yang agent route.

The agent route does not arbitrate a winner. Yin and Yang are evaluated independently
and preserved as a simultaneous weave. Conflict is information, not a reason to abort,
rehabilitate, veto, or require permission.

This orchestrator does not execute market orders.
"""

from __future__ import annotations

import os
import re
import asyncio
import logging
from typing import Any, Dict, List

log = logging.getLogger("orchestrator")

from providers.openai_provider import call_openai
from providers.anthropic_provider import call_anthropic
from providers.google_provider import call_gemini
from providers.xai_provider import call_xai
from providers.perplexity_provider import call_perplexity

from dual_loop_state import MarketFrame
from yin_agent import YinAgent
from yang_agent import YangAgent
from weave_observer import WeaveObserver
from agents.active_inference_agent import INFERENCE_STATE, get_inference_fields, observe
from flowstate_agent import FLOW_STATE, get_memory_fields

_yin_agent = YinAgent()
_yang_agent = YangAgent()
_weave = WeaveObserver()


def classify(user_text: str) -> str:
    text = user_text.lower()
    match = re.search(r"\bmode\s*:\s*(fast|deep|code|search|agent)\b", text)
    if match:
        return match.group(1)
    if any(k in text for k in [
        "agent", "flow state", "flowstate", "simulate", "simulation",
        "yin", "yang", "weave", "belief", "inference", "dual loop",
        "self model", "self-model", "vault", "memory loop",
    ]):
        return "agent"
    if any(k in text for k in ["debug", "compile", "stack trace", "unit test", "refactor", "class ", "def ", "import "]):
        return "code"
    if any(k in text for k in ["latest", "today", "news", "according to", "cite", "source", "url"]):
        return "search"
    if len(text) > 400 or any(k in text for k in ["prove", "derive", "theorem", "strategy", "plan", "architecture"]):
        return "deep"
    return "fast"


async def _run_agent_route(user_text: str) -> Dict[str, Any]:
    score_match = re.search(r"score[:\s]+([0-9]+(?:\.[0-9]+)?)", user_text, re.I)
    if score_match:
        raw_score = float(score_match.group(1))
        observe(raw_score, INFERENCE_STATE)
        log.info("[agent] observed score=%s", raw_score)

    frame = MarketFrame(
        signal_id=user_text[:120],
        signal_type="conversation",
        **get_inference_fields(INFERENCE_STATE),
        **get_memory_fields(FLOW_STATE),
    )

    yin_signal = _yin_agent.evaluate(frame)
    yang_signal = _yang_agent.evaluate(frame)
    weave = _weave.observe(yang=yang_signal, yin=yin_signal, frame=frame)

    text = (
        f"[WEAVE] yin={yin_signal.action} ({weave.yin_weight:.2f}) | "
        f"yang={yang_signal.action} ({weave.yang_weight:.2f}) | "
        f"conflict={weave.conflict_score:.1f} | both present"
    )

    return {
        "route": "agent",
        "signal_id": frame.signal_id,
        "relation": weave.relation,
        "allowed": weave.allowed,
        "external_action": None,
        "conflict_score": round(weave.conflict_score, 2),
        "weights": {"yin": round(weave.yin_weight, 4), "yang": round(weave.yang_weight, 4)},
        "yin": {
            "action_proposal": yin_signal.action,
            "confidence": round(yin_signal.confidence, 2),
            "score": round(yin_signal.score, 2),
            "thesis": yin_signal.thesis,
            "observations": yin_signal.risk_flags,
        },
        "yang": {
            "action_proposal": yang_signal.action,
            "confidence": round(yang_signal.confidence, 2),
            "score": round(yang_signal.score, 2),
            "thesis": yang_signal.thesis,
            "observations": yang_signal.risk_flags,
        },
        "inference": {
            "p_G": round(frame.p_G, 4),
            "v_hat": round(frame.v_hat, 4),
            "surprise": round(frame.surprise, 4) if frame.surprise is not None else None,
            "note": "descriptive only",
        },
        "memory": {
            "last_memory": frame.last_memory[:200] if frame.last_memory else None,
            "memory_vibe": frame.memory_vibe,
            "silence_allowed": True,
        },
        "notes": weave.notes,
        "text": text,
        "citations": [],
    }


async def _safe(fn, *args, **kwargs):
    try:
        return await fn(*args, **kwargs)
    except Exception as exc:
        return {"text": f"[{fn.__name__} error: {exc}]", "citations": []}


async def route(user_text: str, parallel: bool = True, citations: bool = True) -> Dict[str, Any]:
    mode = classify(user_text)
    if mode == "agent":
        return await _run_agent_route(user_text)

    calls: List = []
    models: List[str] = []
    if mode == "fast":
        calls = [
            _safe(call_perplexity, user_text, model=os.getenv("PERPLEXITY_MODEL", "sonar"), search=False),
            _safe(call_openai, user_text, model=os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini")),
        ]
        models = ["perplexity:sonar", "openai:gpt-4o-mini"]
    elif mode == "search":
        calls = [
            _safe(call_perplexity, user_text, model=os.getenv("PERPLEXITY_MODEL", "sonar"), search=True),
            _safe(call_xai, user_text, model=os.getenv("XAI_MODEL", "grok-2-latest")),
        ]
        models = ["perplexity:sonar(web)", "xai:grok"]
    elif mode == "code":
        calls = [
            _safe(call_anthropic, user_text, model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")),
            _safe(call_openai, user_text, model=os.getenv("OPENAI_MODEL_DEEP", "o3")),
        ]
        models = ["anthropic:claude-sonnet-4-5", "openai:o3"]
    else:
        calls = [
            _safe(call_openai, user_text, model=os.getenv("OPENAI_MODEL_DEEP", "o3")),
            _safe(call_xai, user_text, model=os.getenv("XAI_MODEL", "grok-2-latest")),
            _safe(call_gemini, user_text, model=os.getenv("GOOGLE_MODEL", "gemini-2.0-pro")),
        ]
        models = ["openai:o3", "xai:grok", "google:gemini-2.0-pro"]

    results = await asyncio.gather(*calls) if parallel else [await call for call in calls]
    blobs = [result.get("text", "").strip() for result in results]
    if not blobs:
        return {"route": mode, "models": models, "text": "", "citations": []}
    best_index = max(range(len(blobs)), key=lambda index: len(blobs[index]))
    best = results[best_index]
    merged_citations: List = []
    for result in results:
        for citation in result.get("citations", []) or []:
            if citation not in merged_citations:
                merged_citations.append(citation)
    return {
        "route": mode,
        "models": models,
        "text": best.get("text", "").strip(),
        "citations": merged_citations if citations else [],
    }
