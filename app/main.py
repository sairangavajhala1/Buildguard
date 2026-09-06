"""Buildguard escrow backend — FastAPI application."""

from fastapi import FastAPI, HTTPException

from app.dodo_service import MilestoneEscrowRequest, create_escrow_checkout

app = FastAPI(
    title="Buildguard Escrow API",
    description="Dodo Payments escrow deposit endpoints.",
    version="0.1.0",
)


@app.post("/api/escrow/deposit", summary="Create escrow deposit checkout")
def deposit_success(data: MilestoneEscrowRequest):
    """Create a checkout session collecting a milestone escrow deposit.

    Returns the hosted checkout URL the client should redirect to.
    """
    try:
        return create_escrow_checkout(data)
    except Exception as exc:  # noqa: BLE001 - surface SDK/provider errors
        raise HTTPException(status_code=502, detail=f"Failed to create checkout session: {exc}") from exc