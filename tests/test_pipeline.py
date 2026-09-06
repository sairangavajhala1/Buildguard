"""End-to-end pipeline test: escrow deposit -> payment confirm -> audit -> CFO.

Runs the full API flow against the in-memory state store with the Dodo SDK
client mocked (fully offline).
"""

import os
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.state import milestones

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test-key")
os.environ.setdefault("DODO_PAYMENTS_ENVIRONMENT", "test_mode")

from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    milestones.clear()
    yield
    milestones.clear()


def _deposit(mock_client) -> str:
    """Create an escrow deposit and return the milestone id."""
    mock_client.checkout_sessions.create.return_value = SimpleNamespace(
        payment_link="https://test.checkout.dodopayments.com/session/cks_dep",
        session_id="cks_dep",
    )
    response = client.post(
        "/api/escrow/deposit",
        json={
            "milestone_title": "Foundation pour",
            "amount_usd": 10000.00,
            "client_name": "Jane Builder",
            "client_email": "jane@example.com",
        },
    )
    assert response.status_code == 200
    return response.json()["milestone_id"]


def test_full_pipeline_deposit_confirm_quarantine_settle():
    with patch("app.dodo_service.client") as mock_client:
        milestone_id = _deposit(mock_client)

        # 1. New milestone is escrow-pending, not yet audited.
        assert milestones[milestone_id]["escrow_status"] == "ESCROW_PENDING"
        assert milestones[milestone_id]["audit_status"] == "NOT_SUBMITTED"

        # 2. Simulate the Dodo payment-succeeded webhook.
        confirm = client.post(f"/api/escrow/mock-confirm/{milestone_id}")
        assert confirm.status_code == 200
        assert confirm.json()["escrow_status"] == "ESCROW_LOCKED"
        assert milestones[milestone_id]["escrow_status"] == "ESCROW_LOCKED"

        # 3. Submit an invoice that fails the safety inspection -> quarantined.
        audit = client.post(
            "/api/milestone/audit",
            json={
                "milestone_id": milestone_id,
                "billed_amount": 5000.00,
                "invoice_date": (date.today() - timedelta(days=1)).isoformat(),
                "insurance_expiry_date": (date.today() + timedelta(days=365)).isoformat(),
                "safety_inspection_passed": False,
            },
        )
        assert audit.status_code == 200
        audit_body = audit.json()
        assert audit_body["status"] == "QUARANTINED"
        assert "Safety inspection not passed" in audit_body["violations"]
        assert milestones[milestone_id]["audit_status"] == "QUARANTINED"
        assert milestones[milestone_id]["violations"] == audit_body["violations"]
        assert milestones[milestone_id]["billed_amount"] == 5000.00

        # 4. CFO human-in-the-loop override -> settled, quarantine cleared.
        approve = client.post(f"/api/milestone/cfo-approve/{milestone_id}")
        assert approve.status_code == 200
        assert approve.json()["audit_status"] == "SETTLED"
        assert milestones[milestone_id]["audit_status"] == "SETTLED"
        assert milestones[milestone_id]["violations"] == []

    # 5. Ledger reflects the settled milestone.
    ledger = client.get("/api/milestones")
    assert ledger.status_code == 200
    rows = {m["milestone_id"]: m for m in ledger.json()["milestones"]}
    assert rows[milestone_id]["escrow_status"] == "ESCROW_LOCKED"
    assert rows[milestone_id]["audit_status"] == "SETTLED"


def test_valid_audit_approves_milestone():
    with patch("app.dodo_service.client") as mock_client:
        milestone_id = _deposit(mock_client)

        audit = client.post(
            "/api/milestone/audit",
            json={
                "milestone_id": milestone_id,
                "billed_amount": 8000.00,
                "invoice_date": (date.today() - timedelta(days=1)).isoformat(),
                "insurance_expiry_date": (date.today() + timedelta(days=365)).isoformat(),
                "safety_inspection_passed": True,
            },
        )
        assert audit.status_code == 200
        assert audit.json()["status"] == "APPROVED"
        assert audit.json()["violations"] == []
        assert milestones[milestone_id]["audit_status"] == "APPROVED"


def test_overbilling_quarantines_milestone():
    with patch("app.dodo_service.client") as mock_client:
        milestone_id = _deposit(mock_client)

        audit = client.post(
            "/api/milestone/audit",
            json={
                "milestone_id": milestone_id,
                "billed_amount": 15000.00,  # exceeds 10000 contracted
                "invoice_date": (date.today() - timedelta(days=1)).isoformat(),
                "insurance_expiry_date": (date.today() + timedelta(days=365)).isoformat(),
                "safety_inspection_passed": True,
            },
        )
        assert audit.status_code == 200
        assert audit.json()["status"] == "QUARANTINED"
        assert any("exceeds" in v for v in audit.json()["violations"])


def test_unknown_milestone_returns_404():
    assert client.post("/api/escrow/mock-confirm/ms_missing").status_code == 404
    assert (
        client.post(
            "/api/milestone/audit",
            json={
                "milestone_id": "ms_missing",
                "billed_amount": 100,
                "invoice_date": "2026-01-01",
                "insurance_expiry_date": "2027-01-01",
                "safety_inspection_passed": True,
            },
        ).status_code
        == 404
    )
    assert client.post("/api/milestone/cfo-approve/ms_missing").status_code == 404


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))