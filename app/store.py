"""In-memory store of flagged violations.

A lightweight stand-in for a persistent violations datastore so the HITL
override workflow can be exercised end-to-end. Swap this module for a real
database-backed repository when one is introduced.
"""

from datetime import datetime, timezone

from app.models import Violation, ViolationStatus

_SEED: dict[str, Violation] = {
    "V-1001": Violation(
        id="V-1001",
        title="Missing fall-arrest anchors on level 3 scaffold",
        description="Scaffold erected without certified fall-arrest anchor points; "
        "exposed workers above 6 ft.",
        subcontractor="TruBuild Framing LLC",
        subcontractor_phone="+1555010010",
        severity="critical",
        flagged_at=datetime(2026, 9, 5, 9, 12, tzinfo=timezone.utc),
    ),
    "V-1002": Violation(
        id="V-1002",
        title="Unlabeled electrical panel near wet area",
        description="Temporary panel feeding floor pumps lacks signage and GFCI "
        "verification record.",
        subcontractor="Volta Electric Co.",
        subcontractor_phone="+1555010020",
        severity="high",
        flagged_at=datetime(2026, 9, 5, 14, 3, tzinfo=timezone.utc),
    ),
    "V-1003": Violation(
        id="V-1003",
        title="Material hoarding outside designated laydown zone",
        description="Steel bundles stacked within 4 ft of the public sidewalk "
        "without barrier protection.",
        subcontractor="Meridian Steelworks",
        subcontractor_phone="+1555010030",
        severity="medium",
        flagged_at=datetime(2026, 9, 6, 7, 45, tzinfo=timezone.utc),
    ),
}


def list_violations(status: ViolationStatus | None = None) -> list[Violation]:
    """Return flagged violations, optionally filtered by status."""
    items = list(_VIOLATIONS.values())
    if status is not None:
        items = [v for v in items if v.status == status]
    return sorted(items, key=lambda v: v.id)


def get_violation(violation_id: str) -> Violation | None:
    return _VIOLATIONS.get(violation_id)


def set_status(violation_id: str, status: ViolationStatus) -> Violation:
    violation = _VIOLATIONS[violation_id]
    _VIOLATIONS[violation_id] = violation.model_copy(update={"status": status})
    return _VIOLATIONS[violation_id]


_VIOLATIONS: dict[str, Violation] = {}


def reset() -> None:
    """Restore the store to its pristine seeded state (used by tests)."""
    _VIOLATIONS.clear()
    _VIOLATIONS.update({vid: v.model_copy() for vid, v in _SEED.items()})


reset()