"""Dodo Payments escrow integration service.

Creates Dodo Payments checkout sessions that collect milestone escrow
deposits. The client is configured from environment variables (loaded from a
local ``.env`` file when present):

- ``DODO_PAYMENTS_API_KEY``: required; the Dodo Payments API key.
- ``DODO_PAYMENTS_ENVIRONMENT``: optional; ``"test_mode"`` (default) or
  ``"live_mode"``.
- ``DODO_PRODUCT_ID``: optional; the Dodo product used for escrow lines
  (default ``"pdt_buildguard_escrow"``).
"""

import os

from dotenv import load_dotenv
from dodopayments import DodoPayments
from pydantic import BaseModel, Field

load_dotenv()


class MilestoneEscrowRequest(BaseModel):
    """Request payload for creating an escrow checkout session."""

    project_id: str = ""
    milestone_id: str = ""
    milestone_title: str
    amount_usd: float = Field(gt=0)
    client_name: str = ""
    client_email: str


def create_client() -> DodoPayments:
    """Build the Dodo Payments SDK client from environment variables."""
    return DodoPayments(
        bearer_token=os.environ.get("DODO_PAYMENTS_API_KEY", ""),
        environment=os.environ.get("DODO_PAYMENTS_ENVIRONMENT", "test_mode"),
    )


# Module-level client used by `create_escrow_checkout`. Tests may patch this.
client = create_client()

# Product used for escrow line items. Override via env if the dashboard
# product id differs from the default.
DODO_PRODUCT_ID = os.getenv("DODO_PRODUCT_ID", "pdt_buildguard_escrow")

# Note: the SDK's checkout-session endpoint names this kwarg `billing_address`
# (there is no `billing` parameter on `checkout_sessions.create`).
_ESCROW_BILLING_ADDRESS = {
    "country": "US",
    "city": "Austin",
    "state": "TX",
    "street": "100 Construction Way",
    "zipcode": "78701",
}

_ESCROW_RETURN_URL = "http://localhost:8000/docs#/Escrow/deposit_success"


def create_escrow_checkout(data: MilestoneEscrowRequest) -> dict:
    """Create a Dodo Payments checkout session for a milestone escrow deposit.

    Returns ``{"checkout_url": ..., "session_id": ...}``.
    """
    session = client.checkout_sessions.create(
        # `amount` is the line-item price in cents. Each line binds the escrow
        # to the BuildGuard escrow product and records the contracted amount.
        product_cart=[
            {
                "product_id": DODO_PRODUCT_ID,
                "amount": int(data.amount_usd * 100),
                "quantity": 1,
            }
        ],
        billing_currency="USD",
        billing_address=_ESCROW_BILLING_ADDRESS,
        customer={
            "name": data.client_name,
            "email": data.client_email,
        },
        metadata={
            "project_id": data.project_id,
            "milestone_id": data.milestone_id,
            "type": "escrow_deposit",
        },
        return_url=_ESCROW_RETURN_URL,
    )
    # The checkout-session response exposes the hosted checkout URL as
    # `checkout_url`; `payment_link` is accepted for compatibility with the
    # spec's response mapping when a client surfaces it.
    checkout_url = getattr(session, "payment_link", None) or session.checkout_url
    return {
        "checkout_url": checkout_url,
        "session_id": session.session_id,
    }