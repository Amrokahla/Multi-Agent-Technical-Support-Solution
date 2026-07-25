"""Staffing-scenario engines — capacity impact and the do-nothing projection.

capacity_impact answers "N agents become unavailable / are added": the SLA and
coverage delta. whatif_simulate answers "what happens if we do nothing": backlog,
SLA and utilization over a horizon.
"""

from __future__ import annotations

from app.ai.insights import metrics as insights
from app.ai.sla import risk
from app.services import wfm


def capacity_impact(agents_delta: int) -> dict:
    roster = risk.roster_size()
    after = max(roster + agents_delta, 1)
    factor = after / roster
    cov = wfm.get_coverage()

    def unmet(f: float) -> float:
        return sum(max(s["required"] - s["available"] * f, 0) for s in cov["skills"])

    base_unmet, new_unmet = unmet(1.0), unmet(factor)
    affected = []
    for s in cov["skills"]:
        extra = max(s["required"] - s["available"] * factor, 0) - max(s["required"] - s["available"], 0)
        if extra > 0.5:
            affected.append({"queue": s["skill"], "extra_shortfall_agent_hours": round(extra, 1)})
    affected.sort(key=lambda x: -x["extra_shortfall_agent_hours"])

    return {
        "roster": roster,
        "agents_delta": agents_delta,
        "agents_after": after,
        "compliance_before_pct": risk.high_priority_compliance()["high_priority_compliance_pct"],
        "compliance_after_pct": risk.high_priority_compliance(available_agents=after)["high_priority_compliance_pct"],
        "unmet_before_agent_hours": round(base_unmet, 1),
        "unmet_after_agent_hours": round(new_unmet, 1),
        "extra_shortfall_agent_hours": round(new_unmet - base_unmet, 1),
        "most_affected": affected[:3],
    }


def whatif_simulate(horizon_days: int = 14, uplift_pct: float = 0.0) -> dict:
    cov = wfm.get_coverage()
    cap = wfm.get_capacity()
    factor = 1 + uplift_pct / 100
    total_required = sum(s["required"] for s in cov["skills"]) * factor
    total_available = sum(s["available"] for s in cov["skills"])
    net_agent_hours_day = total_required - total_available  # > 0 → work accumulates

    tickets_per_agent_hour = 60 / cap["handle_min_median"]
    daily_backlog_growth = int(round(max(net_agent_hours_day, 0) * tickets_per_agent_hour))
    start_backlog = int(insights.weekly()["backlog"].iloc[-1])
    end_backlog = start_backlog + daily_backlog_growth * horizon_days
    comp = risk.high_priority_compliance(uplift_pct=uplift_pct)

    return {
        "horizon_days": horizon_days,
        "uplift_pct": uplift_pct,
        "start_backlog": start_backlog,
        "end_backlog": end_backlog,
        "daily_backlog_growth": daily_backlog_growth,
        "utilization": comp["overall_utilization"],
        "sla_compliance_pct": comp["high_priority_compliance_pct"],
        "backlog_grows": end_backlog > start_backlog,
    }
