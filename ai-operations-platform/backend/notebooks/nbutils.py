"""Shared helpers for the WFM notebooks: path bootstrap + data loaders.

Notebooks live in backend/notebooks/; this resolves the project root and returns
tidy pandas frames for the store, the WFM layer, and the calibration profiles.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORE = PROJECT_ROOT / "data" / "raw" / "zendesk"
WFM = PROJECT_ROOT / "data" / "raw" / "wfm"
PROFILES = PROJECT_ROOT / "data" / "processed" / "profiles"
PROCESSED = PROJECT_ROOT / "data" / "processed"

NOW = pd.Timestamp("2026-07-24 12:00:00", tz="UTC")


def _jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def _custom(fields: list, field_id: int):
    return next((f["value"] for f in fields if f["id"] == field_id), None)


def load_tickets() -> pd.DataFrame:
    df = pd.DataFrame(_jsonl(STORE / "tickets.jsonl"))
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["locale"] = df["custom_fields"].apply(lambda x: _custom(x, 900001))
    df["queue"] = df["custom_fields"].apply(lambda x: _custom(x, 900002))
    df["is_variant"] = df["id"] > 5000
    return df


def load_metrics() -> pd.DataFrame:
    rows = []
    for m in _jsonl(STORE / "ticket_metrics.jsonl"):
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


def load_agents() -> pd.DataFrame:
    return pd.DataFrame(_jsonl(WFM / "agent_profile.jsonl"))


def load_shifts() -> pd.DataFrame:
    df = pd.DataFrame(_jsonl(WFM / "agent_shifts.jsonl"))
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df


def load_contracts() -> pd.DataFrame:
    return pd.DataFrame(_jsonl(WFM / "client_contracts.jsonl"))


def load_agent_skills() -> pd.DataFrame:
    rows = []
    for a in _jsonl(STORE / "agent_attribute_values.jsonl"):
        for vid in a["attribute_value_ids"]:
            rows.append({"agent_id": a["agent_id"], "attribute_value_id": vid})
    return pd.DataFrame(rows)


def load_profiles() -> dict:
    return {p.stem: json.loads(p.read_text()) for p in PROFILES.glob("*.json")}


def groups() -> dict[int, str]:
    return {g["id"]: g["name"] for g in json.loads((STORE / "groups.json").read_text())}


def daily_demand(tickets: pd.DataFrame) -> pd.Series:
    """Total tickets per calendar day, reindexed to the full daily range (0-filled)."""
    counts = tickets.set_index("created_at").resample("D").size()
    full = pd.date_range(counts.index.min().normalize(), counts.index.max().normalize(), freq="D")
    return counts.reindex(full, fill_value=0).astype(float)


# --- SLA risk (notebook 05) --------------------------------------------------

def load_sla_events() -> pd.DataFrame:
    return pd.DataFrame(_jsonl(STORE / "ticket_metric_events.jsonl"))


def sla_targets() -> dict:
    """(priority, metric) -> target minutes, mapping policy metric names to event names."""
    rename = {"first_reply_time": "reply_time", "total_resolution_time": "resolution_time"}
    policy = json.loads((STORE / "sla_policies.json").read_text())[0]["policy_metrics"]
    return {(p["priority"], rename[p["metric"]]): p["target"] for p in policy}


def build_sla_frame() -> pd.DataFrame:
    """One row per resolved SLA metric instance (breach/fulfill), leakage-safe features.

    Features are only what is known at ticket arrival — no reply/resolution times,
    replies, reopens or wait times (those are outcomes that determine the label).
    """
    tickets = load_tickets()
    events = load_sla_events()
    events = events[events["type"].isin(["breach", "fulfill"])].copy()
    events["label"] = (events["type"] == "breach").astype(int)

    cols = ["id", "priority", "type", "group_id", "organization_id", "created_at", "locale", "tags", "via"]
    tk = tickets[cols].rename(columns={"type": "ticket_type"})
    frame = events[["ticket_id", "metric", "instance_id", "label"]].merge(
        tk, left_on="ticket_id", right_on="id", how="left"
    )

    frame["hour"] = frame["created_at"].dt.hour
    frame["weekday"] = frame["created_at"].dt.dayofweek
    frame["month"] = frame["created_at"].dt.month
    frame["is_weekend"] = (frame["weekday"] >= 5).astype(int)
    frame["channel"] = frame["via"].apply(lambda v: v.get("channel") if isinstance(v, dict) else None)
    frame["n_tags"] = frame["tags"].apply(lambda x: len(x) if isinstance(x, list) else 0)
    targets = sla_targets()
    frame["sla_target_min"] = [targets.get((p, m)) for p, m in zip(frame["priority"], frame["metric"])]
    frame["queue"] = frame["group_id"].map(groups())
    return frame
