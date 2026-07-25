"""Reports service — the analytics computed on Sync and cached for the copilot.

build_bundle() is the full report set for the UI tabs/pop-ups. reports_context()
is a compact snapshot injected into the agent as a stable prefix (baseline the
agent answers from, without recomputing). sync() busts the caches so the next
build reflects freshly fetched data.
"""

from __future__ import annotations

from functools import lru_cache

from app.ai import clients
from app.ai.insights import metrics as ins_metrics
from app.ai.sla import risk
from app.services import wfm
from app.tools.insights import OperationalInsightsTool


@lru_cache(maxsize=1)
def build_bundle() -> dict:
    """Full reports for the UI: what each tab/pop-up renders."""
    return {
        "summary": wfm.get_summary(),
        "forecast": wfm.get_forecast(),
        "capacity": wfm.get_capacity(),
        "coverage": wfm.get_coverage(),
        "optimizer": wfm.get_optimization(),
        "insights": OperationalInsightsTool().invoke({"metric": "all"}),
        "clients": clients.client_load(top_n=8),
    }


@lru_cache(maxsize=1)
def reports_context() -> dict:
    """Compact baseline snapshot for the agent (stable prefix for prompt caching)."""
    s = wfm.get_summary()
    fc = wfm.get_forecast()
    cov = wfm.get_coverage()
    opt = wfm.get_optimization()
    ins = OperationalInsightsTool().invoke({"metric": "all"})
    cl = clients.client_load(top_n=5)
    sla = risk.high_priority_compliance()

    return {
        "as_of": s["as_of"],
        "scale_factor": s["scale_factor"],
        "forecast": {"mean_per_day": fc["mean_per_day"], "model": s["forecast"]["chosen_model"],
                     "mae": s["forecast"]["mae"], "at_noise_floor": s["forecast"]["at_noise_floor"]},
        "capacity": {"understaffed_pct": s["capacity"]["understaffed_pct"],
                     "overstaffed_pct": s["capacity"]["overstaffed_pct"], "peak_hour": s["capacity"]["peak_hour"]},
        "coverage": {"net_shortage_agent_hours": cov["net_shortage_agent_hours"],
                     "worst_skill": s["coverage"]["worst_skill"], "worst_gap": s["coverage"]["worst_gap"],
                     "short_skills": [{"skill": x["skill"], "gap": x["gap"]} for x in cov["skills"] if x["gap"] < 0][:4]},
        "sla_baseline": {"high_priority_compliance_pct": sla["high_priority_compliance_pct"],
                         "overall_utilization": sla["overall_utilization"]},
        "reallocation": {"unmet_before": opt["unmet_before"], "unmet_after": opt["unmet_after"],
                         "reduction_pct": opt["reduction_pct"], "moves": opt["moves"],
                         "reassign": opt["reassign"], "cross_train": opt["cross_train"], "moves_into": opt["moves_into"]},
        "trends": {"headline": ins["headline"], "anomalies": len(ins["anomalies"]),
                   "unfavorable_movers": [{"kpi": k["name"], "change_pct": k["change_pct"]}
                                          for k in ins["kpis"] if k["favorable"] is False][:3]},
        "clients": {"is_concentrated": cl["concentration"]["is_concentrated"],
                    "top": [{"client": c["client"], "share_pct": c["share_pct"], "dedicated": c["dedicated"]}
                            for c in cl["clients"][:3]]},
    }


def sync() -> dict:
    """Recompute from (conceptually) fresh data and return the full bundle."""
    build_bundle.cache_clear()
    reports_context.cache_clear()
    wfm.reset_cache()
    ins_metrics.weekly.cache_clear()
    ins_metrics.ticket_frame.cache_clear()
    risk._scored.cache_clear()
    return build_bundle()
