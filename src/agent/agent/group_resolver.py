"""Group-to-department resolver — simulated Graph API placeholder.

Maps Entra security group GUIDs to department names.  This implementation
is intentionally simple: any non-empty input returns ``["engineering"]``.
Replace with real Microsoft Graph API calls in a future epic.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def resolve_departments(group_guids: list[str]) -> list[str]:
    """Resolve Entra group GUIDs to department names.

    Parameters
    ----------
    group_guids:
        List of Entra security group GUIDs from the JWT ``groups`` claim.

    Returns
    -------
    list[str]
        Department names.  Returns ``["engineering"]`` for any non-empty
        input (simulated).  Returns ``[]`` for empty input.
    """
    if not group_guids:
        return []

    # Simulated resolution — replace with Graph API in a future epic
    departments = ["engineering"]
    logger.debug(
        "Resolved %d group(s) → departments=%s (simulated)",
        len(group_guids),
        departments,
    )
    return departments
