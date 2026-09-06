"""Pydantic schemas for the Buildguard HITL override and milestone workflows."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ViolationStatus(str, Enum):
    FLAGGED = "flagged"
    APPROVED = "approved"
    REJECTED = "rejected"


class OverrideDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class Violation(BaseModel):
    id: str
    title: str
    description: str
    subcontractor: str
    subcontractor_phone: str
    severity: str = "high"
    status: ViolationStatus = ViolationStatus.FLAGGED
    flagged_at: datetime


class OverrideRequest(BaseModel):
    violation_id: str
    decision: OverrideDecision
    resolution_notes: str = Field(default="", max_length=500)
    # Optional override phone; falls back to the subcontractor's stored number.
    subcontractor_phone: str | None = None


class OverrideResponse(BaseModel):
    violation_id: str
    decision: OverrideDecision
    resolved_status: ViolationStatus
    call_status: str
    audio_path: str
    message: str


# ---------------------------------------------------------------------------
# Milestone escrow / audit workflow
# ---------------------------------------------------------------------------


class MilestoneCreateRequest(BaseModel):
    """Payload for creating a milestone escrow checkout session."""

    project_name: str
    milestone_title: str
    contracted_amount: float = Field(gt=0)
    client_name: str
    client_email: str
    project_id: str | None = None


class MilestoneAuditRequest(BaseModel):
    """Payload for running a compliance audit on a milestone payout.

    Mirrors the inputs of ``audit_engine.AuditRequest``:
    bill (invoice date + billed amount), insurance (expiry date) and the
    safety-inspector flag.
    """

    milestone_id: str
    invoice_date: str = Field(description="Invoice date, YYYY-MM-DD")
    billed_amount: float = Field(ge=0)
    insurance_date: str = Field(description="Policy expiry date, YYYY-MM-DD")
    safety_flag: bool
    inspector_notes: str | None = None


class MilestoneApproveRequest(BaseModel):
    """Payload for the CFO approve / release-payout action."""

    milestone_id: str