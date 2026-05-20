"""Supported saga action registry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SagaActionDefinition:
    """Typed saga action contract used for retry and idempotency validation."""

    name: str
    supports_idempotency: bool = True
    side_effecting: bool = True


SAGA_ACTION_DEFINITIONS: dict[str, SagaActionDefinition] = {
    name: SagaActionDefinition(name=name)
    for name in {
        "claims.lookup_order",
        "claims.issue_refund",
        "claims.reverse_refund",
        "claims.release_lookup_hold",
        "notifications.send_email",
        "notifications.retract_email",
    }
}

SUPPORTED_SAGA_ACTIONS = frozenset(SAGA_ACTION_DEFINITIONS)


def validate_saga_action_name(action_name: str | None, *, field_name: str) -> None:
    """Raise when a saga action is not known to the runtime action registry."""

    if action_name is None:
        return
    if action_name not in SAGA_ACTION_DEFINITIONS:
        supported = ", ".join(sorted(SAGA_ACTION_DEFINITIONS))
        raise ValueError(f"{field_name} must be one of the supported saga actions: {supported}.")


def saga_action_supports_idempotency(action_name: str) -> bool:
    """Return whether an action contract supports idempotent external retries."""

    definition = SAGA_ACTION_DEFINITIONS.get(action_name)
    return bool(definition and definition.supports_idempotency)
