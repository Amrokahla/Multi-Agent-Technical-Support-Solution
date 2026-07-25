"""Client-load engine — which clients drive the ticket load, and how concentrated.

Supports the "one client causing most of the load" reasoning: rank clients by
recent ticket rate, flag concentration relative to a uniform split, and show each
client's trend and whether they are on a dedicated contract.
"""

from __future__ import annotations

import json

import pandas as pd

from app.ai.wfm.loaders import analysis_now, load_contracts
from app.ai.wfm.loaders import load_tickets
from app.config import get_settings


def _org_names() -> dict[int, str]:
    orgs = json.loads((get_settings().data_dir / "organizations.json").read_text())
    return {o["id"]: o["name"] for o in orgs}


def client_load(top_n: int = 5, window_days: int = 28) -> dict:
    tickets = load_tickets()
    contracts = load_contracts().set_index("organization_id")
    org_names = _org_names()

    now = analysis_now()
    window_start = now - pd.Timedelta(days=window_days)
    prior_start = window_start - pd.Timedelta(days=window_days)
    recent = tickets[tickets["created_at"] >= window_start]
    prior = tickets[(tickets["created_at"] >= prior_start) & (tickets["created_at"] < window_start)]

    counts = recent["organization_id"].value_counts()
    prior_counts = prior["organization_id"].value_counts()
    total = int(len(recent)) or 1
    active_orgs = int((counts > 0).sum()) or 1
    uniform_share = 100 / active_orgs

    clients = []
    for org_id, n in counts.head(top_n).items():
        in_contract = org_id in contracts.index
        pn = int(prior_counts.get(org_id, 0))
        clients.append({
            "organization_id": int(org_id),
            "client": str(contracts.loc[org_id, "name"]) if in_contract else org_names.get(org_id, f"Org {org_id}"),
            "tickets": int(n),
            "share_pct": round(100 * n / total, 1),
            "per_day": round(n / window_days, 1),
            "dedicated": bool(contracts.loc[org_id, "dedicated"]) if in_contract else False,
            "trend_pct": round(100 * (n - pn) / pn, 1) if pn else None,
        })

    top1 = clients[0]["share_pct"] if clients else 0.0
    top3 = round(sum(c["share_pct"] for c in clients[:3]), 1)
    return {
        "window_days": window_days,
        "total_tickets": total,
        "active_clients": active_orgs,
        "clients": clients,
        "concentration": {
            "top1_share_pct": top1,
            "top3_share_pct": top3,
            "uniform_share_pct": round(uniform_share, 2),
            "top1_vs_uniform": round(top1 / uniform_share, 1) if uniform_share else None,
            "is_concentrated": bool(top1 >= 3 * uniform_share or top3 >= 30),
        },
    }
