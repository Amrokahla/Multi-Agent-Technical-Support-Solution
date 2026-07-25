"""Reports endpoints — Sync runs the pipeline once; GET returns the current bundle."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.reports import ReportsBundle
from app.services import reports

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/sync", response_model=ReportsBundle)
def sync() -> dict:
    """Run the analytics pipeline (fresh) and return the full report bundle."""
    return {**reports.sync(), "synced_at": _now()}


@router.get("", response_model=ReportsBundle)
def current() -> dict:
    """Return the currently cached report bundle (computes once if absent)."""
    return {**reports.build_bundle(), "synced_at": _now()}
