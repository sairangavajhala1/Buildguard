"""CFO compliance auditor for construction milestone payouts.

Performs a multi-factor audit of a milestone payout request combining:

1. Contract milestone specifications (contracted amount).
2. Contractor bill (billed amount + invoice date).
3. Safety inspector checklist (municipal/site safety sign-off).
4. General liability insurance coverage (policy expiry date).

Two conditions are **hard exceptions** — either one quarantines the payout
immediately regardless of the other factors:

* Price variance: the billed amount exceeds the contracted amount by more
  than 5% of the contracted amount.
* Insurance lapse: the general-liability insurance expired before
  (prior to) the bill/invoice date.

The result is a structured decision dictionary (an :class:`AuditResult`
model; use ``result.model_dump()`` for the plain dict form) containing
``status``, ``quarantine_reasons`` and a timestamped ``audit_log``.
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

DATE_FORMAT = "%Y-%m-%d"
PRICE_VARIANCE_LIMIT = 0.05  # hard exception: > 5% over the contracted amount


def _parse_date(value: str, field_name: str) -> datetime:
    """Parse a ``YYYY-MM-DD`` date string, raising ValueError on bad input."""
    try:
        return datetime.strptime(value, DATE_FORMAT)
    except (TypeError, ValueError):
        raise ValueError(
            f"{field_name} must be a valid date in YYYY-MM-DD format, got {value!r}"
        )


# ---------------------------------------------------------------------------
# Input factors
# ---------------------------------------------------------------------------


class MilestoneSpec(BaseModel):
    """(1) Contract milestone specifications from the signed agreement."""

    project_id: str
    milestone_id: str
    contracted_amount: float = Field(
        ..., gt=0, description="Agreed contract amount for this milestone"
    )


class ContractorBill(BaseModel):
    """(2) Contractor-submitted bill for the milestone."""

    billed_amount: float = Field(..., ge=0, description="Amount claimed on the invoice")
    invoice_date: str = Field(..., description="Invoice date, YYYY-MM-DD")


class SafetyChecklist(BaseModel):
    """(3) Safety inspector checklist result for the site/milestone."""

    inspection_passed: bool = Field(
        ..., description="Municipal/site safety sign-off obtained"
    )
    inspector_notes: Optional[str] = Field(
        default=None, description="Notes from the safety inspector"
    )


class InsuranceCoverage(BaseModel):
    """(4) General liability insurance coverage certificate."""

    policy_number: Optional[str] = Field(default=None, description="Policy reference")
    expiry_date: str = Field(..., description="Policy expiry date, YYYY-MM-DD")


class AuditRequest(BaseModel):
    """Bundled inputs for the multi-factor compliance audit."""

    milestone: MilestoneSpec
    bill: ContractorBill
    safety: SafetyChecklist
    insurance: InsuranceCoverage


# ---------------------------------------------------------------------------
# Output structures
# ---------------------------------------------------------------------------


class AuditEntry(BaseModel):
    """A single line in the timestamped audit log."""

    check: str
    passed: bool
    detail: str
    timestamp: str


class AuditResult(BaseModel):
    """Structured decision output of the compliance audit.

    The fields ``status``, ``quarantine_reasons`` and ``audit_log`` form the
    decision dictionary; call ``model_dump()`` for the plain dict form.
    """

    status: str  # "approved" | "quarantined"
    approved_for_payout: bool
    quarantined: bool
    variance_pct: float
    quarantine_reasons: List[str] = Field(default_factory=list)
    audit_log: List[AuditEntry] = Field(default_factory=list)
    audit_notes: str = ""


# ---------------------------------------------------------------------------
# Auditor
# ---------------------------------------------------------------------------


def run_compliance_audit(req: AuditRequest) -> AuditResult:
    """Run the multi-factor CFO compliance audit for a milestone payout.

    Factors considered:

    * Price variance between ``req.bill.billed_amount`` and the contracted
      ``req.milestone.contracted_amount`` (hard exception above 5%).
    * Safety inspector sign-off from ``req.safety``.
    * General-liability insurance expiry vs. the bill date (hard exception
      when the policy expired before the invoice date).

    Returns an :class:`AuditResult` — a structured decision dictionary with
    ``status``, ``quarantine_reasons`` and a timestamped ``audit_log``.

    Raises:
        ValueError: if an input date is not in ``YYYY-MM-DD`` format.
    """
    now = datetime.now(timezone.utc)
    invoice_dt = _parse_date(req.bill.invoice_date, "invoice_date")
    insurance_dt = _parse_date(req.insurance.expiry_date, "insurance.expiry_date")

    contracted = req.milestone.contracted_amount
    billed = req.bill.billed_amount

    violations: List[str] = []
    audit_log: List[AuditEntry] = []

    # 1. Price variance vs. the contracted milestone amount (hard exception).
    variance = (billed - contracted) / contracted
    variance_pct = round(variance * 100, 2)
    over_limit = variance > PRICE_VARIANCE_LIMIT
    if over_limit:
        violations.append(
            f"Billing exceeds agreed contract by {variance_pct:.1f}% "
            f"(> {PRICE_VARIANCE_LIMIT * 100:.0f}% hard exception)"
        )
    audit_log.append(
        AuditEntry(
            check="price_variance",
            passed=not over_limit,
            detail=(
                f"contracted={contracted:.2f}, billed={billed:.2f}, "
                f"variance={variance_pct:+.2f}% (hard limit +{PRICE_VARIANCE_LIMIT * 100:.0f}%)"
            ),
            timestamp=now.isoformat(),
        )
    )

    # 2. Safety inspector checklist.
    safety_ok = req.safety.inspection_passed
    if not safety_ok:
        violations.append("Missing mandatory municipal/site safety sign-off")
    audit_log.append(
        AuditEntry(
            check="safety_inspection",
            passed=safety_ok,
            detail=(
                "Safety sign-off obtained"
                if safety_ok
                else "Safety sign-off missing (inspector notes: "
                f"{req.safety.inspector_notes or 'n/a'})"
            ),
            timestamp=now.isoformat(),
        )
    )

    # 3. General liability insurance expiry vs. bill date (hard exception).
    insurance_ok = insurance_dt >= invoice_dt
    if not insurance_ok:
        violations.append(
            f"General Liability Insurance expired on {req.insurance.expiry_date} "
            f"prior to invoice date {req.bill.invoice_date}"
        )
    audit_log.append(
        AuditEntry(
            check="insurance_coverage",
            passed=insurance_ok,
            detail=(
                f"policy expiry={req.insurance.expiry_date}, "
                f"invoice date={req.bill.invoice_date}"
            ),
            timestamp=now.isoformat(),
        )
    )

    quarantined = len(violations) > 0
    return AuditResult(
        status="quarantined" if quarantined else "approved",
        approved_for_payout=not quarantined,
        quarantined=quarantined,
        variance_pct=variance_pct,
        quarantine_reasons=violations,
        audit_log=audit_log,
        audit_notes=(
            "Audit flagged risks requiring CFO override"
            if quarantined
            else "Passed all compliance criteria"
        ),
    )