"""v2 scenario tools — client load, spike detection, capacity impact, do-nothing
simulation, and team comparison. Thin wrappers over the app/ai engines.
"""

from __future__ import annotations

from app.ai import clients, impact, spike, teams
from app.schemas.tools import (
    CapacityImpactParams,
    ClientLoadParams,
    DetectSpikeParams,
    FlexResult,
    TeamCompareParams,
    WhatifSimulateParams,
)
from app.tools.base import Tool


class ClientLoadTool(Tool):
    name = "client_load"
    description = (
        "Rank clients by recent ticket load and flag whether the load is concentrated in a few "
        "clients (client-specific) or spread broadly. Shows each client's share, trend, and whether "
        "they are on a dedicated contract."
    )
    Params = ClientLoadParams
    Result = FlexResult

    def run(self, params: ClientLoadParams) -> FlexResult:
        return FlexResult(**clients.client_load(params.top_n, params.window_days))


class DetectSpikeTool(Tool):
    name = "detect_spike"
    description = (
        "Detect whether ticket volume or high-priority load is rising versus baseline, and localize "
        "it: broad (system-wide) vs one queue vs one client."
    )
    Params = DetectSpikeParams
    Result = FlexResult

    def run(self, params: DetectSpikeParams) -> FlexResult:
        return FlexResult(**spike.detect_spike(params.metric, params.lookback_days, params.baseline_days))


class CapacityImpactTool(Tool):
    name = "capacity_impact"
    description = (
        "Estimate the impact of losing or adding agents (agents_delta, e.g. -3 for three unavailable) "
        "on high-priority SLA compliance and per-queue coverage, plus the shortfall to offset."
    )
    Params = CapacityImpactParams
    Result = FlexResult

    def run(self, params: CapacityImpactParams) -> FlexResult:
        return FlexResult(**impact.capacity_impact(params.agents_delta))


class WhatifSimulateTool(Tool):
    name = "whatif_simulate"
    description = (
        "Project the do-nothing outcome over a horizon: backlog growth, high-priority SLA compliance "
        "and utilization, optionally under a volume uplift."
    )
    Params = WhatifSimulateParams
    Result = FlexResult

    def run(self, params: WhatifSimulateParams) -> FlexResult:
        return FlexResult(**impact.whatif_simulate(params.horizon_days, params.uplift_pct))


class TeamCompareTool(Tool):
    name = "team_compare"
    description = (
        "Compare each team/queue against peers on resolution time, throughput and utilization to "
        "diagnose whether a slow team is a capacity (understaffing) or a skill/complexity issue."
    )
    Params = TeamCompareParams
    Result = FlexResult

    def run(self, params: TeamCompareParams) -> FlexResult:
        return FlexResult(**teams.team_compare())
