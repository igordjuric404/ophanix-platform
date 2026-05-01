"""Product lifecycle transition adapter for agent registration."""

from __future__ import annotations


class AgentLifecycleTransitionError(ValueError):
    """Raised when an agent lifecycle transition is invalid."""


class AgentLifecycleAdapter:
    """Validate product agent lifecycle transitions."""

    valid_transitions: dict[str, set[str]] = {
        "draft": {"pending_approval"},
        "pending_approval": {"provisioned", "rejected"},
        "provisioned": {"active", "decommissioning"},
        "active": {"suspended", "decommissioning", "orphaned"},
        "suspended": {"active", "decommissioning"},
        "orphaned": {"active", "decommissioning"},
        "decommissioning": {"decommissioned"},
        "rejected": set(),
        "decommissioned": set(),
    }

    def validate_transition(self, previous_status: str, next_status: str) -> None:
        """Raise if a transition is not allowed."""

        allowed = self.valid_transitions.get(previous_status, set())
        if next_status not in allowed:
            raise AgentLifecycleTransitionError(
                f"Invalid transition from {previous_status} to {next_status}."
            )
