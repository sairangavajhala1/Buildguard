"""Tests for the Dodo Payments escrow checkout integration.

The Dodo Payments SDK call is mocked so the suite runs fully offline
(no real API key or network required).
"""

import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from dodopayments.types.checkout_session_response import CheckoutSessionResponse
from dodopayments.types.product_item_req_param import ProductItemReqParam
from dodopayments.types.price_param import OneTimePrice
from fastapi.testclient import TestClient

from app.dodo_service import (
    MilestoneEscrowRequest,
    _resolve_product_id,
    create_escrow_checkout,
)
from app.state import milestones

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test-key")
os.environ.setdefault("DODO_PAYMENTS_ENVIRONMENT", "test_mode")

from app.main import app  # noqa: E402  (needs env vars set first)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    milestones.clear()
    yield
    milestones.clear()


SAMPLE_REQUEST = {
    "project_id": "proj_123",
    "milestone_id": "ms_456",
    "milestone_title": "Foundation pour",
    "amount_usd": 12500.50,
    "client_name": "Jane Builder",
    "client_email": "jane@example.com",
}

EXPECTED_BILLING_ADDRESS = {
    "country": "US",
    "city": "Austin",
    "state": "TX",
    "street": "100 Construction Way",
    "zipcode": "78701",
}


def make_session(payment_link="https://test.checkout.dodopayments.com/session/cks_abc", session_id="cks_abc"):
    return SimpleNamespace(payment_link=payment_link, session_id=session_id)


class TestResolveProductId:
    def test_env_var_wins(self, monkeypatch):
        monkeypatch.setenv("DODO_PRODUCT_ID", "pdt_from_env")
        dodo = Mock()
        assert _resolve_product_id(dodo) == "pdt_from_env"
        dodo.products.list.assert_not_called()
        dodo.products.create.assert_not_called()

    def test_blank_env_var_falls_through(self, monkeypatch):
        monkeypatch.setenv("DODO_PRODUCT_ID", "   ")
        dodo = Mock()
        dodo.products.list.return_value = SimpleNamespace(
            items=[SimpleNamespace(product_id="pdt_existing")]
        )
        assert _resolve_product_id(dodo) == "pdt_existing"

    def test_first_existing_product_used_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("DODO_PRODUCT_ID", raising=False)
        dodo = Mock()
        dodo.products.list.return_value = SimpleNamespace(
            items=[
                SimpleNamespace(product_id="pdt_first"),
                SimpleNamespace(product_id="pdt_second"),
            ]
        )
        assert _resolve_product_id(dodo) == "pdt_first"
        dodo.products.create.assert_not_called()

    def test_default_product_created_when_none_exist(self, monkeypatch):
        monkeypatch.delenv("DODO_PRODUCT_ID", raising=False)
        dodo = Mock()
        dodo.products.list.return_value = SimpleNamespace(items=[])
        dodo.products.create.return_value = SimpleNamespace(product_id="pdt_created")

        assert _resolve_product_id(dodo) == "pdt_created"

        dodo.products.create.assert_called_once_with(
            name="Milestone Escrow",
            price={
                "type": "one_time_price",
                "currency": "USD",
                "price": 10000,
                "discount": 0,
            },
            tax_category="digital_products",
        )
        # The price payload must be valid against the SDK's OneTimePrice shape.
        price = dodo.products.create.call_args.kwargs["price"]
        assert set(price) <= set(OneTimePrice.__annotations__)
        assert price["type"] == "one_time_price"


