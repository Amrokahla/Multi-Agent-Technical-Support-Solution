"""Build the cross-stage summary from the four stage results.

Shared by the default (frozen-dataset) service and the CSV-upload path so both
report the same headline shape.
"""

from __future__ import annotations


def _chosen_score(forecast_result: dict) -> dict:
    chosen = forecast_result["chosen_model"]
    return next(m for m in forecast_result["models"] if m["model"] == chosen)


def build_summary(as_of: str, window_days: int, scale_factor: float, fc: dict, cap: dict, cov: dict, opt: dict) -> dict:
    score = _chosen_score(fc)
    worst = cov["skills"][0]  # skills are sorted most-negative gap first
    return {
        "as_of": as_of,
        "window_days": window_days,
        "scale_factor": scale_factor,
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
