"""Smoke tests for the app skeleton. Run from backend/: ``pytest``."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_data_health_returns_manifest_counts():
    response = client.get("/api/health/data")
    assert response.status_code == 200
    body = response.json()
    # The frozen dataset ships with the repo, so counts should be populated.
    assert body["ticket_count"] == 8000
