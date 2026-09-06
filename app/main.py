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


# ---------------------------------------------------------------------------
# Dodo escrow deposit (direct checkout)
# ---------------------------------------------------------------------------


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
        raise HTTPException(status_code=502, detail=f"Failed to create checkout session: {exc}") from exc


# ---------------------------------------------------------------------------
# Milestone escrow + audit workflow
# ---------------------------------------------------------------------------


def _slug(name: str) -> str:
    """Slugify a project name for use as a Dodo project id."""
    slug = "".join(c for c in name.upper() if c.isalnum() or c in " -_")[:24]
    return "-".join(slug.split())


@app.post("/api/milestone/create")
def create_milestone(payload: MilestoneCreateRequest):
    """Create a Dodo escrow checkout session for a milestone.

    Saves the milestone with status ``ESCROW_PENDING`` and returns the hosted
    checkout URL the contractor should fund.
    """
    project_id = payload.project_id or f"PRJ-{_slug(payload.project_name)}"
    milestone_id = state.next_id()
    escrow_request = MilestoneEscrowRequest(
        project_id=project_id,
        milestone_id=milestone_id,
        milestone_title=payload.milestone_title,
        amount_usd=payload.contracted_amount,
        client_name=payload.client_name,
        client_email=payload.client_email,
    )

    # Create the escrow checkout session via the Dodo Payments SDK.
    if os.getenv("DODO_PAYMENTS_API_KEY"):
        try:
            checkout = create_escrow_checkout(escrow_request)
            checkout_url = checkout["checkout_url"]
            session_id = checkout["session_id"]
        except Exception as exc:  # noqa: BLE001 - surface SDK/provider errors
            raise HTTPException(
                status_code=502, detail=f"Failed to create checkout session: {exc}"
            ) from exc
    else:
        # No API key configured: return a sandbox checkout link so the demo
        # dashboard still works end-to-end.
        checkout_url = (
            f"https://test.checkout.dodopayments.com/sandbox/{milestone_id}"
        )
        session_id = None

    milestone = state.create_milestone(
        milestone_id=milestone_id,
        project_name=payload.project_name,
        milestone_title=payload.milestone_title,
        contracted_amount=payload.contracted_amount,
        project_id=project_id,
        checkout_url=checkout_url,
        session_id=session_id,
    )
    return {
        "milestone_id": milestone["id"],
        "checkout_url": milestone["checkout_url"],
        "status": milestone["status"],
    }


@app.post("/api/milestone/audit")
def audit_milestone(payload: MilestoneAuditRequest):
    """Run the compliance audit on a submitted contractor bill.

    If the audit quarantines the payout the milestone transitions to
    ``QUARANTINED`` and the violations are recorded; otherwise it becomes
    ``ESCROW_FUNDED`` (escrow funded, awaiting settlement).
    """
    milestone = state.get_milestone(payload.milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Unknown milestone")

    audit_request = AuditRequest(
        milestone=MilestoneSpec(
            project_id=milestone["project_id"],
            milestone_id=milestone["id"],
            contracted_amount=milestone["contracted_amount"],
        ),
        bill=ContractorBill(
            billed_amount=payload.billed_amount,
            invoice_date=payload.invoice_date,
        ),
        safety=SafetyChecklist(
            inspection_passed=payload.safety_flag,
            inspector_notes=payload.inspector_notes,
        ),
        insurance=InsuranceCoverage(expiry_date=payload.insurance_date),
    )
    try:
        result = run_compliance_audit(audit_request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if result.quarantined:
        state.update_milestone(
            milestone["id"],
            status="QUARANTINED",
            billed_amount=payload.billed_amount,
            violations=list(result.quarantine_reasons),
        )
    else:
        state.update_milestone(
            milestone["id"],
            status="ESCROW_FUNDED",
            billed_amount=payload.billed_amount,
            violations=[],
        )

    updated = state.get_milestone(milestone["id"])
    return {
        "milestone_id": milestone["id"],
        "status": updated["status"],
        "quarantined": result.quarantined,
        "violations": updated["violations"],
        "variance_pct": result.variance_pct,
        "audit_log": [entry.model_dump() for entry in result.audit_log],
    }


@app.post("/api/milestone/cfo-approve")
def cfo_approve(payload: MilestoneApproveRequest):
    """CFO override: approve a flagged/held milestone and release the payout.

    Transitions the milestone to ``SETTLED``.
    """
    milestone = state.get_milestone(payload.milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Unknown milestone")
    if milestone["status"] == "SETTLED":
        raise HTTPException(status_code=409, detail="Milestone is already SETTLED")

    state.update_milestone(milestone["id"], status="SETTLED")
    updated = state.get_milestone(milestone["id"])
    return {
        "milestone_id": milestone["id"],
        "status": updated["status"],
        "violations": updated["violations"],
    }


@app.get("/api/milestones")
def list_active_milestones():
    """List all tracked milestones (live table data for the dashboard)."""
    return state.list_milestones()


# ---------------------------------------------------------------------------
# HITL override workflow (voice alerts via Smallest.ai)
# ---------------------------------------------------------------------------


@app.get("/hitl/violations", response_model=list[Violation])
def list_flagged_violations(status: ViolationStatus | None = None):
    """Inspect flagged violations (optionally filtered by status)."""
    return store.list_violations(status=status)


def build_resolution_message(
    violation: Violation,
    decision: OverrideDecision,
    notes: str,
) -> str:
    """Compose the spoken resolution text for the subcontractor call."""
    if decision == OverrideDecision.APPROVE:
        text = (
            f"This is Buildguard alerting {violation.subcontractor}. The flagged "
            f"violation {violation.id}, {violation.title}, has been reviewed and "
            "approved. No further action is required. Thank you for your cooperation."
        )
    else:
        text = (
            f"This is Buildguard alerting {violation.subcontractor}. The flagged "
            f"violation {violation.id}, {violation.title}, has been reviewed and is "
            "confirmed. Corrective action is required immediately. Please contact "
            "your project manager for the full resolution details."
        )
    if notes:
        text += f" Resolution notes: {notes}."
    return text


@app.post("/hitl/override", response_model=OverrideResponse)
def hitl_override(request: OverrideRequest):
    """Approve/reject a flagged violation and voice-call the subcontractor."""
    violation = store.get_violation(request.violation_id)
    if violation is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown violation {request.violation_id}"
        )
    if violation.status != ViolationStatus.FLAGGED:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Violation {request.violation_id} is already resolved "
                f"({violation.status.value})."
            ),
        )

    resolved_status = (
        ViolationStatus.APPROVED
        if request.decision == OverrideDecision.APPROVE
        else ViolationStatus.REJECTED
    )
    phone = request.subcontractor_phone or violation.subcontractor_phone
    message = build_resolution_message(violation, request.decision, request.resolution_notes)

    try:
        call = dispatch_voice_alert(
            phone_number=phone,
            message=message,
            violation_id=violation.id,
        )
    except VoiceDispatchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    store.set_status(violation.id, resolved_status)

    return OverrideResponse(
        violation_id=violation.id,
        decision=request.decision,
        resolved_status=resolved_status,
        call_status=call["provider_status"],
        audio_path=call["audio_path"],
        message=message,
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
def dashboard():
    """Serve the Tailwind dashboard at the site root."""
    return FileResponse(STATIC_DIR / "index.html")
