"""Workforce-optimization service.

Runs the four-stage pipeline over the frozen dataset and caches the result. The
data is immutable, so the analysis is computed once (lazily) and reused; call
``reset_cache`` in tests that swap the underlying data.
"""

from __future__ import annotations

from functools import lru_cache

from app.ai.wfm import capacity, coverage, forecast, loaders, optimizer
from app.ai.wfm.workload import build_context


def _chosen_score(forecast_result: dict) -> dict:
    chosen = forecast_result["chosen_model"]
    return next(m for m in forecast_result["models"] if m["model"] == chosen)


def _build_summary(now, ctx, fc: dict, cap: dict, cov: dict, opt: dict) -> dict:
    score = _chosen_score(fc)
    worst = cov["skills"][0]  # skills are sorted most-negative gap first
    return {
        "as_of": now.isoformat(),
        "window_days": ctx.ndays,
        "scale_factor": ctx.scale_factor,
        "forecast": {
            "chosen_model": fc["chosen_model"],
            "mae": score["mae"],
            "mape": score["mape"],
            "noise_floor_mae": fc["noise_floor_mae"],
            "at_noise_floor": score["mae"] <= fc["noise_floor_mae"] * 1.15,
        },
        "capacity": {
            "understaffed_pct": cap["understaffed_pct"],
            "overstaffed_pct": cap["overstaffed_pct"],
            "peak_hour": cap["peak_hour"],
        },
        "coverage": {
            "net_shortage_agent_hours": cov["net_shortage_agent_hours"],
            "understaffed_cells": cov["understaffed_cells"],
            "total_cells": cov["total_cells"],
            "worst_skill": worst["skill"],
            "worst_gap": worst["gap"],
        },
        "optimizer": {
            "unmet_before": opt["unmet_before"],
            "unmet_after": opt["unmet_after"],
            "reduction_pct": opt["reduction_pct"],
            "moves": opt["moves"],
            "reassign": opt["reassign"],
            "cross_train": opt["cross_train"],
        },
    }


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
    summary = _build_summary(now, ctx, fc, cap, cov, opt)

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
