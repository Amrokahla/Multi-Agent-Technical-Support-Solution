"""Staffing overlay — turn baseline breach propensity into staffing-aware risk.

Baseline risk p0 comes from the calibrated model. A deterministic multiplier from
the coverage engine scales it by how stressed each queue is at the requested
staffing: p = clip(p0 * m(u), 0, 1), u = required / available. This is what makes
"with N agents" move the answer, without faking a causal ML relationship.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from app.ai.sla import features as F
from app.ai.sla.model import get_model
from app.ai.wfm.loaders import agent_home_groups
from app.services import wfm

UTIL_TARGET = 0.8
# Probabilities should never read exactly 0 or 1 — cap so compliance stays informative.
RISK_CAP = 0.97


def multiplier(u: float) -> float:
    """Risk multiplier ~ utilization vs target: 1.0 at target, rising when short.

    Linear (not the notebook's ^1.5) so it discriminates across the plausible
    staffing range instead of saturating once badly understaffed.
    """
    return float(np.clip(u / UTIL_TARGET, 0.5, 3.5))


def roster_size() -> int:
    return len(agent_home_groups())


@lru_cache(maxsize=1)
def _scored() -> pd.DataFrame:
    """Training frame with the model's baseline breach probability per instance."""
    model = get_model()
    frame = F.build_training_frame()
    return frame.assign(p0=model.predict_proba(frame))


def _staff_factor(available_agents: int | None) -> float:
    return (available_agents / roster_size()) if available_agents else 1.0


def _risk_level(risk: float) -> str:
    return "high" if risk >= 0.5 else "medium" if risk >= 0.3 else "low"


def queue_risk(available_agents: int | None = None, uplift_pct: float = 0.0) -> list[dict]:
    scored = _scored()
    by_queue = scored.groupby("queue")["p0"].mean().to_dict()
    overall_p0 = float(scored["p0"].mean())
    demand_factor = 1 + uplift_pct / 100
    staff_factor = _staff_factor(available_agents)

    rows = []
    for s in wfm.get_coverage()["skills"]:
        required = s["required"] * demand_factor
        available = max(s["available"] * staff_factor, 1e-6)
        u = required / available
        mult = multiplier(u)
        p0 = by_queue.get(s["skill"], overall_p0)
        risk = float(np.clip(p0 * mult, 0, RISK_CAP))
        rows.append({
            "queue": s["skill"],
            "baseline_risk": round(p0, 3),
            "utilization": round(u, 2),
            "multiplier": round(mult, 2),
            "breach_risk": round(risk, 3),
            "required_agent_hours": round(required, 1),
            "available_agent_hours": round(available, 1),
            "risk_level": _risk_level(risk),
        })
    rows.sort(key=lambda r: -r["breach_risk"])
    return rows


def high_priority_compliance(available_agents: int | None = None, uplift_pct: float = 0.0) -> dict:
    scored = _scored()
    p0_hp = float(scored.loc[scored["priority"].isin(["urgent", "high"]), "p0"].mean())
    skills = wfm.get_coverage()["skills"]
    total_required = sum(s["required"] for s in skills) * (1 + uplift_pct / 100)
    total_available = max(sum(s["available"] for s in skills) * _staff_factor(available_agents), 1e-6)
    u = total_required / total_available
    mult = multiplier(u)
    hp_breach = float(np.clip(p0_hp * mult, 0, RISK_CAP))
    return {
        "high_priority_compliance_pct": round(100 * (1 - hp_breach), 1),
        "overall_utilization": round(u, 2),
        "overall_multiplier": round(mult, 2),
        "hp_baseline_risk": round(p0_hp, 3),
    }


def high_risk_hours(available_agents: int | None = None, uplift_pct: float = 0.0, top: int = 3) -> list[int]:
    staff_factor = _staff_factor(available_agents)
    demand_factor = 1 + uplift_pct / 100
    hours = []
    for pt in wfm.get_capacity()["intraday"]:
        available = max(pt["available"] * staff_factor, 1e-6)
        hours.append((pt["hour"], pt["required"] * demand_factor / available))
    hours.sort(key=lambda h: -h[1])
    return [h for h, _ in hours[:top]]
