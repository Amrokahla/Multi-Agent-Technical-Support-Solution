"""Operational KPI engine: weekly series, trend, robust anomalies, and drivers.

KPIs are computed on the created-week ticket cohort (backlog is a week-end
snapshot). Driver attribution decomposes a KPI change into structural-segment
contributions that reconcile to the pooled delta.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from app.ai.wfm.loaders import group_names, load_metrics, load_tickets
from app.config import get_settings

# KPI direction sense: +1 = up is good, -1 = up is bad, 0 = neutral.
SENSE = {
    "volume": 0, "breach_rate": -1, "handle_time": -1, "resolution_time": -1,
    "csat": +1, "reopen_rate": -1, "backlog": -1,
}
UNIT = {
    "volume": "tickets/wk", "breach_rate": "rate", "handle_time": "min", "resolution_time": "min",
    "csat": "rate", "reopen_rate": "rate", "backlog": "open",
}
METRICS = list(SENSE)
DIMENSIONS = ["queue", "priority", "channel", "ticket_type"]
# Per-ticket column backing each mean-type KPI (volume/backlog are handled specially).
_MEAN_COL = {
    "breach_rate": "breached", "handle_time": "handle_time", "resolution_time": "resolution_time",
    "csat": "csat_good", "reopen_rate": "reopened",
}


def _breach_ids() -> set:
    path = get_settings().data_dir / "ticket_metric_events.jsonl"
    ids = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            e = json.loads(line)
            if e.get("type") == "breach":
                ids.add(e["ticket_id"])
    return ids


@lru_cache(maxsize=1)
def ticket_frame() -> pd.DataFrame:
    tickets = load_tickets()
    metrics = load_metrics().set_index("ticket_id")
    breach = _breach_ids()
    gname = group_names()

    df = tickets[["id", "created_at", "priority", "group_id", "type", "via", "satisfaction_rating"]].copy()
    df = df.rename(columns={"type": "ticket_type"})
    df["queue"] = df["group_id"].map(gname)
    df["channel"] = df["via"].apply(lambda v: v.get("channel") if isinstance(v, dict) else None)
    # Monday-anchored week, kept tz-aware (avoids to_period dropping the timezone).
    df["week"] = (df["created_at"] - pd.to_timedelta(df["created_at"].dt.weekday, unit="D")).dt.normalize()
    df = df.join(metrics[["replies", "reopens", "full_resolution_min", "solved_at"]], on="id")

    df["handle_time"] = 6 + df["replies"].fillna(0) * 12
    df["reopened"] = (df["reopens"].fillna(0) > 0).astype(int)
    df["breached"] = df["id"].isin(breach).astype(int)
    df["resolution_time"] = df["full_resolution_min"]
    df["csat_good"] = df["satisfaction_rating"].apply(
        lambda s: 1.0 if isinstance(s, dict) and s.get("score") == "good"
        else (0.0 if isinstance(s, dict) and s.get("score") == "bad" else np.nan)
    )
    df["solved_at"] = pd.to_datetime(df["solved_at"], utc=True, errors="coerce")
    return df


@lru_cache(maxsize=1)
def weekly() -> pd.DataFrame:
    """Weekly KPI series, trimmed to full weeks."""
    df = ticket_frame()
    g = df.groupby("week")
    w = pd.DataFrame({
        "volume": g.size(),
        "breach_rate": g["breached"].mean(),
        "handle_time": g["handle_time"].mean(),
        "resolution_time": g["resolution_time"].mean(),
        "csat": g["csat_good"].mean(),
        "reopen_rate": g["reopened"].mean(),
    }).sort_index()
    w = w.iloc[1:-1]  # drop partial first/last weeks

    created, solved = df["created_at"], df["solved_at"]
    w["backlog"] = [
        int(((created <= end) & (solved.isna() | (solved > end))).sum())
        for end in (w.index + pd.Timedelta(days=7))  # week index is already tz-aware
    ]
    return w


def trend(metric: str, window: int = 8) -> dict:
    s = weekly()[metric].dropna()
    current = float(s.iloc[-window:].mean())
    previous = float(s.iloc[-2 * window:-window].mean())
    change_abs = current - previous
    change_pct = (change_abs / previous * 100) if previous else 0.0
    direction = "up" if change_pct > 2 else "down" if change_pct < -2 else "flat"
    sense = SENSE[metric]
    favorable = None if sense == 0 or direction == "flat" else (change_abs * sense > 0)
    return {
        "name": metric, "unit": UNIT[metric],
        "current": round(current, 3), "previous": round(previous, 3),
        "change_pct": round(change_pct, 1), "change_abs": round(change_abs, 3),
        "direction": direction, "favorable": favorable,
    }


def flag_anomalies(series: pd.Series, threshold: float = 3.5) -> pd.Series:
    """Robust modified z-score (median/MAD, Iglewicz-Hoaglin); returns flagged points' z."""
    s = series.dropna()
    median = s.median()
    mad = (s - median).abs().median()
    if mad == 0:
        return pd.Series(dtype=float)
    z = 0.6745 * (s - median) / mad
    return z[z.abs() > threshold]


def anomalies(metric: str, threshold: float = 3.5) -> list[dict]:
    s = weekly()[metric].dropna()
    median = float(s.median())
    flagged = flag_anomalies(s, threshold)
    return [
        {"metric": metric, "week": str(week.date()), "value": round(float(s[week]), 3),
         "expected": round(median, 3), "deviation": round(float(z), 1),
         "severity": "high" if abs(z) > 5 else "medium"}
        for week, z in flagged.items()
    ]


def drivers(metric: str, dimension: str, window: int = 8) -> dict:
    """Segment contributions to the pooled KPI change (they sum to total_delta)."""
    idx = weekly().index
    recent, prior = set(idx[-window:]), set(idx[-2 * window:-window])
    df = ticket_frame()
    cur, pre = df[df["week"].isin(recent)], df[df["week"].isin(prior)]

    if metric == "volume":
        c = cur.groupby(dimension).size()
        p = pre.groupby(dimension).size()
        keys = c.index.union(p.index)
        contrib = c.reindex(keys, fill_value=0) - p.reindex(keys, fill_value=0)
    else:
        col = _MEAN_COL[metric]
        cur, pre = cur.dropna(subset=[col]), pre.dropna(subset=[col])
        nc, npv = max(len(cur), 1), max(len(pre), 1)
        cg = cur.groupby(dimension).agg(n=("id", "size"), v=(col, "mean")).reindex(
            cur.groupby(dimension).size().index.union(pre.groupby(dimension).size().index), fill_value=0)
        pg = pre.groupby(dimension).agg(n=("id", "size"), v=(col, "mean")).reindex(cg.index, fill_value=0)
        contrib = (cg["n"] / nc) * cg["v"] - (pg["n"] / npv) * pg["v"]

    contrib = contrib.sort_values(key=lambda x: x.abs(), ascending=False)
    # Full precision so segments reconcile exactly to total_delta; display layer rounds.
    return {
        "dimension": dimension,
        "total_delta": float(contrib.sum()),
        "segments": [{"segment": str(k), "contribution": float(v)} for k, v in contrib.items()],
    }


def period() -> tuple[str, str]:
    idx = weekly().index
    return str(idx.min().date()), str((idx.max() + pd.Timedelta(days=6)).date())
