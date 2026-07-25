"""Run the WFM pipeline on an uploaded Zendesk-style ticket CSV.

A ticket export carries demand (created_at, queue/group) but not the roster
(shifts, skills). So we take demand from the file and model a transparent
even-baseline roster sized to it — one that is deliberately spread evenly across
skills, which is exactly the misalignment the optimizer then corrects. The four
stage functions are reused unchanged; only their input frames are synthesized.
"""

from __future__ import annotations

import io
import re

import numpy as np
import pandas as pd

from app.ai.wfm import capacity, coverage, forecast, optimizer
from app.ai.wfm.constants import HANDLE_BASE_MIN, HANDLE_PER_REPLY_MIN, UTIL_TARGET
from app.ai.wfm.loaders import daily_demand
from app.ai.wfm.summarize import build_summary
from app.ai.wfm.workload import WorkContext

MAX_SKILLS = 9
MIN_DAYS = 14
SHIFT_HOURS = 8
PRIORITY_HANDLE = {"urgent": 60, "high": 42, "normal": 30, "low": 18}

# Column-name patterns for a Zendesk (or generic) ticket export, in priority order.
COLUMN_PATTERNS = {
    "created_at": ["created at", "created", "opened", "date"],
    "skill": ["group", "queue", "team", "skill", "category", "department"],
    "replies": ["public replies", "replies", "reply", "comments"],
    "priority": ["priority"],
    "organization": ["organization", "account", "company", "org"],
    "ticket_id": ["ticket id", "id", "ticket"],
}


class UploadError(ValueError):
    """Raised when the CSV cannot be analysed; message is shown to the user."""


def _match_column(columns: list[str], patterns: list[str]) -> str | None:
    lowered = {c.strip().lower(): c for c in columns}
    for pattern in patterns:
        for low, original in lowered.items():
            if pattern == low:
                return original
    for pattern in patterns:
        for low, original in lowered.items():
            if pattern in low:
                return original
    return None


def _handle_minutes(df: pd.DataFrame, cols: dict[str, str | None]) -> pd.Series:
    if cols["replies"]:
        replies = pd.to_numeric(df[cols["replies"]], errors="coerce").fillna(0)
        return HANDLE_BASE_MIN + replies * HANDLE_PER_REPLY_MIN
    if cols["priority"]:
        mapped = df[cols["priority"]].astype(str).str.lower().map(PRIORITY_HANDLE)
        return mapped.fillna(PRIORITY_HANDLE["normal"])
    return pd.Series(PRIORITY_HANDLE["normal"], index=df.index, dtype=float)


def _parse(csv_bytes: bytes) -> tuple[pd.DataFrame, dict, list[str]]:
    try:
        raw = pd.read_csv(io.BytesIO(csv_bytes))
    except Exception as exc:  # noqa: BLE001 - surface any parse failure to the user
        raise UploadError(f"Could not read the CSV: {exc}") from None
    if raw.empty:
        raise UploadError("The file has no rows.")

    cols = {key: _match_column(list(raw.columns), pats) for key, pats in COLUMN_PATTERNS.items()}
    warnings: list[str] = []
    if not cols["created_at"]:
        raise UploadError("No 'created at' column found — a ticket creation date is required.")

    created = pd.to_datetime(raw[cols["created_at"]], errors="coerce", utc=True)
    df = raw.assign(created_at=created).dropna(subset=["created_at"])
    if df.empty:
        raise UploadError(f"Column '{cols['created_at']}' has no readable dates.")
    dropped = len(raw) - len(df)
    if dropped:
        warnings.append(f"Skipped {dropped:,} rows with an unreadable date.")

    if cols["skill"]:
        skill = df[cols["skill"]].fillna("Unassigned").astype(str).str.strip().replace("", "Unassigned")
    else:
        skill = pd.Series("All tickets", index=df.index)
        warnings.append("No group/queue column — treating all tickets as one skill.")

    # Keep the busiest skills; lump the long tail so the grid stays readable.
    top = skill.value_counts().index[:MAX_SKILLS]
    skill = skill.where(skill.isin(top), other="Other")
    if (skill == "Other").any():
        warnings.append(f"Grouped less-common queues beyond the top {MAX_SKILLS} into 'Other'.")

    names = list(pd.Index(skill.unique()).sort_values())
    skill_to_id = {name: i + 1 for i, name in enumerate(names)}
    group_names = {gid: name for name, gid in skill_to_id.items()}

    out = pd.DataFrame({
        "created_at": df["created_at"].values,
        "group_id": skill.map(skill_to_id).values,
        "handle_min": _handle_minutes(df, cols).values,
    })
    if cols["organization"]:
        out["organization_id"] = pd.factorize(df[cols["organization"]].astype(str))[0] + 1
    else:
        out["organization_id"] = np.nan
    out["day"] = out["created_at"].dt.strftime("%Y-%m-%d")
    out["hour"] = out["created_at"].dt.hour

    meta = {"columns": {k: v for k, v in cols.items() if v}, "group_names": group_names, "rows_parsed": int(len(raw))}
    return out, meta, warnings


