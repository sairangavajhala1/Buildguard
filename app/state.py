"""Centralized in-memory state store for BuildGuard milestones.

A milestone record looks like::

    {
        "project_id": str,
        "milestone_id": str,
        "milestone_title": str,
        "contracted_amount": float,
        "billed_amount": float | None,
        "escrow_status": "ESCROW_PENDING" | "ESCROW_LOCKED",
        "audit_status": "NOT_SUBMITTED" | "APPROVED" | "QUARANTINED" | "SETTLED",
        "violations": list[str],
        "checkout_url": str,
    }

This is a demo store: swap it for a persistent database in production.
"""

milestones: dict = {}


def add_milestone(milestone: dict) -> dict:
    """Store a new milestone keyed by ``milestone_id``."""
    milestones[milestone["milestone_id"]] = milestone
    return milestone


def get_milestone(milestone_id: str) -> dict | None:
    """Return the milestone with ``milestone_id`` or ``None``."""
    return milestones.get(milestone_id)


def update_milestone(milestone_id: str, **updates) -> dict | None:
    """Apply ``updates`` to a milestone in place and return it."""
    milestone = milestones.get(milestone_id)
    if milestone is None:
        return None
    milestone.update(updates)
    return milestone


def list_milestones() -> list[dict]:
    """Return all milestones (insertion order)."""
    return list(milestones.values())