class TestCreateEscrowCheckout:
    @patch("app.dodo_service.client")
    def test_passes_expected_params(self, mock_client):
        mock_client.checkout_sessions.create.return_value = make_session()
        request = MilestoneEscrowRequest(**SAMPLE_REQUEST)

        result = create_escrow_checkout(request)

        assert mock_client.products.list.call_count == 0  # env var short-circuits
        mock_client.checkout_sessions.create.assert_called_once_with(
            product_cart=[
                {
                    "product_id": "pdt_test_escrow",
                    "amount": 1250050,
                    "quantity": 1,
                }
            ],
            billing_currency="USD",
            billing_address=EXPECTED_BILLING_ADDRESS,
            customer={"name": "Jane Builder", "email": "jane@example.com"},
            metadata={
                "project_id": "proj_123",
                "milestone_id": "ms_456",
                "type": "escrow_deposit",
            },
            return_url="http://localhost:8000/docs#/Escrow/deposit_success",
        )
        assert result == {
            "checkout_url": "https://test.checkout.dodopayments.com/session/cks_abc",
            "session_id": "cks_abc",
        }

    @patch("app.dodo_service.client")
    def test_amount_is_converted_to_cents(self, mock_client):
        mock_client.checkout_sessions.create.return_value = make_session()
        request = MilestoneEscrowRequest(**SAMPLE_REQUEST)

        create_escrow_checkout(request)

        cart_item = mock_client.checkout_sessions.create.call_args.kwargs["product_cart"][0]
        assert cart_item["amount"] == 1250050

    @patch("app.dodo_service.client")
    def test_checkout_uses_resolved_product_id(self, mock_client, monkeypatch):
        """Without DODO_PRODUCT_ID, the resolved product flows into the cart."""
        monkeypatch.delenv("DODO_PRODUCT_ID", raising=False)
        mock_client.products.list.return_value = SimpleNamespace(
            items=[SimpleNamespace(product_id="pdt_existing")]
        )
        mock_client.checkout_sessions.create.return_value = make_session()

        create_escrow_checkout(MilestoneEscrowRequest(**SAMPLE_REQUEST))

        cart_item = mock_client.checkout_sessions.create.call_args.kwargs["product_cart"][0]
        assert cart_item["product_id"] == "pdt_existing"
        mock_client.products.create.assert_not_called()

    def test_call_args_are_valid_for_the_real_sdk(self):
        """Guard against drift between our call and the SDK's typed API."""
        import inspect

        try:
            from dodopayments.resources.checkout_sessions import CheckoutSessionsResource

            create_params = inspect.signature(CheckoutSessionsResource.create).parameters
        except ImportError:  # pragma: no cover - structure changed
            create_params = None

        request = MilestoneEscrowRequest(**SAMPLE_REQUEST)
        with patch("app.dodo_service.client") as mock_client:
            mock_client.checkout_sessions.create.return_value = make_session()
            create_escrow_checkout(request)

        call_kwargs = mock_client.checkout_sessions.create.call_args.kwargs
        if create_params is not None:
            # Every kwarg must be an accepted parameter of the SDK method.
            unknown = set(call_kwargs) - set(create_params)
            assert not unknown, f"SDK does not accept kwargs: {unknown}"

        # Cart item keys must be valid ProductItemReq fields.
        cart_keys = set(call_kwargs["product_cart"][0])
        assert cart_keys <= set(ProductItemReqParam.__annotations__), (
            f"Invalid product_cart keys: {cart_keys - set(ProductItemReqParam.__annotations__)}"
        )

        # The response mapping must be expressible with the real SDK types.
        real_response = CheckoutSessionResponse(
            session_id="cks_abc",
            checkout_url="https://test.checkout.dodopayments.com/session/cks_abc",
        )
        with patch("app.dodo_service.client") as mock_client:
            mock_client.checkout_sessions.create.return_value = real_response
            result = create_escrow_checkout(request)
        assert result["checkout_url"] == real_response.checkout_url
        assert result["session_id"] == "cks_abc"


class TestDepositEndpoint:
    @patch("app.dodo_service.client")
    def test_deposit_endpoint_returns_checkout_and_saves_milestone(self, mock_client):
        mock_client.checkout_sessions.create.return_value = make_session()

        response = client.post("/api/escrow/deposit", json=SAMPLE_REQUEST)

        assert response.status_code == 200
        body = response.json()
        assert body["checkout_url"] == "https://test.checkout.dodopayments.com/session/cks_abc"
        assert body["session_id"] == "cks_abc"
        assert body["milestone_id"] == "ms_456"

        saved = milestones["ms_456"]
        assert saved["escrow_status"] == "ESCROW_PENDING"
        assert saved["audit_status"] == "NOT_SUBMITTED"
        assert saved["contracted_amount"] == SAMPLE_REQUEST["amount_usd"]
        assert saved["checkout_url"] == body["checkout_url"]

    @patch("app.dodo_service.client")
    def test_deposit_endpoint_generates_ids_when_omitted(self, mock_client):
        mock_client.checkout_sessions.create.return_value = make_session()
        payload = {
            "milestone_title": "Foundation pour",
            "amount_usd": 5000,
            "client_email": "jane@example.com",
        }

        response = client.post("/api/escrow/deposit", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["milestone_id"].startswith("ms_")
        assert body["milestone_id"] in milestones
        assert milestones[body["milestone_id"]]["project_id"].startswith("proj_")
        # Generated ids flow into Dodo metadata.
        metadata = mock_client.checkout_sessions.create.call_args.kwargs["metadata"]
        assert metadata["milestone_id"] == body["milestone_id"]

    @patch("app.dodo_service.client")
    def test_deposit_endpoint_propagates_sdk_errors(self, mock_client):
        mock_client.checkout_sessions.create.side_effect = RuntimeError("boom")

        response = client.post("/api/escrow/deposit", json=SAMPLE_REQUEST)

        assert response.status_code == 502
        assert "boom" in response.json()["detail"]
        assert len(milestones) == 0  # nothing persisted on failure

    def test_deposit_endpoint_validates_payload(self):
        invalid = dict(SAMPLE_REQUEST, amount_usd=-5)
        response = client.post("/api/escrow/deposit", json=invalid)
        assert response.status_code == 422


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))