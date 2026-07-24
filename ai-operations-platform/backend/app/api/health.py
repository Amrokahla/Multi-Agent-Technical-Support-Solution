"""Liveness and dataset-availability endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.repositories import data_store
from app.schemas.common import DatasetSummary, HealthStatus

router = APIRouter()


@router.get("/health", response_model=HealthStatus)
def health(settings: Settings = Depends(get_settings)) -> HealthStatus:
    return HealthStatus(status="ok", app=settings.app_name, environment=settings.environment)


@router.get("/health/data", response_model=DatasetSummary)
def data_health() -> DatasetSummary:
    manifest = data_store.read_manifest()
    return DatasetSummary(**manifest)
