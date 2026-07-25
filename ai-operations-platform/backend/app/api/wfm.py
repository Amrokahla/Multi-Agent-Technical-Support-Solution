"""Workforce-optimization endpoints — the four pipeline stages, a summary, and
the CSV-upload path that runs the same pipeline on an uploaded ticket export."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.ai.wfm import upload as upload_pipeline
from app.ai.wfm.upload import UploadError
from app.schemas.wfm import (
    AnalyzeResult,
    CapacityResult,
    CoverageResult,
    ForecastResult,
    OptimizerResult,
    WfmSummary,
)
from app.config import get_settings
from app.services import wfm

router = APIRouter()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _sample_path() -> Path:
    return get_settings().data_dir.parent.parent / "sample" / "zendesk_tickets_sample.csv"


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


@router.post("/analyze", response_model=AnalyzeResult)
async def analyze(file: UploadFile = File(...)) -> dict:
    """Run the full pipeline on an uploaded Zendesk-style ticket CSV."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 25 MB.")
    try:
        return upload_pipeline.analyze(content, source=file.filename or "upload.csv")
    except UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/sample", response_model=AnalyzeResult)
def sample() -> dict:
    """Run the pipeline on the bundled sample export (the 'Load sample' button)."""
    path = _sample_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample dataset not found.")
    return upload_pipeline.analyze(path.read_bytes(), source="zendesk_tickets_sample.csv")


@router.get("/sample.csv")
def sample_csv() -> FileResponse:
    """Download the raw sample export so users can see the expected CSV format."""
    path = _sample_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample dataset not found.")
    return FileResponse(path, media_type="text/csv", filename="zendesk_tickets_sample.csv")
