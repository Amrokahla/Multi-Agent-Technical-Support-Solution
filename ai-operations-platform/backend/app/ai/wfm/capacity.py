"""Step 2 — capacity model.

Convert windowed workload into required agents per (day, hour) at the target
utilization, count available agents from shift coverage, and summarise the
intraday required-vs-available profile plus over/understaffing.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from app.ai.wfm.constants import UTIL_TARGET
from app.ai.wfm.workload import WorkContext


def _availability_by_hour(shifts: pd.DataFrame) -> pd.DataFrame:
    counts: Counter = Counter()
    for row in shifts.itertuples(index=False):
        start_hour = row.start_ts.hour
        day = row.date.strftime("%Y-%m-%d")
        for offset in range(row.len):
            counts[(day, (start_hour + offset) % 24)] += 1
    return pd.DataFrame(
        [{"day": d, "hour": h, "available": n} for (d, h), n in counts.items()]
    )


def run(ctx: WorkContext) -> dict:
    scale = ctx.scale_factor
    tickets = ctx.tickets

    required = (
        tickets.groupby(["day", "hour"])["handle_min"]
        .sum()
        .mul(scale / (60 * UTIL_TARGET))
        .rename("required")
        .reset_index()
    )
    available = _availability_by_hour(ctx.shifts)

    grid = pd.DataFrame(
        [(d, h) for d in sorted(tickets["day"].unique()) for h in range(24)],
        columns=["day", "hour"],
    )
    cap = (
        grid.merge(required, on=["day", "hour"], how="left")
        .merge(available, on=["day", "hour"], how="left")
        .fillna(0.0)
    )

    avg = cap.groupby("hour")[["required", "available"]].mean()
    understaffed = float((cap["required"] > cap["available"] + 0.5).mean() * 100)
    overstaffed = float((cap["available"] > cap["required"] * 1.5).mean() * 100)
    peak_hour = int(avg["required"].idxmax())

    return {
        "util_target": UTIL_TARGET,
        "scale_factor": scale,
        "window_days": ctx.ndays,
        "handle_min_median": round(ctx.handle_median, 1),
        "handle_min_p90": round(ctx.handle_p90, 1),
        "raw_occupancy_pct": round(ctx.raw_occupancy_pct, 1),
        "understaffed_pct": round(understaffed, 1),
        "overstaffed_pct": round(overstaffed, 1),
        "peak_hour": peak_hour,
        "peak_required": round(float(avg.loc[peak_hour, "required"]), 1),
        "peak_available": round(float(avg.loc[peak_hour, "available"]), 1),
        "intraday": [
            {
                "hour": int(h),
                "required": round(float(row["required"]), 2),
                "available": round(float(row["available"]), 2),
            }
            for h, row in avg.iterrows()
        ],
    }