def _synthesize_roster(tickets: pd.DataFrame, group_names: dict[int, str], now: pd.Timestamp) -> tuple[pd.DataFrame, dict, dict, float, int]:
    groups = sorted(group_names)
    k = len(groups)
    ndays = int(tickets["created_at"].dt.date.nunique())
    work_h_day = float(tickets["handle_min"].sum()) / 60 / ndays

    # Size the roster to demand, floored so every skill has cover and there is
    # room to reallocate; the scale factor then lifts demand to ~target occupancy
    # (≈1x for a large export, higher for a small sample — same idea as the main pipeline).
    n_agents = int(np.clip(round(work_h_day / (SHIFT_HOURS * UTIL_TARGET)), k * 2, 200))
    scale = round(UTIL_TARGET * (n_agents * SHIFT_HOURS) / work_h_day, 1)

    home_groups = {i + 1: groups[i % k] for i in range(n_agents)}  # even, round-robin
    agent_areas = {a: {g} for a, g in home_groups.items()}  # specialists -> optimizer cross-trains

    days = pd.date_range(tickets["created_at"].min().normalize(), tickets["created_at"].max().normalize(), freq="D")
    rows = []
    for agent_id in home_groups:
        start_hour = ((agent_id - 1) * 24 // n_agents) % 24  # stagger to spread 24h coverage
        for day in days:
            start = day + pd.Timedelta(hours=int(start_hour))
            rows.append({
                "agent_id": agent_id,
                "date": day,
                "start_ts": start,
                "end_ts": start + pd.Timedelta(hours=SHIFT_HOURS),
                "len": SHIFT_HOURS,
            })
    shifts = pd.DataFrame(rows)
    return shifts, agent_areas, home_groups, scale, n_agents


def analyze(csv_bytes: bytes, source: str) -> dict:
    tickets, parse_meta, warnings = _parse(csv_bytes)
    group_names = parse_meta["group_names"]
    ndays = int(tickets["created_at"].dt.date.nunique())
    if ndays < MIN_DAYS:
        raise UploadError(f"Only {ndays} days of tickets — need at least {MIN_DAYS} for a forecast.")

    now = tickets["created_at"].max()
    shifts, agent_areas, home_groups, scale, n_agents = _synthesize_roster(tickets, group_names, now)

    ctx = WorkContext(
        tickets=tickets,
        shifts=shifts,
        ndays=ndays,
        scale_factor=scale,
        handle_median=float(tickets["handle_min"].median()),
        handle_p90=float(tickets["handle_min"].quantile(0.9)),
        raw_occupancy_pct=100 * (float(tickets["handle_min"].sum()) / 60 / ndays) / (n_agents * SHIFT_HOURS),
    )

    contracts = pd.DataFrame(columns=["organization_id", "name", "dedicated"])
    fc = forecast.run(daily_demand(tickets))
    cap = capacity.run(ctx)
    cov = coverage.run(ctx, tickets, agent_areas, group_names, contracts)
    opt = optimizer.run(ctx, agent_areas, group_names, home_groups)
    summary = build_summary(now.isoformat(), ndays, scale, fc, cap, cov, opt)

    meta = {
        "source": source,
        "roster_modeled": True,
        "rows_parsed": parse_meta["rows_parsed"],
        "tickets_used": int(len(tickets)),
        "date_start": str(tickets["created_at"].min().date()),
        "date_end": str(tickets["created_at"].max().date()),
        "ndays": ndays,
        "skills": [group_names[g] for g in sorted(group_names)],
        "agents_modeled": n_agents,
        "scale_factor": scale,
        "columns": parse_meta["columns"],
        "warnings": warnings,
    }
    return {"summary": summary, "forecast": fc, "capacity": cap, "coverage": cov, "optimizer": opt, "meta": meta}
