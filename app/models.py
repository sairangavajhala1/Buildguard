"""Pydantic schemas for the Buildguard HITL override workflow."""

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