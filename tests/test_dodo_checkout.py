"""Tests for the Dodo Payments escrow checkout integration.

The Dodo Payments SDK call is mocked so the suite runs fully offline
(no real API key or network required).
"""

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from dodopayments.types.checkout_session_response import CheckoutSessionResponse
from fastapi.testclient import TestClient

from app.dodo_service import MilestoneEscrowRequest, create_escrow_checkout

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test-key")
os.environ.setdefault("DODO_PAYMENTS_ENVIRONMENT", "test_mode")

from app.main import app  # noqa: E402  (needs env vars set first)

client = TestClient(app)


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


class TestCreateEscrowCheckout:
    @patch("app.dodo_service.client")
    def test_passes_expected_params(self, mock_client):
        mock_client.checkout_sessions.create.return_value = make_session()
        request = MilestoneEscrowRequest(**SAMPLE_REQUEST)

        result = create_escrow_checkout(request)

        mock_client.checkout_sessions.create.assert_called_once_with(
            product_cart=[
                {
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

    def test_call_args_are_valid_for_the_real_sdk(self):
        """Guard against drift between our call and the SDK's typed API."""
        import inspect

        try:
            from dodopayments.resources.checkout_sessions import CheckoutSessionsResource

            create_params = inspect.signature(CheckoutSessionsResource.create).parameters
        except ImportError:  # pragma: no cover - structure changed
            create_params = None

        from dodopayments.types.product_item_req_param import ProductItemReqParam

        valid_cart_keys = set(ProductItemReqParam.__annotations__)

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
        assert cart_keys <= valid_cart_keys, f"Invalid product_cart keys: {cart_keys - valid_cart_keys}"

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
    def test_deposit_endpoint_returns_checkout(self, mock_client):
        mock_client.checkout_sessions.create.return_value = make_session()

        response = client.post("/api/escrow/deposit", json=SAMPLE_REQUEST)

        assert response.status_code == 200
        assert response.json() == {
            "checkout_url": "https://test.checkout.dodopayments.com/session/cks_abc",
            "session_id": "cks_abc",
        }

    @patch("app.dodo_service.client")
    def test_deposit_endpoint_propagates_sdk_errors(self, mock_client):
        mock_client.checkout_sessions.create.side_effect = RuntimeError("boom")

        response = client.post("/api/escrow/deposit", json=SAMPLE_REQUEST)

        assert response.status_code == 502
        assert "boom" in response.json()["detail"]

    def test_deposit_endpoint_validates_payload(self):
        invalid = dict(SAMPLE_REQUEST, amount_usd=-5)
        response = client.post("/api/escrow/deposit", json=invalid)
        assert response.status_code == 422


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))