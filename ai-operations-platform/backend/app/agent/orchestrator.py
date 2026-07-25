"""Copilot orchestrator — conversational, multi-round tool loop.

GPT-5 plans across up to MAX_ROUNDS rounds (chaining tools: detect -> localize ->
diagnose via analyze_tickets -> assess -> recommend), feeding each tool result
back so it can decide the next step. GPT-5-mini then writes a structured markdown
answer from the accumulated results. Session memory arrives as `history`. Every
number still comes from a tool; a grounding guardrail enforces it.
"""

from __future__ import annotations

import json

from app.agent.guardrails import enforce_grounding
from app.agent.prompts import PLANNER_SYSTEM, SYNTH_SYSTEM, reports_prefix, synth_prompt
from app.agent.provider import ToolCall, get_provider
from app.agent.registry import get_registry
from app.config import get_settings
from app.schemas.agent import AgentResponse, AnalyticsLink, ToolTraceEntry
from app.services import reports

MAX_ROUNDS = 4
TOOL_RESULT_CHARS = 4000

_ANALYTICS = {
    "forecast_demand": ("Forecast", "/#forecast"),
    "predict_sla_risk": ("Coverage & SLA", "/#coverage"),
    "allocate_resources": ("Reallocation plan", "/#realignment"),
    "operational_insights": ("Trends", "/#insights"),
    "capacity_impact": ("Coverage & SLA", "/#coverage"),
    "whatif_simulate": ("Trends", "/#insights"),
    "team_compare": ("Coverage & SLA", "/#coverage"),
}
_CAVEAT_HINTS = ("caveat", "synthetic", "scale", "modeled", "illustrative", "calibrated", "generator")


def _assistant_toolcalls(calls: list[ToolCall], content: str | None) -> dict:
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
            for c in calls
        ],
    }


def _analytics_links(tools: list[str]) -> list[AnalyticsLink]:
    seen, links = set(), []
    for name in tools:
        entry = _ANALYTICS.get(name)
        if entry and entry[1] not in seen:
            seen.add(entry[1])
            links.append(AnalyticsLink(label=entry[0], href=entry[1]))
    return links


def _caveats(trace: list[ToolTraceEntry]) -> list[str]:
    out = []
    for t in trace:
        if not (t.ok and t.result):
            continue
        for note in t.result.get("notes", []) or []:
            if note not in out and any(h in note.lower() for h in _CAVEAT_HINTS):
                out.append(note)
        cav = t.result.get("caveat")
        if isinstance(cav, str) and cav not in out:
            out.append(cav)
    return out[:4]


def _models() -> dict:
    s = get_settings()
    return {"planner": s.planner_model, "synthesizer": s.synth_model}


def _fallback_answer(trace: list[ToolTraceEntry]) -> str:
    tools = ", ".join(t.tool for t in trace if t.ok) or "no tools"
    return f"Analysis ran ({tools}), but the summary could not be generated. Open the linked analytics for details."


def answer(question: str, history: list[dict] | None = None, provider=None) -> AgentResponse:
    provider = provider or get_provider()
    registry = get_registry()
    tools = registry.schemas()
    history = history or []

    # Standing reports as a stable prefix: the agent answers from these and only
    # calls tools for deeper investigation. Stable across turns -> prompt-cached.
    report_snapshot = reports.reports_context()
    reports_msg = {"role": "system", "content": reports_prefix(report_snapshot)}

    messages = [{"role": "system", "content": PLANNER_SYSTEM}, reports_msg, *history,
                {"role": "user", "content": question}]
    trace: list[ToolTraceEntry] = []

    for _ in range(MAX_ROUNDS):
        calls, content = provider.plan(messages, tools)
        if not calls:
            break
        messages.append(_assistant_toolcalls(calls, content))
        for call in calls:
            result = registry.dispatch(call.name, call.arguments)
            ok = isinstance(result, dict) and "error" not in result
            trace.append(ToolTraceEntry(
                tool=call.name, arguments=call.arguments, ok=ok,
                result=result if ok else None, error=None if ok else result.get("error"),
            ))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)[:TOOL_RESULT_CHARS]})

    ok_results = [{"tool": t.tool, "arguments": t.arguments, "result": t.result} for t in trace if t.ok]
    synth_messages = [{"role": "system", "content": SYNTH_SYSTEM}, reports_msg, *history,
                      {"role": "user", "content": synth_prompt(question, ok_results)}]
    draft = provider.synthesize(synth_messages)
    if not draft.strip():
        draft = provider.synthesize(synth_messages)
    if draft.strip():
        final, grounded = enforce_grounding(draft, trace, provider, synth_messages, extra=[report_snapshot])
    else:
        final, grounded = _fallback_answer(trace), True

    return AgentResponse(
        question=question, answer=final, tool_trace=trace,
        analytics_links=_analytics_links([t.tool for t in trace if t.ok]),
        caveats=_caveats(trace), models_used=_models(), grounding_ok=grounded,
    )
