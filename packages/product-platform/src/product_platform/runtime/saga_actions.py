"""Supported saga action registry."""

from __future__ import annotations


SUPPORTED_SAGA_ACTIONS = frozenset(
    {
        "claims.lookup_order",
        "claims.issue_refund",
        "claims.reverse_refund",
        "claims.release_lookup_hold",
        "notifications.send_email",
        "notifications.retract_email",
    }
)


def validate_saga_action_name(action_name: str | None, *, field_name: str) -> None:
    """Raise when a saga action is not known to the runtime action registry."""

    if action_name is None:
        return
    if action_name not in SUPPORTED_SAGA_ACTIONS:
        supported = ", ".join(sorted(SUPPORTED_SAGA_ACTIONS))
        raise ValueError(f"{field_name} must be one of the supported saga actions: {supported}.")
