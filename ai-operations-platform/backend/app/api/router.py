"""Aggregate API router. Feature routers are mounted here as they are built."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import health, wfm

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(wfm.router, prefix="/wfm", tags=["workforce"])

# Roadmap — one router per AI feature:
#   api_router.include_router(risk.router, prefix="/risk", tags=["sla-risk"])
#   api_router.include_router(clusters.router, prefix="/clusters", tags=["root-cause"])
#   api_router.include_router(health_score.router, prefix="/clients", tags=["client-health"])
