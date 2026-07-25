"""Grounding guardrail — every number in the answer must trace to a tool result.

A safety net (not a hard gate): if the synthesizer emits a figure absent from the
tool outputs, re-synthesize once constrained to the allowed figures; if it still
slips, return the answer flagged ungrounded and log it.
"""

from __future__ import annotations

import re

_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?%?")
_TRIVIAL = {0.0, 1.0, 2.0}  # counts/dates that shouldn't trip the check


def extract_numbers(text: str) -> list[float]:
    out = []
    for tok in _NUM.findall(text or ""):
        try:
            out.append(float(tok.replace(",", "").rstrip("%")))
        except ValueError:
            pass
    return out


def _collect(obj, acc: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acc.add(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, acc)
    elif isinstance(obj, str):
        acc.update(extract_numbers(obj))


def allowed_numbers(trace, extra: list | None = None) -> set[float]:
    base: set[float] = set()
    for t in trace:
        if getattr(t, "ok", False):
            _collect(t.result, base)
        _collect(t.arguments, base)
    for item in extra or []:  # e.g. the standing-reports snapshot the agent answers from
        _collect(item, base)
    # Rounded variants, plus fraction<->percentage only where it makes sense (so a
    # value like 84.9 never spawns 8490 and mask a hallucinated big number).
    expanded = set(base)
    for a in base:
        expanded.update({round(a), round(a, 1)})
        if 0 <= a <= 1:  # rate -> percentage
            expanded.update({round(a * 100), round(a * 100, 1)})
        if 1 < a <= 100:  # percentage -> rate
            expanded.add(round(a / 100, 3))
    return expanded


def _is_allowed(n: float, allowed: set[float]) -> bool:
    if n in _TRIVIAL:
        return True
    return any(abs(n - a) <= max(0.5, 0.02 * abs(a)) for a in allowed)


def ungrounded(answer: str, trace, extra: list | None = None) -> list[float]:
    allowed = allowed_numbers(trace, extra)
    return [n for n in extract_numbers(answer) if not _is_allowed(n, allowed)]


def enforce_grounding(answer: str, trace, provider, synth_messages: list[dict],
                      extra: list | None = None) -> tuple[str, bool]:
    bad = ungrounded(answer, trace, extra)
    if not bad:
        return answer, True
    allowed = sorted(allowed_numbers(trace, extra))
    retry = synth_messages + [{
        "role": "user",
        "content": f"Your draft used figures not in the reports/tools: {bad}. Rewrite using only "
                   f"these figures and remove any others: {allowed}.",
    }]
    revised = provider.synthesize(retry)
    return revised, not ungrounded(revised, trace, extra)
