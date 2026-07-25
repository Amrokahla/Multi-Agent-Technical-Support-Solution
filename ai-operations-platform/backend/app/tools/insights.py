"""Tool 4 — operational_insights.

Analyse operational KPI trends, flag anomalies, and explain which structural
segments (queue / priority / channel / type) drove a change. Ops metrics only —
no ticket-content root-cause.
"""

from __future__ import annotations

from app.ai.insights import metrics
from app.schemas.tools import (
    Anomaly,
    DriverGroup,
    DriverSegment,
    InsightsParams,
    InsightsResult,
    KpiTrend,
)
from app.tools.base import Tool

_DRIVER_DIMENSIONS = ("queue", "priority")
_TOP_SEGMENTS = 4


class OperationalInsightsTool(Tool):
    name = "operational_insights"
    description = (
        "Analyse operational KPI trends (volume, SLA breach rate, handle time, resolution time, "
        "CSAT, reopen rate, backlog), flag anomalous weeks, and explain which structural segments "
        "(queue/priority/channel/type) drove a change. Set metric to focus, or 'all'."
    )
    Params = InsightsParams
    Result = InsightsResult

    def run(self, params: InsightsParams) -> InsightsResult:
        names = metrics.METRICS if params.metric == "all" else [params.metric]
        kpis = [KpiTrend(**metrics.trend(n, params.window_weeks)) for n in names]
        anomalies = [Anomaly(**a) for n in names for a in metrics.anomalies(n)]

        focus = self._focus(kpis)
        # Backlog is a snapshot with no cohort decomposition — explain the biggest
        # driver-capable mover instead so the drivers section is never empty.
        driver_metric = focus.name if focus.name != "backlog" else self._focus(
            [k for k in kpis if k.name != "backlog"]
        ).name
        driver_groups = self._drivers(driver_metric, params.window_weeks)
        period_from, period_to = metrics.period()

        return InsightsResult(
            period_from=period_from,
            period_to=period_to,
            window_weeks=params.window_weeks,
            headline=self._headline(focus, driver_groups if driver_metric == focus.name else []),
            kpis=kpis,
            anomalies=anomalies,
            drivers=driver_groups,
            notes=["KPIs reflect calibrated synthetic seasonality, not real-world drift."],
        )

    def _focus(self, kpis: list[KpiTrend]) -> KpiTrend:
        movers = [k for k in kpis if k.favorable is False] or kpis
        return max(movers, key=lambda k: abs(k.change_pct))

    def _drivers(self, metric: str, window: int) -> list[DriverGroup]:
        if metric == "backlog":  # snapshot KPI has no cohort decomposition
            return []
        groups = []
        for dimension in _DRIVER_DIMENSIONS:
            g = metrics.drivers(metric, dimension, window)
            groups.append(DriverGroup(
                metric=metric,
                dimension=g["dimension"],
                total_delta=round(g["total_delta"], 4),
                segments=[
                    DriverSegment(segment=s["segment"], contribution=round(s["contribution"], 4))
                    for s in g["segments"][:_TOP_SEGMENTS]
                ],
            ))
        return groups

    def _headline(self, focus: KpiTrend, drivers: list[DriverGroup]) -> str:
        text = f"{focus.name.replace('_', ' ')} {focus.direction} {abs(focus.change_pct):.0f}% over the last window"
        if drivers and drivers[0].segments:
            text += f", led by {drivers[0].dimension} '{drivers[0].segments[0].segment}'"
        return text
