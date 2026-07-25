"""LLM ticket analyzer — reads the actual tickets behind a segment to explain WHY.

Deterministically samples tickets by filter (window / queue / client / priority /
tag), then asks GPT-5-mini to read their subjects + descriptions and return
structured themes, a likely cause, temporary-vs-structural, priority mismatches,
and a complexity signal. Numbers still come from the deterministic tools; this
adds qualitative cause. Ticket text stays server-side.
"""

from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from app.ai.wfm.loaders import analysis_now, group_names, load_contracts, load_tickets
from app.config import get_settings

_SYSTEM = (
    "You analyze B2B support tickets to explain operational causes for a delivery manager. "
    "Read the sampled tickets and return STRICT JSON with keys: "
    "themes (list of {theme, share_pct, example_ids}), likely_cause (string), "
    "temporary_or_structural ('temporary'|'structural'|'unclear'), "
    "priority_mismatches (list of {ticket_id, stated_priority, suggested_priority, reason}), "
    "complexity_signal ('low'|'medium'|'high'), summary (string). "
    "Base everything only on the tickets provided; cite ticket ids in example_ids."
)
_DESC_CHARS = 220


def _call_llm(system: str, user: str) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set — the ticket analyzer needs it.")
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.synth_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_completion_tokens=4000,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or "{}"


@lru_cache(maxsize=1)
def _client_index() -> tuple[tuple[int, str], ...]:
    """(organization_id, name) pairs from organizations + contracts, for name lookup."""
    pairs: list[tuple[int, str]] = []
    orgs = json.loads((get_settings().data_dir / "organizations.json").read_text())
    pairs += [(o["id"], o["name"]) for o in orgs]
    try:
        contracts = load_contracts()
        pairs += [(int(r["organization_id"]), str(r["name"])) for _, r in contracts.iterrows()]
    except Exception:  # noqa: BLE001 - contracts optional
        pass
    return tuple(pairs)


def _resolve_client_ids(client: str) -> set[int]:
    """Resolve a client filter (a name substring OR a numeric org id) to org ids."""
    c = str(client).strip()
    if c.isdigit():
        return {int(c)}
    lc = c.lower()
    return {oid for oid, name in _client_index() if lc in str(name).lower()}


def _sample(window_days: int, queue: str | None, client: str | None, priority: str | None,
            tag: str | None, sample_size: int) -> pd.DataFrame:
    df = load_tickets()
    df = df[df["created_at"] >= analysis_now() - pd.Timedelta(days=window_days)]
    gname = group_names()
    df = df.assign(queue=df["group_id"].map(gname))
    if queue:
        df = df[df["queue"].str.contains(queue, case=False, na=False)]
    if priority:
        df = df[df["priority"] == priority.lower()]
    if tag:
        df = df[df["tags"].apply(lambda ts: isinstance(ts, list) and any(tag.lower() in str(t).lower() for t in ts))]
    if client:
        ids = _resolve_client_ids(client)  # by name or numeric id
        df = df[df["organization_id"].isin(ids)] if ids else df.iloc[0:0]
    return df.sort_values("created_at", ascending=False).head(sample_size)


def analyze_tickets(window_days: int = 28, queue: str | None = None, client: str | None = None,
                    priority: str | None = None, tag: str | None = None, focus: str = "",
                    sample_size: int = 50) -> dict:
    sample = _sample(window_days, queue, client, priority, tag, sample_size)
    if sample.empty:
        return {"sampled": 0, "summary": "No tickets matched the filter.", "themes": []}

    lines = [
        f"[{r.id}] priority={r.priority} queue={r.queue} :: {str(r.subject)[:120]} — {str(r.description or '')[:_DESC_CHARS]}"
        for r in sample.itertuples()
    ]
    user = (f"Focus: {focus or 'explain what is driving this segment'}\n"
            f"{len(lines)} tickets:\n" + "\n".join(lines))

    try:
        parsed = json.loads(_call_llm(_SYSTEM, user))
    except json.JSONDecodeError:
        parsed = {"summary": "Analyzer returned unparseable output.", "themes": []}

    parsed.setdefault("themes", [])
    parsed.setdefault("priority_mismatches", [])
    parsed["sampled"] = int(len(sample))
    parsed["filter"] = {k: v for k, v in
                        {"window_days": window_days, "queue": queue, "client": client,
                         "priority": priority, "tag": tag}.items() if v is not None}
    return parsed
