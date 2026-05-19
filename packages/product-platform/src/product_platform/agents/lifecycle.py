"""Product lifecycle transition adapter for agent registration."""

from __future__ import annotations


class AgentLifecycleTransitionError(ValueError):
    """Raised when an agent lifecycle transition is invalid."""


AGENT_LIFECYCLE_STATES = frozenset(
    {
        "draft",
        "pending_approval",
        "provisioned",
        "active",
        "restricted",
        "quarantined",
        "suspended",
        "revoked",
        "decommissioning",
        "decommissioned",
        "archived",
        "orphaned",
        "rejected",
    }
)
AGENT_OPERATIONAL_STATUSES = frozenset({"active"})
AGENT_NON_OPERATIONAL_REASON_CODES = {
    "restricted": "agent_restricted",
    "quarantined": "agent_quarantined",
    "suspended": "agent_inactive",
    "revoked": "agent_revoked",
    "decommissioning": "agent_decommissioning",
    "decommissioned": "agent_decommissioned",
    "archived": "agent_archived",
    "orphaned": "agent_orphaned",
    "rejected": "agent_rejected",
}


def is_agent_operational(status: str) -> bool:
    """Return whether an agent may use runtime/tool/mesh/plugin boundaries."""

    return status in AGENT_OPERATIONAL_STATUSES


def agent_non_operational_reason_code(status: str) -> str:
    """Return a stable reason code for blocking a non-operational agent."""

    return AGENT_NON_OPERATIONAL_REASON_CODES.get(status, "agent_inactive")


def agent_non_operational_message(status: str) -> str:
    """Return a safe operator-facing lifecycle block message."""

    normalized = status.replace("_", " ")
    return f"Agent status {normalized} is not allowed for this operation."


class AgentLifecycleAdapter:
    """Validate product agent lifecycle transitions."""

    valid_transitions: dict[str, set[str]] = {
        "draft": {"pending_approval", "archived"},
        "pending_approval": {"provisioned", "rejected", "quarantined", "revoked", "archived"},
        "provisioned": {"active", "restricted", "quarantined", "revoked", "decommissioning"},
        "active": {
            "restricted",
            "quarantined",
            "suspended",
            "revoked",
            "decommissioning",
            "orphaned",
        },
        "restricted": {"active", "quarantined", "suspended", "revoked", "decommissioning"},
        "quarantined": {"restricted", "revoked", "decommissioning"},
        "suspended": {"active", "restricted", "quarantined", "revoked", "decommissioning"},
        "orphaned": {"active", "restricted", "quarantined", "revoked", "decommissioning"},
        "decommissioning": {"decommissioned", "revoked"},
        "rejected": {"archived"},
        "decommissioned": {"archived"},
        "revoked": {"archived"},
        "archived": set(),
    }

    def validate_transition(self, previous_status: str, next_status: str) -> None:
        """Raise if a transition is not allowed."""

        allowed = self.valid_transitions.get(previous_status, set())
        if next_status not in allowed:
            raise AgentLifecycleTransitionError(
                f"Invalid transition from {previous_status} to {next_status}."
            )
