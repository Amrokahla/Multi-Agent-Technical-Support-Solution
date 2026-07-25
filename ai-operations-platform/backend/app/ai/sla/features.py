"""Leakage-safe feature/label builder for the SLA-risk model.

One row per resolved SLA metric instance (breach or fulfill). Features are only
what is known at ticket arrival — never reply/resolution times, replies, reopens
or wait times, which are outcomes that determine the label.
"""

from __future__ import annotations

import json

import pandas as pd

from app.ai.wfm.loaders import group_names, load_tickets
from app.config import get_settings

CAT = ["priority", "ticket_type", "queue", "metric", "channel", "locale"]
NUM = ["sla_target_min", "hour", "weekday", "month", "is_weekend", "n_tags"]
LABEL = "label"

# Outcome columns that must never become features (used by the leakage assertion).
EXCLUDED = [
    "reply_time_in_minutes", "first_resolution_time_in_minutes", "full_resolution_time_in_minutes",
    "replies", "reopens", "agent_wait_time_in_minutes", "requester_wait_time_in_minutes",
    "on_hold_time_in_minutes", "solved_at",
]

_METRIC_RENAME = {"first_reply_time": "reply_time", "total_resolution_time": "resolution_time"}


def _store():
    return get_settings().data_dir


def _sla_targets() -> dict:
    policy = json.loads((_store() / "sla_policies.json").read_text())[0]["policy_metrics"]
    return {(p["priority"], _METRIC_RENAME[p["metric"]]): p["target"] for p in policy}


def _events() -> pd.DataFrame:
    with open(_store() / "ticket_metric_events.jsonl", encoding="utf-8") as fh:
        return pd.DataFrame(json.loads(line) for line in fh)


def build_training_frame() -> pd.DataFrame:
    tickets = load_tickets()
    events = _events()
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
    targets = _sla_targets()
    frame["sla_target_min"] = [targets.get((p, m)) for p, m in zip(frame["priority"], frame["metric"])]
    frame["queue"] = frame["group_id"].map(group_names())
    return frame


def categories_from(frame: pd.DataFrame) -> dict[str, list]:
    """Fixed category vocabulary per categorical column (stored with the model)."""
    return {c: sorted(frame[c].fillna("NA").astype(str).unique().tolist()) for c in CAT}


def prepare_X(frame: pd.DataFrame, categories: dict[str, list]) -> pd.DataFrame:
    """Select features and cast categoricals to a fixed vocabulary so encoding is
    identical at train and predict time (unseen values become missing)."""
    X = pd.DataFrame(index=frame.index)
    for c in CAT:
        values = frame[c].fillna("NA").astype(str) if c in frame else pd.Series("NA", index=frame.index)
        X[c] = pd.Categorical(values, categories=categories[c])
    for n in NUM:
        X[n] = pd.to_numeric(frame[n], errors="coerce") if n in frame else 0
    return X
