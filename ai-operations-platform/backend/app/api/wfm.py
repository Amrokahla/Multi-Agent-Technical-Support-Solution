"""Workforce-optimization endpoints — the four pipeline stages + a summary."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.wfm import (
    CapacityResult,
    CoverageResult,
    ForecastResult,
    OptimizerResult,
    WfmSummary,
)
from app.services import wfm

router = APIRouter()


@router.get("/summary", response_model=WfmSummary)
def summary() -> dict:
    """Headline numbers across all four stages."""
    return wfm.get_summary()


@router.get("/forecast", response_model=ForecastResult)
def forecast() -> dict:
    """Step 1 — daily demand, model bake-off, and H2 backtest."""
    return wfm.get_forecast()


@router.get("/capacity", response_model=CapacityResult)
def capacity() -> dict:
    """Step 2 — required vs available agents by hour, scale factor, staffing balance."""
    return wfm.get_capacity()


@router.get("/coverage", response_model=CoverageResult)
def coverage() -> dict:
    """Step 3 — per-skill gap, the skill x hour matrix, and client risk."""
    return wfm.get_coverage()


@router.get("/optimize", response_model=OptimizerResult)
def optimize() -> dict:
    """Step 4 — before/after supply vs demand and the reassignment recommendations."""
    return wfm.get_optimization()
