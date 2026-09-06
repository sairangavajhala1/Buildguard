"""BuildGuard escrow backend — FastAPI application.

Serves the CFO dashboard (``static/index.html``) and the escrow/compliance
API backed by the in-memory milestone store.
"""

import secrets
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.compliance import run_compliance_audit
from app.dodo_service import MilestoneEscrowRequest, create_escrow_checkout
from app.state import add_milestone, get_milestone, list_milestones, update_milestone

app = FastAPI(
    title="BuildGuard Escrow API",
    description="Autonomous Office of the CFO — escrow deposits and compliance audits.",
    version="0.1.0",
)

# Static assets (dashboard) served under /static; the root route serves it.
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Serve the CFO dashboard."""
    return FileResponse("static/index.html")


class AuditRequest(BaseModel):
    """Payload for a contractor invoice compliance audit."""

    milestone_id: str
    billed_amount: float = Field(gt=0, description="Amount billed by the contractor, USD")
    invoice_date: date
    insurance_expiry_date: date
    safety_inspection_passed: bool


@app.post("/api/escrow/deposit", summary="Create escrow deposit checkout")
def escrow_deposit(data: MilestoneEscrowRequest):
    """Create a Dodo checkout session and record the milestone as escrow-pending.

    When ``project_id``/``milestone_id`` are omitted, they are generated here.
    """
    project_id = data.project_id or f"proj_{secrets.token_hex(4)}"
    milestone_id = data.milestone_id or f"ms_{secrets.token_hex(6)}"
    data = data.model_copy(
        update={"project_id": project_id, "milestone_id": milestone_id}
    )

    try:
        checkout = create_escrow_checkout(data)
    except Exception as exc:  # noqa: BLE001 - surface SDK/provider errors
        raise HTTPException(
            status_code=502, detail=f"Failed to create checkout session: {exc}"
        ) from exc

    add_milestone(
        {
            "project_id": project_id,
            "milestone_id": milestone_id,
            "milestone_title": data.milestone_title,
            "contracted_amount": data.amount_usd,
            "billed_amount": None,
            "escrow_status": "ESCROW_PENDING",
            "audit_status": "NOT_SUBMITTED",
            "violations": [],
            "checkout_url": checkout["checkout_url"],
        }
    )
    return {
        "checkout_url": checkout["checkout_url"],
        "session_id": checkout["session_id"],
        "milestone_id": milestone_id,
    }


@app.post("/api/escrow/mock-confirm/{milestone_id}", summary="Simulate payment success")
def mock_escrow_confirm(milestone_id: str):
    """Simulate a Dodo webhook: lock the escrow for a milestone."""
    milestone = get_milestone(milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    update_milestone(milestone_id, escrow_status="ESCROW_LOCKED")
    return {"milestone_id": milestone_id, "escrow_status": "ESCROW_LOCKED"}


@app.post("/api/milestone/audit", summary="Submit contractor invoice for audit")
def milestone_audit(req: AuditRequest):
    """Run compliance rules on an invoice; quarantine or approve the milestone."""
    milestone = get_milestone(req.milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")

    result = run_compliance_audit(
        contracted_amount=milestone["contracted_amount"],
        billed_amount=req.billed_amount,
        invoice_date=req.invoice_date,
        insurance_expiry_date=req.insurance_expiry_date,
        safety_inspection_passed=req.safety_inspection_passed,
    )

    update_milestone(
        req.milestone_id,
        audit_status=result["status"],
        violations=result["violations"],
        billed_amount=req.billed_amount,
    )
    return {"milestone_id": req.milestone_id, **result}


@app.post("/api/milestone/cfo-approve/{milestone_id}", summary="CFO override: release escrow")
def cfo_approve(milestone_id: str):
    """Human-in-the-loop override: settle the milestone and clear violations."""
    milestone = get_milestone(milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    update_milestone(milestone_id, audit_status="SETTLED", violations=[])
    return {
        "milestone_id": milestone_id,
        "audit_status": "SETTLED",
        "escrow_status": milestone["escrow_status"],
    }


@app.get("/api/milestones", summary="List all milestones")
def milestones():
    """Return all milestones for dashboard rendering."""
    return {"milestones": list_milestones()}