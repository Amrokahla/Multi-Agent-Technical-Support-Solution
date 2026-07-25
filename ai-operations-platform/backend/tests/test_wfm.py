"""Tests for the workforce-optimization pipeline. Run from backend/: ``pytest``.

The frozen dataset ships with the repo, so these assert the concrete, validated
results documented in docs/00-workforce-optimization.md. Forecast accuracy can
shift slightly with library versions, so those checks are on the conclusion
(at the noise floor), not an exact MAE.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_all_wfm_endpoints_ok():
    for path in ("summary", "forecast", "capacity", "coverage", "optimize"):
        assert client.get(f"/api/wfm/{path}").status_code == 200


def test_capacity_scale_factor_and_balance():
    body = client.get("/api/wfm/capacity").json()
    assert body["scale_factor"] == 15.5
    assert body["handle_min_median"] == 30.0
    assert body["peak_hour"] == 10
    # The roster is misaligned: a real share of slots both under- and overstaffed.
    assert body["understaffed_pct"] > 25
    assert body["overstaffed_pct"] > 35


def test_coverage_tier1_is_the_worst_gap():
    body = client.get("/api/wfm/coverage").json()
    worst = body["skills"][0]
    assert worst["skill"].startswith("Tier 1")
    assert worst["gap"] < -50
    assert body["net_shortage_agent_hours"] < 0
    matrix = body["gap_matrix"]
    assert len(matrix["hours"]) == 24
    assert len(matrix["values"]) == 24
    assert len(matrix["skills"]) == len(matrix["values"][0])


def test_optimizer_closes_most_of_the_gap():
    body = client.get("/api/wfm/optimize").json()
    assert body["unmet_before"] > body["unmet_after"]
    assert body["reduction_pct"] > 85
    assert body["moves"] == body["reassign"] + body["cross_train"]
    # Every recommendation targets a skill and carries a valid action type.
    for rec in body["recommendations"]:
        assert rec["type"] in {"reassign", "cross-train"}
        assert rec["from_skill"] and rec["to_skill"]


def test_summary_forecast_at_noise_floor():
    body = client.get("/api/wfm/summary").json()
    assert body["forecast"]["at_noise_floor"] is True
    assert body["scale_factor"] == 15.5
    assert body["coverage"]["worst_skill"].startswith("Tier 1")


def test_sample_upload_runs_full_pipeline():
    body = client.get("/api/wfm/sample").json()
    assert body["meta"]["roster_modeled"] is True
    assert body["meta"]["tickets_used"] == 8000
    assert body["meta"]["agents_modeled"] > 0
    # The full pipeline populated every stage.
    assert body["optimizer"]["reduction_pct"] > 0
    assert len(body["coverage"]["gap_matrix"]["values"]) == 24


def test_analyze_detects_columns_and_runs():
    dates = [f"2026-01-{d:02d}T09:00:00Z" for d in range(1, 29)]
    rows = "\n".join(f"{d},Support" if i % 2 else f"{d},Billing" for i, d in enumerate(dates))
    csv = f"Created at,Group\n{rows}\n".encode()
    resp = client.post("/api/wfm/analyze", files={"file": ("export.csv", csv, "text/csv")})
    assert resp.status_code == 200
    assert resp.json()["meta"]["columns"]["created_at"] == "Created at"


def test_analyze_rejects_csv_without_date():
    resp = client.post("/api/wfm/analyze", files={"file": ("bad.csv", b"a,b\n1,2\n", "text/csv")})
    assert resp.status_code == 422
    assert "created" in resp.json()["detail"].lower()
