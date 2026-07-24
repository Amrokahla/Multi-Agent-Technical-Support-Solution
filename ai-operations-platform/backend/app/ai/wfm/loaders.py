"""Data loaders for the WFM pipeline.

Read the frozen Zendesk store and the workforce layer into tidy pandas frames.
This is the backend counterpart of ``backend/notebooks/nbutils.py``; paths come
from settings instead of a hardcoded project root.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.ai.wfm.constants import CF_LOCALE, CF_QUEUE, VARIANT_ID_THRESHOLD
from app.config import get_settings


def _read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _custom_field(fields: list, field_id: int):
    return next((f["value"] for f in fields if f["id"] == field_id), None)


def _store() -> Path:
    return get_settings().data_dir


def _wfm() -> Path:
    return get_settings().wfm_dir


def analysis_now() -> pd.Timestamp:
    """The frozen dataset's "now" — the end of its restamped time span (UTC)."""
    manifest = _read_json(_store() / "manifest.json")
    end = manifest["time_span"]["end"]
    return pd.Timestamp(end).tz_convert("UTC")


def load_tickets() -> pd.DataFrame:
    df = pd.DataFrame(_read_jsonl(_store() / "tickets.jsonl"))
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df["locale"] = df["custom_fields"].apply(lambda x: _custom_field(x, CF_LOCALE))
    df["queue"] = df["custom_fields"].apply(lambda x: _custom_field(x, CF_QUEUE))
    df["is_variant"] = df["id"] > VARIANT_ID_THRESHOLD
    return df


def load_metrics() -> pd.DataFrame:
    rows = []
    for m in _read_jsonl(_store() / "ticket_metrics.jsonl"):
        rows.append({
            "ticket_id": m["ticket_id"],
            "reply_min": m["reply_time_in_minutes"]["calendar"],
            "full_resolution_min": m["full_resolution_time_in_minutes"]["calendar"],
            "agent_work_min": m["requester_wait_time_in_minutes"]["calendar"],
            "replies": m["replies"],
            "reopens": m["reopens"],
            "solved_at": m["solved_at"],
        })
    return pd.DataFrame(rows)


def load_shifts() -> pd.DataFrame:
    df = pd.DataFrame(_read_jsonl(_wfm() / "agent_shifts.jsonl"))
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df


def load_contracts() -> pd.DataFrame:
    return pd.DataFrame(_read_jsonl(_wfm() / "client_contracts.jsonl"))


def load_agent_skills() -> pd.DataFrame:
    rows = []
    for a in _read_jsonl(_store() / "agent_attribute_values.jsonl"):
        for value_id in a["attribute_value_ids"]:
            rows.append({"agent_id": a["agent_id"], "attribute_value_id": value_id})
    return pd.DataFrame(rows)


def group_names() -> dict[int, str]:
    return {g["id"]: g["name"] for g in _read_json(_store() / "groups.json")}


def agent_home_groups() -> dict[int, int]:
    """Each agent's home group id, from the Zendesk user objects."""
    users = _read_json(_store() / "users.json")
    return {u["id"]: u["group_id"] for u in users if u.get("role") == "agent"}


def area_value_to_group() -> dict[str, int]:
    """Map each routing 'area' attribute-value id to its group id (via name)."""
    name_to_group = {name: gid for gid, name in group_names().items()}
    routing = _read_json(_store() / "routing_attribute_values.json")
    return {
        v["id"]: name_to_group.get(v["name"])
        for v in routing
        if v["attribute_id"] == "att_area"
    }


def agent_areas() -> dict[int, set[int]]:
    """Per-agent set of group ids the agent is skilled to serve."""
    value_to_group = area_value_to_group()
    skills = load_agent_skills()
    skills = skills[skills["attribute_value_id"].isin(value_to_group)]
    grouped = skills.assign(gid=skills["attribute_value_id"].map(value_to_group))
    return grouped.groupby("agent_id")["gid"].apply(set).to_dict()


def daily_demand(tickets: pd.DataFrame) -> pd.Series:
    """Total tickets per calendar day, reindexed to the full daily range (0-filled)."""
    counts = tickets.set_index("created_at").resample("D").size()
    full = pd.date_range(
        counts.index.min().normalize(), counts.index.max().normalize(), freq="D"
    )
    return counts.reindex(full, fill_value=0).astype(float)
