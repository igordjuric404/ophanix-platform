from __future__ import annotations

import unittest

from pydantic import ValidationError

from product_platform.audit.events import (
    AuditEventEnvelope,
    agent_lifecycle_event,
    mcp_call_event,
    policy_decision_event,
    runtime_action_event,
    trust_change_event,
    workflow_run_event,
)


class AuditPhase1Tests(unittest.TestCase):
    def test_valid_event_envelope(self) -> None:
        event = AuditEventEnvelope(
            organization_id="org_default",
            environment_id="env_default",
            event_type="test.event",
            source_component="tests",
            actor_type="system",
            payload_json={"ok": True},
        )

        self.assertTrue(event.id.startswith("evt_"))
        self.assertEqual(event.organization_id, "org_default")
        self.assertEqual(event.environment_id, "env_default")
        self.assertEqual(event.payload_json["ok"], True)

    def test_invalid_event_missing_organization_fails(self) -> None:
        with self.assertRaises(ValidationError):
            AuditEventEnvelope(
                organization_id="",
                environment_id="env_default",
                event_type="test.event",
                source_component="tests",
                actor_type="system",
            )

    def test_event_helpers_create_expected_types_and_payloads(self) -> None:
        common = {"organization_id": "org_default", "environment_id": "env_default"}
        events = [
            policy_decision_event(
                **common,
                actor_id="user_admin",
                policy_id="policy_1",
                decision="deny",
                matched_rule="block-delete",
                reason="Dangerous operation.",
            ),
            agent_lifecycle_event(
                **common,
                agent_id="agent_1",
                lifecycle_state="registered",
                actor_id="user_admin",
            ),
            trust_change_event(**common, agent_id="agent_1", trust_delta=-5, new_score=700),
            mcp_call_event(
                **common,
                agent_id="agent_1",
                server_id="server_1",
                tool_name="delete_file",
                decision="deny",
            ),
            runtime_action_event(
                **common,
                session_id="session_1",
                action="execute",
                ring="ring_2",
                decision="allow",
            ),
            workflow_run_event(
                **common,
                workflow_run_id="workflow_1",
                workflow_type="discovery_scan",
                status="queued",
            ),
        ]

        self.assertEqual(
            [event.event_type for event in events],
            [
                "policy.decision",
                "agent.lifecycle",
                "trust.change",
                "mcp.call",
                "runtime.action",
                "workflow.run",
            ],
        )
        self.assertEqual(events[0].payload_json["matched_rule"], "block-delete")
        self.assertEqual(events[2].trust_delta, -5)
        self.assertEqual(events[3].payload_json["tool_name"], "delete_file")
        self.assertTrue(all(event.organization_id == "org_default" for event in events))
        self.assertTrue(all(event.environment_id == "env_default" for event in events))


if __name__ == "__main__":
    unittest.main()

