"""Contractor invoice compliance audit rules for BuildGuard.

`run_compliance_audit` evaluates an invoice against the contracted amount and
the contractor's compliance paperwork. Any violation quarantines the milestone
until a CFO override settles it.
"""

from datetime import date

VIOLATION_OVERBILL = "Billed amount exceeds contracted amount"
VIOLATION_INSURANCE = "Insurance policy expired"
VIOLATION_SAFETY = "Safety inspection not passed"


def run_compliance_audit(
    contracted_amount: float,
    billed_amount: float,
    invoice_date: date,
    insurance_expiry_date: date,
    safety_inspection_passed: bool,
) -> dict:
    """Run the compliance audit rules for a contractor invoice.

    Returns ``{"status", "violations", ...}`` where status is ``"APPROVED"``
    when no violations are found and ``"QUARANTINED"`` otherwise.
    """
    violations: list[str] = []

    if billed_amount > contracted_amount:
        violations.append(VIOLATION_OVERBILL)

    if insurance_expiry_date <= date.today():
        violations.append(VIOLATION_INSURANCE)

    if invoice_date > date.today():
        violations.append("Invoice is dated in the future")

    if not safety_inspection_passed:
        violations.append(VIOLATION_SAFETY)

    return {
        "status": "QUARANTINED" if violations else "APPROVED",
        "violations": violations,
        "contracted_amount": contracted_amount,
        "billed_amount": billed_amount,
        "invoice_date": invoice_date.isoformat(),
        "insurance_expiry_date": insurance_expiry_date.isoformat(),
        "safety_inspection_passed": safety_inspection_passed,
    }