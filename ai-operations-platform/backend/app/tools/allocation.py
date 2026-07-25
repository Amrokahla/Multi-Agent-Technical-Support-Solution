"""Tool 3 — allocate_resources.

Wraps the reassignment optimizer: returns a deterministic plan for redistributing
the current agents across skills to close coverage gaps.
"""

from __future__ import annotations

from app.schemas.tools import AllocateResourcesParams, AllocateResourcesResult, Move, SkillSupply
from app.services import wfm
from app.tools.base import Tool


class AllocateResourcesTool(Tool):
    name = "allocate_resources"
    description = (
        "Recommend how to redistribute the current agents across skills to close coverage "
        "gaps — a deterministic reassignment and cross-training plan."
    )
    Params = AllocateResourcesParams
    Result = AllocateResourcesResult

    def run(self, params: AllocateResourcesParams) -> AllocateResourcesResult:
        opt = wfm.get_optimization()
        skills = [
            SkillSupply(skill=s["skill"], demand=s["demand"], before=s["before"], after=s["after"])
            for s in opt["skills"]
        ]
        recommendations = [
            Move(agent_id=r["agent_id"], from_skill=r["from_skill"], to_skill=r["to_skill"], type=r["type"])
            for r in opt["recommendations"]
        ]
        return AllocateResourcesResult(
            unmet_before=opt["unmet_before"],
            unmet_after=opt["unmet_after"],
            reduction_pct=opt["reduction_pct"],
            moves=opt["moves"],
            reassign=opt["reassign"],
            cross_train=opt["cross_train"],
            moves_into=opt["moves_into"],
            skills=skills,
            recommendations=recommendations,
            notes=["Plan respects each agent's skills; the roster (current shifts) is held fixed."],
        )
