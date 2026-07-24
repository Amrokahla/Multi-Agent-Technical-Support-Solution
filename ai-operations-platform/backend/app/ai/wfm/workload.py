"""Shared workload preparation for the capacity, coverage and optimizer stages.

Turns raw tickets + metrics + shifts into the windowed working set every staffing
stage needs: agent-occupied handle time, the recent shift window, the number of
days in it, and the sample->operation volume scale factor.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.ai.wfm.constants import (
    HANDLE_BASE_MIN,
    HANDLE_PER_REPLY_MIN,
    UTIL_TARGET,
    WINDOW_DAYS,
)


@dataclass
class WorkContext:
    tickets: pd.DataFrame  # windowed tickets with handle_min, hour
    shifts: pd.DataFrame  # windowed shifts with start hour and integer length
    ndays: int  # distinct ticket-days in the window
    scale_factor: float  # sample -> full-operation volume multiplier
    handle_median: float  # agent-minutes per ticket (median)
    handle_p90: float  # agent-minutes per ticket (p90)
    raw_occupancy_pct: float  # unscaled workload vs available capacity


def with_handle_time(tickets: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    """Join metrics onto tickets and derive agent-occupied handle minutes."""
    joined = tickets.merge(metrics, left_on="id", right_on="ticket_id")
    joined["handle_min"] = HANDLE_BASE_MIN + joined["replies"].fillna(0) * HANDLE_PER_REPLY_MIN
    return joined


def _prepare_shifts(shifts: pd.DataFrame, window_start: pd.Timestamp) -> pd.DataFrame:
    recent = shifts[shifts["date"] >= window_start].copy()
    recent["start_ts"] = pd.to_datetime(recent["start"], utc=True)
    recent["end_ts"] = pd.to_datetime(recent["end"], utc=True)
    recent["len"] = (
        (recent["end_ts"] - recent["start_ts"]).dt.total_seconds() / 3600
    ).round().astype(int)
    return recent


def build_context(
    tickets: pd.DataFrame,
    metrics: pd.DataFrame,
    shifts: pd.DataFrame,
    now: pd.Timestamp,
) -> WorkContext:
    handled = with_handle_time(tickets, metrics)
    window_start = now - pd.Timedelta(days=WINDOW_DAYS)

    recent = handled[handled["created_at"] >= window_start].copy()
    recent["hour"] = recent["created_at"].dt.hour
    recent["day"] = recent["created_at"].dt.strftime("%Y-%m-%d")
    ndays = int(recent["created_at"].dt.date.nunique())

    shifts_win = _prepare_shifts(shifts, window_start)

    work_hours_per_day = recent.groupby("day")["handle_min"].sum() / 60
    avail_hours_per_day = (
        shifts_win.assign(day=shifts_win["date"].dt.strftime("%Y-%m-%d"))
        .groupby("day")["len"]
        .sum()
        .mean()
    )
    mean_work = float(work_hours_per_day.mean())
    scale = round(UTIL_TARGET * avail_hours_per_day / mean_work, 1)
    raw_occ = 100 * mean_work / float(avail_hours_per_day)

    return WorkContext(
        tickets=recent,
        shifts=shifts_win,
        ndays=ndays,
        scale_factor=float(scale),
        handle_median=float(handled["handle_min"].median()),
        handle_p90=float(handled["handle_min"].quantile(0.9)),
        raw_occupancy_pct=float(raw_occ),
    )
