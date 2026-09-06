import pytest
from unittest.mock import patch
from app.dodo_service import create_escrow_checkout, MilestoneEscrowRequest

SAMPLE_REQUEST = {
    "project_id": "proj_123",
    "milestone_id": "ms_456",
    "milestone_title": "Foundation",
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


def make_session():
    class Session:
        checkout_url = "https://checkout.dodopayments.com/pay/cs_test_123"
        payment_link = None
        session_id = "sess_123"
    return Session()


class TestCreateEscrowCheckout:
    @patch("app.dodo_service.client")
    def test_passes_expected_params(self, mock_client):
        mock_client.checkout_sessions.create.return_value = make_session()
        request = MilestoneEscrowRequest(**SAMPLE_REQUEST)

        result = create_escrow_checkout(request)

        mock_client.checkout_sessions.create.assert_called_once_with(
            product_cart=[
                {
                    "product_id": "pdt_0Nn0pIJG6kScrGnKjZWEk",
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
            return_url="http://localhost:8000/?status=funded",
        )
        assert result["session_id"] == "sess_123"
        assert result["checkout_url"] == "https://checkout.dodopayments.com/pay/cs_test_123"