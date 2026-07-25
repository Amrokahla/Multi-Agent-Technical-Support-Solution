"""Spike-detection engine — is load rising, and is it broad or concentrated?

Compares a recent window to a baseline for a metric (volume or high-priority),
then localizes the change by queue and by client to answer the pivotal question:
system-wide, or one queue / one client.
"""

from __future__ import annotations

import pandas as pd

from app.ai.wfm.loaders import analysis_now, group_names, load_tickets

SPIKE_THRESHOLD_PCT = 25.0
_CONCENTRATED_SHARE = 50.0  # a segment owning >50% of the increase = concentrated


def _metric_mask(df: pd.DataFrame, metric: str) -> pd.Series:
    if metric == "high_priority":
        return df["priority"].isin(["urgent", "high"])
    return pd.Series(True, index=df.index)  # volume = all tickets


def _top_contributor(recent: pd.DataFrame, prior: pd.DataFrame, col: str, lookback: int, baseline: int, label):
    r = recent.groupby(col).size() / lookback
    b = prior.groupby(col).size() / baseline
    delta = r.subtract(b, fill_value=0).sort_values(ascending=False)
    if delta.empty:
        return None
    seg, contrib = delta.index[0], float(delta.iloc[0])
    return {"segment": label(seg), "per_day_increase": round(contrib, 2)}


def detect_spike(metric: str = "volume", lookback_days: int = 7, baseline_days: int = 28) -> dict:
    tickets = load_tickets()
    now = analysis_now()
    recent = tickets[tickets["created_at"] >= now - pd.Timedelta(days=lookback_days)]
    b_start = now - pd.Timedelta(days=lookback_days + baseline_days)
    b_end = now - pd.Timedelta(days=lookback_days)
    prior = tickets[(tickets["created_at"] >= b_start) & (tickets["created_at"] < b_end)]

    recent, prior = recent[_metric_mask(recent, metric)], prior[_metric_mask(prior, metric)]
    r_rate = len(recent) / lookback_days
    b_rate = len(prior) / baseline_days if len(prior) else 0.0
    change = round(100 * (r_rate - b_rate) / b_rate, 1) if b_rate else 0.0
    spike = change > SPIKE_THRESHOLD_PCT

    gname = group_names()
    top_queue = _top_contributor(recent, prior, "group_id", lookback_days, baseline_days, lambda g: gname.get(g, str(g)))
    top_client = _top_contributor(recent, prior, "organization_id", lookback_days, baseline_days, lambda o: f"org {o}")

    total_increase = max(r_rate - b_rate, 1e-9)
    scope = "broad"
    if spike and top_queue and top_queue["per_day_increase"] / total_increase * 100 >= _CONCENTRATED_SHARE:
        scope = f"queue-specific ({top_queue['segment']})"
    elif spike and top_client and top_client["per_day_increase"] / total_increase * 100 >= _CONCENTRATED_SHARE:
        scope = f"client-specific ({top_client['segment']})"
    elif not spike:
        scope = "stable"

    return {
        "metric": metric,
        "spike_detected": spike,
        "recent_per_day": round(r_rate, 1),
        "baseline_per_day": round(b_rate, 1),
        "change_pct": change,
        "scope": scope,
        "top_queue": top_queue,
        "top_client": top_client,
        "lookback_days": lookback_days,
        "baseline_days": baseline_days,
    }
