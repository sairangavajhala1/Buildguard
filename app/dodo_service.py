"""Dodo Payments escrow integration service.

Creates Dodo Payments checkout sessions that collect milestone escrow
deposits. The client is configured from environment variables (loaded from a
local ``.env`` file when present):

- ``DODO_PAYMENTS_API_KEY``: required; the Dodo Payments API key.
- ``DODO_PAYMENTS_ENVIRONMENT``: optional; ``"test_mode"`` (default) or
  ``"live_mode"``.
- ``DODO_PRODUCT_ID``: optional; the Dodo product used for escrow lines. When
  absent, an existing product is reused or a default one is created.
"""

import os
import warnings

deposits using the verified product ID and test API key.
"""

import os
from dotenv import load_dotenv
from dodopayments import DodoPayments
from pydantic import BaseModel, Field

load_dotenv()

# Load variables from .env if present
load_dotenv()

# Hardcoded defaults so your service works immediately without .env setup
DODO_DEFAULT_API_KEY = "Fze8wR3G2OPzud8X.JD07fn9VQmVouNNAno4bWs_j0v-DJF8l_pfq5M_IXscfDDhL"
DODO_DEFAULT_PRODUCT_ID = "pdt_0Nn0pIJG6kScrGnKjZWEk"


class MilestoneEscrowRequest(BaseModel):
    """Request payload for creating an escrow checkout session."""

    project_id: str = ""
    milestone_id: str = ""
    milestone_title: str
    amount_usd: float = Field(gt=0)
    client_name: str = ""
    client_email: str


def create_client() -> DodoPayments:
    """Build the Dodo Payments SDK client from environment variables.

    Warns (rather than failing) when the API key is missing or does not look
    like a Dodo key, so misconfigured credentials surface early instead of as
    a bare HTTP 401 from the API.
    """
    api_key = os.environ.get("DODO_PAYMENTS_API_KEY", "")
    if not api_key:
        warnings.warn(
            "DODO_PAYMENTS_API_KEY is not set; Dodo API calls will fail.",
            stacklevel=2,
        )
    elif not api_key.startswith("dodo_"):
        warnings.warn(
            "DODO_PAYMENTS_API_KEY does not look like a Dodo Payments key "
            "(Dodo test keys start with 'dodo_test_', live keys with "
            "'dodo_live_').",
            stacklevel=2,
        )
    return DodoPayments(
        bearer_token=api_key,
        environment=os.environ.get("DODO_PAYMENTS_ENVIRONMENT", "test_mode"),
    """Build the Dodo Payments SDK client using environment variables or hardcoded test credentials."""
    token = os.environ.get("DODO_PAYMENTS_API_KEY", "").strip() or DODO_DEFAULT_API_KEY
    env = os.environ.get("DODO_PAYMENTS_ENVIRONMENT", "test_mode")
    return DodoPayments(
        bearer_token=token,
        environment=env,
    )


# Module-level client used by create_escrow_checkout
client = create_client()


def _resolve_product_id(dodo_client) -> str:
    """Resolve the product id used for escrow cart line items.

    Precedence:
    1. The ``DODO_PRODUCT_ID`` env var, if set and non-empty.
    2. The first existing product returned by ``client.products.list()``.
    3. A freshly created default product ("Milestone Escrow").

    Returns the resolved ``product_id`` string.
    """
    env_id = os.getenv("DODO_PRODUCT_ID")
    if env_id and env_id.strip():
        return env_id.strip()

    products_page = dodo_client.products.list()
    for product in getattr(products_page, "items", []) or []:
        return product.product_id

    created = dodo_client.products.create(
        name="Milestone Escrow",
        # Native SDK price shape: one-time price in USD cents ($100.00 = 10000).
        # The SDK's `products.create` has no top-level `currency`/`type`
        # kwargs; they live inside the `price` parameter.
        price={
            "type": "one_time_price",
            "currency": "USD",
            "price": 10000,
            "discount": 0,
        },
        tax_category="digital_products",
    )
    return created.product_id


# Note: the SDK's checkout-session endpoint names this kwarg `billing_address`
# (there is no `billing` parameter on `checkout_sessions.create`).
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
    prod_id = _resolve_product_id(client)
    session = client.checkout_sessions.create(
        # `amount` is the line-item price in cents. Each line binds the escrow
        # to a real product id (env var, existing product, or default) and
        # records the contracted amount.
        product_cart=[
            {
                "product_id": prod_id,
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