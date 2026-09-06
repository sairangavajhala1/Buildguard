"""In-memory milestone state for the BuildGuard dashboard.

Stores milestones in a dictionary keyed by milestone id::

    milestones[id] = {
        "project_name": str,
        "milestone_title": str,
        "contracted_amount": float,
        "billed_amount": float,
        "status": "ESCROW_PENDING" | "ESCROW_FUNDED" | "QUARANTINED" | "SETTLED",
        "violations": list[str],
    }

Plus escrow metadata (project_id, checkout_url, session_id) needed to link a
milestone back to its Dodo Payments checkout session. A lightweight stand-in
for a persistent datastore.
"""

import itertools
import threading
from typing import Optional

STATUSES = ("ESCROW_PENDING", "ESCROW_FUNDED", "QUARANTINED", "SETTLED")

_milestones: dict[str, dict] = {}
_ids = itertools.count(1)
_lock = threading.Lock()


def next_id() -> str:
    """Reserve and return the next milestone id (does not store anything)."""
    return f"MS-{next(_ids):04d}"


def create_milestone(
    *,
    milestone_id: str | None = None,
    project_name: str,
    milestone_title: str,
    contracted_amount: float,
    project_id: str,
    checkout_url: str,
    session_id: Optional[str] = None,
) -> dict:
    """Create a new milestone in ESCROW_PENDING and return the stored record."""
    milestone_id = milestone_id or next_id()
    record = {
        "id": milestone_id,
        "project_name": project_name,
        "milestone_title": milestone_title,
        "contracted_amount": contracted_amount,
        "billed_amount": 0.0,
        "status": "ESCROW_PENDING",
        "violations": [],
        # Escrow metadata
        "project_id": project_id,
        "checkout_url": checkout_url,
        "session_id": session_id,
    }
    with _lock:
        _milestones[milestone_id] = record
    return record


def get_milestone(milestone_id: str) -> Optional[dict]:
    return _milestones.get(milestone_id)


def list_milestones() -> list[dict]:
    return list(_milestones.values())


def update_milestone(milestone_id: str, **fields) -> Optional[dict]:
    """Apply field updates (status, violations, ...) to a milestone."""
    milestone = _milestones.get(milestone_id)
    if milestone is None:
        return None
    milestone.update(fields)
    return milestone


def reset() -> None:
    """Clear all milestones (used by tests)."""
    global _ids
    with _lock:
        _milestones.clear()
        _ids = itertools.count(1)