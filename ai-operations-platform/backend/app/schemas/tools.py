"""Typed parameter + result schemas for the copilot tools.

These double as the JSON schemas exposed to the LLM (via each tool's Params),
so field descriptions are written for the model to read.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --- Tool 1: forecast_demand -------------------------------------------------

class ForecastDemandParams(BaseModel):
    # Reject unknown args so a hallucinated parameter name fails loudly (the
    # orchestrator feeds the error back to the LLM to re-plan) instead of being
    # silently ignored.
    model_config = ConfigDict(extra="forbid")

    uplift_pct: float = Field(
        0.0, ge=-100, le=500,
        description="Expected change in ticket volume vs baseline, in percent. "
        "e.g. 30 means '30% more tickets'. 0 = baseline.",
    )
    horizon_days: int = Field(
        1, ge=1, le=90,
        description="How many days ahead the outlook is for (informational).",
    )


class SkillDemand(BaseModel):
    skill: str
    required_agent_hours: float
    share_pct: float


class ForecastModelInfo(BaseModel):
    name: str
    mae: float
    mape: float
    noise_floor_mae: float
    at_noise_floor: bool


class ForecastDemandResult(BaseModel):
    baseline_daily_tickets: float
    projected_daily_tickets: float
    uplift_pct: float
    horizon_days: int
    recommended_agents: int
    peak_hour: int
    peak_required_agents: float
    scale_factor: float
    by_skill: list[SkillDemand]
    model: ForecastModelInfo
    notes: list[str]


# --- Tool 3: allocate_resources ----------------------------------------------

class AllocateResourcesParams(BaseModel):
    # Phase 0 optimizes the current roster; a custom available-agent count and
    # richer constraints arrive in a later phase.
    model_config = ConfigDict(extra="forbid")


class SkillSupply(BaseModel):
    skill: str
    demand: float
    before: float
    after: float


class Move(BaseModel):
    agent_id: int
    from_skill: str
    to_skill: str
    type: str


class AllocateResourcesResult(BaseModel):
    unmet_before: float
    unmet_after: float
    reduction_pct: float
    moves: int
    reassign: int
    cross_train: int
    moves_into: dict[str, int]
    skills: list[SkillSupply]
    recommendations: list[Move]
    notes: list[str]


# --- Tool 2: predict_sla_risk ------------------------------------------------

class SlaRiskParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available_agents: int | None = Field(
        None, ge=0, le=1000,
        description="Agents available for the window; omit to use the current roster.",
    )
    uplift_pct: float = Field(
        0.0, ge=-100, le=500,
        description="Expected ticket-volume change vs baseline, in percent (e.g. 30).",
    )
    by_queue: bool = Field(True, description="Include the per-queue risk breakdown.")
    window: str = Field("next day", description="Time window the question is about (informational).")


class QueueRisk(BaseModel):
    queue: str
    baseline_risk: float
    utilization: float
    multiplier: float
    breach_risk: float
    required_agent_hours: float
    available_agent_hours: float
    risk_level: str


class SlaRiskResult(BaseModel):
    available_agents: int | None
    uplift_pct: float
    overall_breach_risk: float
    high_priority_compliance_pct: float
    overall_utilization: float
    by_queue: list[QueueRisk]
    high_risk_queues: list[str]
    high_risk_hours: list[int]
    model_metrics: dict
    drivers: list[str]
    notes: list[str]


# --- Tool 4: operational_insights --------------------------------------------

MetricName = Literal[
    "all", "volume", "breach_rate", "handle_time", "resolution_time", "csat", "reopen_rate", "backlog"
]


class InsightsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: MetricName = Field("all", description="Which KPI to analyse, or 'all'.")
    window_weeks: int = Field(
        8, ge=2, le=26, description="Weeks in the recent window, compared to the prior equal window.",
    )


class KpiTrend(BaseModel):
    name: str
    unit: str
    current: float
    previous: float
    change_pct: float
    change_abs: float
    direction: str
    favorable: bool | None


class Anomaly(BaseModel):
    metric: str
    week: str
    value: float
    expected: float
    deviation: float
    severity: str


class DriverSegment(BaseModel):
    segment: str
    contribution: float


class DriverGroup(BaseModel):
    metric: str
    dimension: str
    total_delta: float
    segments: list[DriverSegment]


class InsightsResult(BaseModel):
    period_from: str
    period_to: str
    window_weeks: int
    headline: str
    kpis: list[KpiTrend]
    anomalies: list[Anomaly]
    drivers: list[DriverGroup]
    notes: list[str]


# --- v2 scenario tools -------------------------------------------------------
# These wrap richer, nested engine outputs; the result is permissive (the engine
# owns the shape) while params stay strict for LLM-argument validation.

class FlexResult(BaseModel):
    model_config = ConfigDict(extra="allow")


class ClientLoadParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    top_n: int = Field(5, ge=1, le=20, description="How many top clients to return.")
    window_days: int = Field(28, ge=7, le=180, description="Recent window in days.")


class DetectSpikeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: Literal["volume", "high_priority"] = Field("volume", description="What to check for a spike.")
    lookback_days: int = Field(7, ge=1, le=30, description="Recent window compared to the baseline.")
    baseline_days: int = Field(28, ge=7, le=90, description="Baseline window before the recent window.")


class CapacityImpactParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agents_delta: int = Field(..., ge=-100, le=200, description="Change in agents, e.g. -3 for three unavailable.")


class WhatifSimulateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    horizon_days: int = Field(14, ge=1, le=90, description="Projection horizon in days.")
    uplift_pct: float = Field(0.0, ge=-100, le=500, description="Assumed volume change vs baseline.")


class TeamCompareParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalyzeTicketsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    window_days: int = Field(28, ge=1, le=180, description="Recent window to sample from.")
    queue: str | None = Field(None, description="Queue/team name filter, e.g. 'Tier 1'.")
    client: str | None = Field(None, description="Client filter — the client NAME (e.g. 'Tech C05 Ltd') or the numeric organization id.")
    priority: Literal["urgent", "high", "normal", "low"] | None = Field(None, description="Priority filter.")
    tag: str | None = Field(None, description="Tag substring filter.")
    focus: str = Field("", description="What to explain, e.g. 'why the volume spike'.")
    sample_size: int = Field(50, ge=5, le=50, description="Max tickets to read (capped).")
