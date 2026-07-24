"""Shared response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthStatus(BaseModel):
    status: str
    app: str
    environment: str


class DatasetSummary(BaseModel):
    # Mirrors data/raw/zendesk/manifest.json; extra keys are tolerated.
    model_config = ConfigDict(extra="allow")

    ticket_count: int = 0
    comment_count: int = 0
    metric_events: int = 0
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_locale: dict[str, int] = {}
