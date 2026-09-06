"""Buildguard HITL override API.

Allows a CFO (or authorized reviewer) to inspect flagged violations, approve
or reject them, and trigger an automated voice call to the subcontractor
stating the final resolution.
"""

from fastapi import FastAPI, HTTPException

from app import store
from app.models import (
    OverrideDecision,
    OverrideRequest,
    OverrideResponse,
    Violation,
    ViolationStatus,
)
from app.voice_service import VoiceDispatchError, dispatch_voice_alert

app = FastAPI(
    title="Buildguard HITL",
    description="Human-in-the-loop override workflow for flagged violations.",
    version="0.1.0",
)


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