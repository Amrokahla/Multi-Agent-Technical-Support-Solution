"""Tool 2 — predict_sla_risk.

Combines the calibrated breach-risk model (baseline propensity) with the coverage
staffing overlay to estimate SLA breach risk by queue and time window for a given
demand change and staffing level.
"""

from __future__ import annotations

from app.ai.sla import risk
from app.ai.sla.model import get_model
from app.schemas.tools import QueueRisk, SlaRiskParams, SlaRiskResult
from app.tools.base import Tool


class PredictSlaRiskTool(Tool):
    name = "predict_sla_risk"
    description = (
        "Estimate SLA breach risk by queue and time window for expected demand and a staffing "
        "level. Set available_agents to test 'with N agents' and uplift_pct for a volume change. "
        "Reports high-priority SLA compliance %."
    )
    Params = SlaRiskParams
    Result = SlaRiskResult

    def run(self, params: SlaRiskParams) -> SlaRiskResult:
        queues = risk.queue_risk(params.available_agents, params.uplift_pct)
        compliance = risk.high_priority_compliance(params.available_agents, params.uplift_pct)
        hours = risk.high_risk_hours(params.available_agents, params.uplift_pct)
        model = get_model()

        overall = round(sum(q["breach_risk"] for q in queues) / len(queues), 3)
        high_risk = [q["queue"] for q in queues if q["risk_level"] == "high"][:5]

        notes = [model.caveat]
        if params.available_agents:
            notes.append(
                f"Modeled {params.available_agents} agents vs the {risk.roster_size()}-agent roster "
                "(available capacity scaled proportionally)."
            )
        if params.uplift_pct:
            notes.append(f"Applied a {params.uplift_pct:+.0f}% volume change.")

        return SlaRiskResult(
            available_agents=params.available_agents,
            uplift_pct=params.uplift_pct,
            overall_breach_risk=overall,
            high_priority_compliance_pct=compliance["high_priority_compliance_pct"],
            overall_utilization=compliance["overall_utilization"],
            by_queue=[QueueRisk(**q) for q in queues] if params.by_queue else [],
            high_risk_queues=high_risk,
            high_risk_hours=hours,
            model_metrics=model.metrics,
            drivers=model.drivers,
            notes=notes,
        )
