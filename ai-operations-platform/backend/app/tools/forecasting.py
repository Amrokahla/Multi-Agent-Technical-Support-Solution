"""Tool 1 — forecast_demand.

Wraps the demand-forecast + capacity engines: reports the demand outlook (with an
optional volume uplift) and recommends how many agents that demand needs.
"""

from __future__ import annotations

import math

from app.schemas.tools import (
    ForecastDemandParams,
    ForecastDemandResult,
    ForecastModelInfo,
    SkillDemand,
)
from app.services import wfm
from app.tools.base import Tool

SHIFT_HOURS = 8


class ForecastDemandTool(Tool):
    name = "forecast_demand"
    description = (
        "Forecast ticket demand and recommend the number of agents needed to serve it. "
        "Set uplift_pct to model an expected volume change (e.g. 30 for '30% more tickets')."
    )
    Params = ForecastDemandParams
    Result = ForecastDemandResult

    def run(self, params: ForecastDemandParams) -> ForecastDemandResult:
        fc = wfm.get_forecast()
        cap = wfm.get_capacity()
        cov = wfm.get_coverage()
        summ = wfm.get_summary()

        factor = 1 + params.uplift_pct / 100
        baseline = round(fc["mean_per_day"], 1)
        total_required = sum(s["required"] for s in cov["skills"]) or 1.0
        recommended = math.ceil(total_required * factor / SHIFT_HOURS)

        by_skill = sorted(
            (
                SkillDemand(
                    skill=s["skill"],
                    required_agent_hours=round(s["required"] * factor, 1),
                    share_pct=round(100 * s["required"] / total_required, 1),
                )
                for s in cov["skills"]
            ),
            key=lambda x: x.required_agent_hours,
            reverse=True,
        )

        notes = []
        if params.uplift_pct:
            notes.append(f"Applied a {params.uplift_pct:+.0f}% volume change to baseline demand.")
        notes.append(
            "Demand is calibrated to real call-centre seasonality; agent figures use a "
            f"labeled sample-to-operation scale factor of {cap['scale_factor']}x."
        )

        return ForecastDemandResult(
            baseline_daily_tickets=baseline,
            projected_daily_tickets=round(baseline * factor, 1),
            uplift_pct=params.uplift_pct,
            horizon_days=params.horizon_days,
            recommended_agents=recommended,
            peak_hour=cap["peak_hour"],
            peak_required_agents=round(cap["peak_required"] * factor, 1),
            scale_factor=cap["scale_factor"],
            by_skill=by_skill,
            model=ForecastModelInfo(
                name=fc["chosen_model"],
                mae=summ["forecast"]["mae"],
                mape=summ["forecast"]["mape"],
                noise_floor_mae=fc["noise_floor_mae"],
                at_noise_floor=summ["forecast"]["at_noise_floor"],
            ),
            notes=notes,
        )
