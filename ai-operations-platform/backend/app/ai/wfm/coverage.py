"""Step 3 — coverage gap by skill and client.

Break required-vs-available down per skill (support area) x hour, producing the
gap matrix, the per-skill totals, and the clients most exposed to understaffing.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from app.ai.wfm.constants import UTIL_TARGET
from app.ai.wfm.workload import WorkContext


def _availability_by_group_hour(shifts: pd.DataFrame, agent_areas: dict[int, set[int]]) -> Counter:
    counts: Counter = Counter()
    for row in shifts.itertuples(index=False):
        start_hour = row.start_ts.hour
        for group_id in agent_areas.get(row.agent_id, set()):
            for offset in range(row.len):
                counts[(group_id, (start_hour + offset) % 24)] += 1
    return counts


def _client_risk(
    tickets_full: pd.DataFrame,
    deficit: pd.Series,
    contracts: pd.DataFrame,
) -> list[dict]:
    by_org = contracts.set_index("organization_id")
    org_group = (
        tickets_full.dropna(subset=["organization_id"])
        .groupby(["organization_id", "group_id"])
        .size()
        .rename("n")
        .reset_index()
    )
    org_group["exposure"] = org_group["group_id"].map(deficit) * org_group["n"]
    ranked = (
        org_group.groupby("organization_id")["exposure"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )
    rows = []
    for org_id, exposure in ranked.items():
        contract = by_org.loc[org_id] if org_id in by_org.index else None
        rows.append({
            "organization_id": int(org_id),
            "client": str(contract["name"]) if contract is not None else "",
            "dedicated": bool(contract["dedicated"]) if contract is not None else False,
            "exposure": round(float(exposure), 1),
        })
    return rows


def run(
    ctx: WorkContext,
    tickets_full: pd.DataFrame,
    agent_areas: dict[int, set[int]],
    group_names: dict[int, str],
    contracts: pd.DataFrame,
) -> dict:
    scale = ctx.scale_factor
    ndays = ctx.ndays
    hours = list(range(24))
    groups = sorted(group_names)

    availability = _availability_by_group_hour(ctx.shifts, agent_areas)
    required = ctx.tickets.groupby(["group_id", "hour"])["handle_min"].sum() * scale / (60 * UTIL_TARGET)

    demand_matrix = pd.DataFrame(
        {g: [required.get((g, h), 0) / ndays for h in hours] for g in groups}, index=hours
    )
    supply_matrix = pd.DataFrame(
        {g: [availability.get((g, h), 0) / ndays for h in hours] for g in groups}, index=hours
    )
    gap = supply_matrix - demand_matrix

    totals = pd.DataFrame({"required": demand_matrix.sum(), "available": supply_matrix.sum()})
    totals["gap"] = totals["available"] - totals["required"]
    totals = totals.sort_values("gap")

    deficit = (demand_matrix.sum() - supply_matrix.sum()).clip(lower=0)

    return {
        "skills": [
            {
                "group_id": int(g),
                "skill": group_names[g],
                "required": round(float(totals.loc[g, "required"]), 1),
                "available": round(float(totals.loc[g, "available"]), 1),
                "gap": round(float(totals.loc[g, "gap"]), 1),
            }
            for g in totals.index
        ],
        "gap_matrix": {
            "hours": hours,
            "skills": [group_names[g] for g in groups],
            "values": [[round(float(gap.loc[h, g]), 2) for g in groups] for h in hours],
        },
        "net_shortage_agent_hours": round(float(gap[gap < 0].sum().sum()), 1),
        "understaffed_cells": int((gap < -0.5).sum().sum()),
        "total_cells": int(gap.size),
        "client_risk": _client_risk(tickets_full, deficit, contracts),
    }
