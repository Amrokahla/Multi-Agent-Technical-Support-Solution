"""Team-comparison engine — a queue vs its peers, to separate capacity from skill.

Compares each queue on median resolution time, throughput and utilization, then
diagnoses whether a slow team is understaffed (capacity) or handling harder work
(skill/complexity).
"""

from __future__ import annotations

from app.ai.wfm.loaders import group_names, load_metrics, load_tickets
from app.services import wfm


def team_compare() -> dict:
    utilization = {s["skill"]: s["required"] / max(s["available"], 1e-6) for s in wfm.get_coverage()["skills"]}

    merged = load_tickets().merge(load_metrics(), left_on="id", right_on="ticket_id")
    merged["queue"] = merged["group_id"].map(group_names())
    grouped = merged.groupby("queue").agg(
        resolution_min=("full_resolution_min", "median"),
        throughput=("id", "size"),
    )
    median_resolution = float(grouped["resolution_min"].median())

    teams = []
    for queue, row in grouped.iterrows():
        util = utilization.get(queue, 0.0)
        slow = row["resolution_min"] > median_resolution * 1.15
        diagnosis = (
            "capacity (understaffed)" if slow and util > 1
            else "skill / complexity" if slow
            else "healthy"
        )
        teams.append({
            "queue": queue,
            "resolution_min": round(float(row["resolution_min"]), 0),
            "throughput": int(row["throughput"]),
            "utilization": round(util, 2),
            "vs_median_pct": round(100 * (row["resolution_min"] - median_resolution) / median_resolution, 1),
            "diagnosis": diagnosis,
        })
    teams.sort(key=lambda t: -t["resolution_min"])

    return {"teams": teams, "slowest": teams[0]["queue"] if teams else None, "median_resolution_min": round(median_resolution, 0)}
