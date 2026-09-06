"""Dodo Payments escrow integration service.

Creates Dodo Payments checkout sessions that collect milestone escrow
deposits using the verified product ID and test API key.
"""

import os
from dotenv import load_dotenv
from dodopayments import DodoPayments
from pydantic import BaseModel, Field

# Load variables from .env if present
load_dotenv()

# Hardcoded defaults so your service works immediately without .env setup
DODO_DEFAULT_API_KEY = "Fze8wR3G2OPzud8X.JD07fn9VQmVouNNAno4bWs_j0v-DJF8l_pfq5M_IXscfDDhL"
DODO_DEFAULT_PRODUCT_ID = "pdt_0Nn0pIJG6kScrGnKjZWEk"


class MilestoneEscrowRequest(BaseModel):
    """Request payload for creating an escrow checkout session."""

    project_id: str
    milestone_id: str
    milestone_title: str
    amount_usd: float = Field(gt=0)
    client_name: str
    client_email: str


def create_client() -> DodoPayments:
    """Build the Dodo Payments SDK client using environment variables or hardcoded test credentials."""
    token = os.environ.get("DODO_PAYMENTS_API_KEY", "").strip() or DODO_DEFAULT_API_KEY
    env = os.environ.get("DODO_PAYMENTS_ENVIRONMENT", "test_mode")
    return DodoPayments(
        bearer_token=token,
        environment=env,
    )


# Module-level client used by create_escrow_checkout
client = create_client()

_ESCROW_BILLING_ADDRESS = {
    "country": "US",
    "city": "Austin",
    "state": "TX",
    "street": "100 Construction Way",
    "zipcode": "78701",
}

_ESCROW_RETURN_URL = "http://localhost:8000/?status=funded"


def create_escrow_checkout(data: MilestoneEscrowRequest) -> dict:
    """Create a Dodo Payments checkout session for a milestone escrow deposit.

    Returns {"checkout_url": ..., "session_id": ...}.
    """
    product_id = os.environ.get("DODO_PRODUCT_ID", "").strip() or DODO_DEFAULT_PRODUCT_ID

    session = client.checkout_sessions.create(
        product_cart=[
            {
                "product_id": product_id,
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

    checkout_url = getattr(session, "payment_link", None) or getattr(session, "checkout_url", None)
    session_id = getattr(session, "session_id", None) or "sess_created"

    return {
        "checkout_url": checkout_url,
        "session_id": session_id,
    }