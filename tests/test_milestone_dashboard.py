"""Tests for the BuildGuard milestone escrow + audit + CFO-approve workflow.

The Dodo Payments SDK and Smallest.ai TTS are mocked so the suite runs fully
offline (no real API keys or network required).
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import state
from app.main import app

# Fake Dodo session response.
from types import SimpleNamespace


@pytest.fixture(autouse=True)
def clean_state():
    state.reset()
    yield
    state.reset()


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("DODO_PAYMENTS_API_KEY", raising=False)
    return TestClient(app)


def make_session(payment_link="https://test.checkout.dodopayments.com/session/cks_abc"):
    return SimpleNamespace(payment_link=payment_link, session_id="cks_abc")


def create_a_milestone(client, monkeypatch):
    """Create a milestone in ESCROW_PENDING (returns its id)."""
    monkeypatch.setenv("DODO_PAYMENTS_API_KEY", "test-key")
    with patch("app.dodo_service.client") as mock_client:
        mock_client.checkout_sessions.create.return_value = make_session()
        return client.post(
            "/api/milestone/create",
            json={
                "project_name": "Riverside Tower",
                "milestone_title": "Foundation pour",
                "contracted_amount": 100000.0,
                "client_name": "Jane Builder",
                "client_email": "jane@example.com",
            },
        )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_milestone_without_api_key_returns_sandbox_checkout(client):
    resp = client.post(
        "/api/milestone/create",
        json={
            "project_name": "Riverside Tower",
            "milestone_title": "Foundation pour",
            "contracted_amount": 100000.0,
            "client_name": "Jane Builder",
            "client_email": "jane@example.com",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ESCROW_PENDING"
    assert body["checkout_url"].startswith("https://test.checkout.dodopayments.com/sandbox/")
    assert body["milestone_id"].startswith("MS-")
    # Stored via state.
    stored = state.get_milestone(body["milestone_id"])
    assert stored is not None
    assert stored["status"] == "ESCROW_PENDING"
    assert stored["contracted_amount"] == 100000.0


def test_create_milestone_with_api_key_calls_dodo(client, monkeypatch):
    monkeypatch.setenv("DODO_PAYMENTS_API_KEY", "test-key")
    with patch("app.dodo_service.client") as mock_client:
        mock_client.checkout_sessions.create.return_value = make_session()
        resp = client.post(
            "/api/milestone/create",
            json={
                "project_name": "Riverside Tower",
                "milestone_title": "Foundation pour",
                "contracted_amount": 100000.0,
                "client_name": "Jane Builder",
                "client_email": "jane@example.com",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["checkout_url"] == "https://test.checkout.dodopayments.com/session/cks_abc"


def test_create_validates_amount(client):
    resp = client.post(
        "/api/milestone/create",
        json={
            "project_name": "Riverside Tower",
            "milestone_title": "Foundation pour",
            "contracted_amount": -5,
            "client_name": "Jane Builder",
            "client_email": "jane@example.com",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_audit_approves_without_api_key_sandbox(client, monkeypatch):
    created = create_a_milestone(client, monkeypatch)
    mid = created.json()["milestone_id"]

    resp = client.post(
        "/api/milestone/audit",
        json={
            "milestone_id": mid,
            "invoice_date": "2026-08-15",
            "billed_amount": 100000.0,
            "insurance_date": "2026-12-31",
            "safety_flag": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ESCROW_FUNDED"
    assert body["quarantined"] is False
    assert body["violations"] == []


def test_audit_quarantines_on_high_billed_amount(client, monkeypatch):
    created = create_a_milestone(client, monkeypatch)
    mid = created.json()["milestone_id"]

    resp = client.post(
        "/api/milestone/audit",
        json={
            "milestone_id": mid,
            "invoice_date": "2026-08-15",
            "billed_amount": 120000.0,  # > 5% over contracted 100k
            "insurance_date": "2026-12-31",
            "safety_flag": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "QUARANTINED"
    assert body["quarantined"] is True
    assert len(body["violations"]) >= 1
    # Recorded on the stored milestone.
    assert state.get_milestone(mid)["status"] == "QUARANTINED"
    assert state.get_milestone(mid)["billed_amount"] == 120000.0


def test_audit_quarantines_on_safety_failure(client, monkeypatch):
    created = create_a_milestone(client, monkeypatch)
    mid = created.json()["milestone_id"]
    resp = client.post(
        "/api/milestone/audit",
        json={
            "milestone_id": mid,
            "invoice_date": "2026-08-15",
            "billed_amount": 100000.0,
            "insurance_date": "2026-12-31",
            "safety_flag": False,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "QUARANTINED"


def test_audit_unknown_milestone_404(client):
    resp = client.post(
        "/api/milestone/audit",
        json={
            "milestone_id": "MS-9999",
            "invoice_date": "2026-08-15",
            "billed_amount": 100000.0,
            "insurance_date": "2026-12-31",
            "safety_flag": True,
        },
    )
    assert resp.status_code == 404


def test_audit_invalid_date_422(client, monkeypatch):
    created = create_a_milestone(client, monkeypatch)
    mid = created.json()["milestone_id"]
    resp = client.post(
        "/api/milestone/audit",
        json={
            "milestone_id": mid,
            "invoice_date": "08/15/2026",
            "billed_amount": 100000.0,
            "insurance_date": "2026-12-31",
            "safety_flag": True,
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# CFO approve
# ---------------------------------------------------------------------------


def test_cfo_approve_quarantined_milestone(client, monkeypatch):
    created = create_a_milestone(client, monkeypatch)
    mid = created.json()["milestone_id"]
    client.post(
        "/api/milestone/audit",
        json={
            "milestone_id": mid,
            "invoice_date": "2026-08-15",
            "billed_amount": 120000.0,
            "insurance_date": "2026-12-31",
            "safety_flag": True,
        },
    )

    resp = client.post(
        "/api/milestone/cfo-approve", json={"milestone_id": mid}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SETTLED"
    assert state.get_milestone(mid)["status"] == "SETTLED"


def test_cfo_approve_unknown_404(client):
    resp = client.post(
        "/api/milestone/cfo-approve", json={"milestone_id": "MS-9999"}
    )
    assert resp.status_code == 404


def test_cfo_approve_already_settled_409(client, monkeypatch):
    created = create_a_milestone(client, monkeypatch)
    mid = created.json()["milestone_id"]
    client.post("/api/milestone/cfo-approve", json={"milestone_id": mid})
    resp = client.post("/api/milestone/cfo-approve", json={"milestone_id": mid})
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# List + dashboard
# ---------------------------------------------------------------------------


def test_list_milestones(client, monkeypatch):
    create_a_milestone(client, monkeypatch)
    resp = client.get("/api/milestones")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "ESCROW_PENDING"


def test_dashboard_served_at_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "BuildGuard" in resp.text
    assert "tailwindcss" in resp.text