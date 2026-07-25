"""Response schema for the reports bundle (Sync)."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.tools import InsightsResult
from app.schemas.wfm import (
    CapacityResult,
    CoverageResult,
    ForecastResult,
    OptimizerResult,
    WfmSummary,
)


class ReportsBundle(BaseModel):
    synced_at: str
    summary: WfmSummary
    forecast: ForecastResult
    capacity: CapacityResult
    coverage: CoverageResult
    optimizer: OptimizerResult
    insights: InsightsResult
    clients: dict
