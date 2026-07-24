"""Response schemas for the workforce-optimization endpoints."""

from __future__ import annotations

from pydantic import BaseModel


# --- Step 1: forecast ---------------------------------------------------------

class ModelScore(BaseModel):
    model: str
    mae: float
    rmse: float
    mape: float


class DemandPoint(BaseModel):
    date: str
    count: float


class BacktestPoint(BaseModel):
    date: str
    actual: float
    forecast: float


class ForecastResult(BaseModel):
    days: int
    start: str
    end: str
    mean_per_day: float
    noise_floor_mae: float
    split_index: int
    chosen_model: str
    models: list[ModelScore]
    weekday_profile: list[float]
    series: list[DemandPoint]
    backtest: list[BacktestPoint]


# --- Step 2: capacity ---------------------------------------------------------

class IntradayPoint(BaseModel):
    hour: int
    required: float
    available: float


class CapacityResult(BaseModel):
    util_target: float
    scale_factor: float
    window_days: int
    handle_min_median: float
    handle_min_p90: float
    raw_occupancy_pct: float
    understaffed_pct: float
    overstaffed_pct: float
    peak_hour: int
    peak_required: float
    peak_available: float
    intraday: list[IntradayPoint]


# --- Step 3: coverage ---------------------------------------------------------

class SkillGap(BaseModel):
    group_id: int
    skill: str
    required: float
    available: float
    gap: float


class GapMatrix(BaseModel):
    hours: list[int]
    skills: list[str]
    values: list[list[float]]


class ClientRisk(BaseModel):
    organization_id: int
    client: str
    dedicated: bool
    exposure: float


class CoverageResult(BaseModel):
    skills: list[SkillGap]
    gap_matrix: GapMatrix
    net_shortage_agent_hours: float
    understaffed_cells: int
    total_cells: int
    client_risk: list[ClientRisk]


# --- Step 4: optimizer --------------------------------------------------------

class SkillSupply(BaseModel):
    group_id: int
    skill: str
    demand: float
    before: float
    after: float


class Recommendation(BaseModel):
    agent_id: int
    from_skill: str
    to_skill: str
    type: str


class OptimizerResult(BaseModel):
    unmet_before: float
    unmet_after: float
    reduction_pct: float
    moves: int
    reassign: int
    cross_train: int
    moves_into: dict[str, int]
    skills: list[SkillSupply]
    recommendations: list[Recommendation]


# --- Cross-stage summary ------------------------------------------------------

class ForecastSummary(BaseModel):
    chosen_model: str
    mae: float
    mape: float
    noise_floor_mae: float
    at_noise_floor: bool


class CapacitySummary(BaseModel):
    understaffed_pct: float
    overstaffed_pct: float
    peak_hour: int


class CoverageSummary(BaseModel):
    net_shortage_agent_hours: float
    understaffed_cells: int
    total_cells: int
    worst_skill: str
    worst_gap: float


class OptimizerSummary(BaseModel):
    unmet_before: float
    unmet_after: float
    reduction_pct: float
    moves: int
    reassign: int
    cross_train: int


class WfmSummary(BaseModel):
    as_of: str
    window_days: int
    scale_factor: float
    forecast: ForecastSummary
    capacity: CapacitySummary
    coverage: CoverageSummary
    optimizer: OptimizerSummary
