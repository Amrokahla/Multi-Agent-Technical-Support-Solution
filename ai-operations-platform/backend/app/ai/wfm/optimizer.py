"""Step 4 — reassignment optimizer.

Greedy skill reallocation: repeatedly move one agent from a surplus skill into the
largest-deficit skill they can serve (preferring an agent who already holds the
skill, else recommending cross-training), each agent moved at most once.
"""

from __future__ import annotations

from collections import Counter

from app.ai.wfm.constants import UTIL_TARGET
from app.ai.wfm.workload import WorkContext


def _skill_demand(ctx: WorkContext, groups: list[int]) -> dict[int, float]:
    per_group_hour = (
        ctx.tickets.groupby(["group_id", "hour"])["handle_min"].sum()
        * ctx.scale_factor
        / (60 * UTIL_TARGET)
        / ctx.ndays
    )
    per_group = per_group_hour.groupby(level=0).sum()
    return {g: float(per_group.get(g, 0.0)) for g in groups}


def run(
    ctx: WorkContext,
    agent_areas: dict[int, set[int]],
    group_names: dict[int, str],
    home_groups: dict[int, int],
) -> dict:
    groups = sorted(group_names)
    agent_hours = (ctx.shifts.groupby("agent_id")["len"].sum() / ctx.ndays).to_dict()
    agents = [a for a in agent_hours if a in home_groups]
    demand = _skill_demand(ctx, groups)

    assign = {a: home_groups[a] for a in agents}
    moved: set[int] = set()

    def supply() -> dict[int, float]:
        out = {g: 0.0 for g in groups}
        for a in agents:
            out[assign[a]] += agent_hours[a]
        return out

    def unmet() -> float:
        s = supply()
        return sum(max(demand[g] - s[g], 0.0) for g in groups)

    supply_before = supply()
    unmet_before = unmet()
    recommendations = []

    while True:
        s = supply()
        deficits = {g: demand[g] - s[g] for g in groups if demand[g] - s[g] > 1}
        if not deficits:
            break
        target = max(deficits, key=deficits.get)
        candidates = [
            a for a in agents
            if a not in moved and (s[assign[a]] - demand[assign[a]]) > agent_hours[a] * 0.5
        ]
        if not candidates:
            break
        candidates.sort(
            key=lambda a: (target not in agent_areas.get(a, set()), -(s[assign[a]] - demand[assign[a]]))
        )
        agent = candidates[0]
        needs_training = target not in agent_areas.get(agent, set())
        recommendations.append({
            "agent_id": int(agent),
            "from_skill": group_names[assign[agent]],
            "to_skill": group_names[target],
            "type": "cross-train" if needs_training else "reassign",
        })
        assign[agent] = target
        moved.add(agent)

    supply_after = supply()
    unmet_after = unmet()
    reduction = 100 * (unmet_before - unmet_after) / unmet_before if unmet_before else 0.0
    reassign = sum(1 for r in recommendations if r["type"] == "reassign")
    cross_train = sum(1 for r in recommendations if r["type"] == "cross-train")

    skills = sorted(groups, key=lambda g: demand[g], reverse=True)

    return {
        "unmet_before": round(unmet_before, 1),
        "unmet_after": round(unmet_after, 1),
        "reduction_pct": round(reduction, 1),
        "moves": len(recommendations),
        "reassign": reassign,
        "cross_train": cross_train,
        "moves_into": dict(Counter(r["to_skill"] for r in recommendations)),
        "skills": [
            {
                "group_id": int(g),
                "skill": group_names[g],
                "demand": round(demand[g], 1),
                "before": round(supply_before[g], 1),
                "after": round(supply_after[g], 1),
            }
            for g in skills
        ],
        "recommendations": recommendations,
    }
