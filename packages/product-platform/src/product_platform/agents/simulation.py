"""Registration draft policy simulation helpers."""

from __future__ import annotations

from product_platform.agents.models import AgentRegistrationSimulationResponse


def simulate_registration_action(
    *,
    agent_id: str,
    capability_names: list[str],
    policy_ids: list[str],
) -> AgentRegistrationSimulationResponse:
    """Evaluate the first requested capability against selected policies."""

    if not capability_names:
        return AgentRegistrationSimulationResponse(
            agent_id=agent_id,
            decision="deny",
            action=None,
            matched_policy_ids=policy_ids,
            reason="No requested capabilities are available to simulate.",
        )
    action = capability_names[0]
    risky_action = any(token in action for token in ["admin", "delete", "write:all", "exec"])
    if not policy_ids:
        return AgentRegistrationSimulationResponse(
            agent_id=agent_id,
            decision="review",
            action=action,
            matched_policy_ids=[],
            reason="No policy selection is attached to the draft.",
        )
    if risky_action and not any("sensitive" in policy_id for policy_id in policy_ids):
        return AgentRegistrationSimulationResponse(
            agent_id=agent_id,
            decision="deny",
            action=action,
            matched_policy_ids=policy_ids,
            reason="Risky capability requires a sensitive-tools policy selection.",
        )
    return AgentRegistrationSimulationResponse(
        agent_id=agent_id,
        decision="allow",
        action=action,
        matched_policy_ids=policy_ids,
        reason="First requested capability is allowed by the selected registration policies.",
    )
