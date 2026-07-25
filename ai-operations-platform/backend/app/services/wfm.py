"""Workforce-optimization service.

Runs the four-stage pipeline over the frozen dataset and caches the result. The
data is immutable, so the analysis is computed once (lazily) and reused; call
``reset_cache`` in tests that swap the underlying data.
"""

from __future__ import annotations

from functools import lru_cache

from app.ai.wfm import capacity, coverage, forecast, loaders, optimizer
from app.ai.wfm.summarize import build_summary
from app.ai.wfm.workload import build_context


@lru_cache(maxsize=1)
def _analysis() -> dict:
    now = loaders.analysis_now()
    tickets = loaders.load_tickets()
    metrics = loaders.load_metrics()
    shifts = loaders.load_shifts()
    contracts = loaders.load_contracts()
    group_names = loaders.group_names()
    agent_areas = loaders.agent_areas()
    home_groups = loaders.agent_home_groups()

    demand_series = loaders.daily_demand(tickets)
    ctx = build_context(tickets, metrics, shifts, now)

    fc = forecast.run(demand_series)
    cap = capacity.run(ctx)
    cov = coverage.run(ctx, tickets, agent_areas, group_names, contracts)
    opt = optimizer.run(ctx, agent_areas, group_names, home_groups)
    summary = build_summary(now.isoformat(), ctx.ndays, ctx.scale_factor, fc, cap, cov, opt)

    return {"forecast": fc, "capacity": cap, "coverage": cov, "optimizer": opt, "summary": summary}


def reset_cache() -> None:
    _analysis.cache_clear()


def get_forecast() -> dict:
    return _analysis()["forecast"]


def get_capacity() -> dict:
    return _analysis()["capacity"]


def get_coverage() -> dict:
    return _analysis()["coverage"]


def get_optimization() -> dict:
    return _analysis()["optimizer"]


def get_summary() -> dict:
    return _analysis()["summary"]
