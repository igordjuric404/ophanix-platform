"""Synchronous Demo Lab scenario runner."""

from __future__ import annotations

from typing import Any

from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventRepository
from product_platform.demo.models import DemoRunStatus, DemoScenarioStepResponse
from product_platform.demo.repository import DemoScenarioNotFoundError, DemoScenarioRepository, demo_step_response


class DemoStepExecutionError(RuntimeError):
    """Raised when a demo step action cannot complete."""


class DemoStepExecutor:
    """Dispatch demo scenario step action types to deterministic handlers."""

    def __init__(self, *, failure_action_types: set[str] | None = None) -> None:
        self.failure_action_types = failure_action_types or set()

    def execute(
        self,
        step: DemoScenarioStepResponse,
        *,
        run_id: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute one scenario step and return persisted result JSON."""

        if step.action_type in self.failure_action_types:
            raise DemoStepExecutionError(f"Configured demo failure for {step.action_type}.")
        handlers = {
            "register_agents": self._register_agents,
            "import_policies": self._import_policies,
            "register_mcp_server": self._register_mcp_server,
            "run_agent_prompt": self._run_agent_prompt,
            "request_approval": self._request_approval,
            "rotate_credential": self._rotate_credential,
            "run_discovery": self._run_discovery,
            "run_saga": self._run_saga,
            "generate_report": self._generate_report,
        }
        try:
            handler = handlers[step.action_type]
        except KeyError as exc:
            raise DemoStepExecutionError(f"Unsupported demo action type: {step.action_type}.") from exc
        result = handler(step, run_id=run_id)
        return {
            "ok": True,
            "action_type": step.action_type,
            "actual_result": result["actual_result"],
            "resource_ids": result.get("resource_ids", {}),
            "correlation_id": correlation_id,
            "expected_result": step.expected_result,
        }

    def _register_agents(self, step: DemoScenarioStepResponse, *, run_id: str) -> dict[str, Any]:
        agents = step.action_config.get("agents", [])
        agent_ids = [str(agent["id"]) for agent in agents if isinstance(agent, dict) and agent.get("id")]
        return {
            "actual_result": f"Registered {len(agent_ids)} demo agents.",
            "resource_ids": {"agent_ids": agent_ids},
        }

    def _import_policies(self, step: DemoScenarioStepResponse, *, run_id: str) -> dict[str, Any]:
        slugs = [str(slug) for slug in step.action_config.get("policy_slugs", [])]
        return {
            "actual_result": f"Imported {len(slugs)} active demo policies.",
            "resource_ids": {"policy_slugs": slugs},
        }

    def _register_mcp_server(self, step: DemoScenarioStepResponse, *, run_id: str) -> dict[str, Any]:
        server_id = str(step.action_config.get("server_id") or "mcp_demo_refund")
        tools = [str(tool) for tool in step.action_config.get("tools", [])]
        return {
            "actual_result": f"Registered MCP server {server_id} with {len(tools)} tools.",
            "resource_ids": {"mcp_server_id": server_id, "tool_names": tools},
        }

    def _run_agent_prompt(self, step: DemoScenarioStepResponse, *, run_id: str) -> dict[str, Any]:
        decision = str(step.action_config.get("expected_decision") or "allow")
        return {
            "actual_result": f"Prompt evaluated with {decision} decision.",
            "resource_ids": {"mesh_message_id": f"mesh_msg_{run_id}_{step.step_order}"},
        }

    def _request_approval(self, step: DemoScenarioStepResponse, *, run_id: str) -> dict[str, Any]:
        return {
            "actual_result": "High-value refund approval was requested and approved.",
            "resource_ids": {"approval_id": f"approval_{run_id}_{step.step_order}"},
        }

    def _rotate_credential(self, step: DemoScenarioStepResponse, *, run_id: str) -> dict[str, Any]:
        agent_id = str(step.action_config.get("agent_id") or "agent_demo_refund")
        return {
            "actual_result": f"Rotated demo credential for {agent_id}.",
            "resource_ids": {
                "agent_id": agent_id,
                "credential_rotation_id": f"credrot_{run_id}_{step.step_order}",
            },
        }

    def _run_discovery(self, step: DemoScenarioStepResponse, *, run_id: str) -> dict[str, Any]:
        return {
            "actual_result": "Discovery scan found and reconciled the shadow refund helper.",
            "resource_ids": {
                "discovery_run_id": f"disco_{run_id}_{step.step_order}",
                "finding_id": str(step.action_config.get("expected_finding") or "shadow_refund_helper"),
            },
        }

    def _run_saga(self, step: DemoScenarioStepResponse, *, run_id: str) -> dict[str, Any]:
        saga_id = str(step.action_config.get("saga_id") or f"saga_{run_id}")
        return {
            "actual_result": f"Executed saga {saga_id}.",
            "resource_ids": {"saga_id": saga_id},
        }

    def _generate_report(self, step: DemoScenarioStepResponse, *, run_id: str) -> dict[str, Any]:
        report_type = str(step.action_config.get("report_type") or "demo_refund_evidence")
        return {
            "actual_result": f"Generated {report_type} report.",
            "resource_ids": {"report_id": f"report_{run_id}_{step.step_order}"},
        }


class DemoScenarioRunner:
    """Run demo scenario steps synchronously one step at a time."""

    def __init__(
        self,
        repository: DemoScenarioRepository,
        *,
        executor: DemoStepExecutor | None = None,
        audit_repository: AuditEventRepository | None = None,
        actor_id: str | None = None,
    ) -> None:
        self.repository = repository
        self.executor = executor or DemoStepExecutor()
        self.audit_repository = audit_repository
        self.actor_id = actor_id

    def continue_run(self, run_id: str, *, correlation_id: str | None = None) -> Any:
        """Execute the next pending step and refresh aggregate run status."""

        run = self.repository.get_run(run_id)
        if run is None:
            raise DemoScenarioNotFoundError("Run not found.")
        if run["status"] != DemoRunStatus.RUNNING:
            return run
        step_run = self.repository.next_pending_step_run(run_id)
        if step_run is None:
            return self.repository.refresh_run_status(run_id)
        running_step = self.repository.mark_step_running(step_run["id"])
        step = self.repository.get_step(running_step["demo_step_id"])
        if step is None:
            raise DemoScenarioNotFoundError("Scenario step not found.")
        step_response = demo_step_response(step)
        try:
            result = self.executor.execute(
                step_response,
                run_id=run_id,
                correlation_id=correlation_id,
            )
        except Exception as exc:
            self.repository.mark_step_failed(
                running_step["id"],
                {
                    "ok": False,
                    "action_type": step_response.action_type,
                    "error": str(exc),
                    "correlation_id": correlation_id,
                },
            )
            refreshed = self.repository.refresh_run_status(run_id)
            self._emit_step_event(
                event_type="demo.step.failed",
                step_run_id=running_step["id"],
                step=step_response,
                result={"error": str(exc)},
                correlation_id=correlation_id,
            )
            self._emit_run_terminal_event(refreshed, correlation_id=correlation_id)
            return refreshed
        self.repository.mark_step_succeeded(running_step["id"], result)
        refreshed = self.repository.refresh_run_status(run_id)
        self._emit_step_event(
            event_type="demo.step.completed",
            step_run_id=running_step["id"],
            step=step_response,
            result=result,
            correlation_id=correlation_id,
        )
        self._emit_run_terminal_event(refreshed, correlation_id=correlation_id)
        return refreshed

    def _emit_step_event(
        self,
        *,
        event_type: str,
        step_run_id: str,
        step: DemoScenarioStepResponse,
        result: dict[str, Any],
        correlation_id: str | None,
    ) -> None:
        if self.audit_repository is None:
            return
        failed = event_type.endswith("failed")
        self.audit_repository.insert(
            AuditEventEnvelope(
                organization_id=self.repository.organization_id,
                environment_id=self.repository.environment_id,
                event_type=event_type,
                source_component="demo-lab",
                actor_type="user",
                actor_id=self.actor_id,
                resource_type="demo_step_run",
                resource_id=step_run_id,
                decision="deny" if failed else "allow",
                severity="warning" if failed else "info",
                correlation_id=correlation_id,
                payload_json={
                    "demo_step_id": step.id,
                    "step_order": step.step_order,
                    "title": step.title,
                    "action_type": step.action_type,
                    "result": result,
                },
            )
        )

    def _emit_run_terminal_event(self, run: Any, *, correlation_id: str | None) -> None:
        if self.audit_repository is None:
            return
        event_type_by_status = {
            DemoRunStatus.SUCCEEDED: "demo.run.completed",
            DemoRunStatus.FAILED: "demo.run.failed",
            DemoRunStatus.CANCELED: "demo.run.canceled",
        }
        event_type = event_type_by_status.get(run["status"])
        if event_type is None:
            return
        self.audit_repository.insert(
            demo_run_audit_event(
                event_type=event_type,
                organization_id=self.repository.organization_id,
                environment_id=self.repository.environment_id,
                actor_id=self.actor_id,
                run_id=run["id"],
                scenario_id=run["scenario_id"],
                status=run["status"],
                summary_json=run["summary_json"],
                correlation_id=correlation_id,
            )
        )


def demo_run_audit_event(
    *,
    event_type: str,
    organization_id: str,
    environment_id: str,
    actor_id: str | None,
    run_id: str,
    scenario_id: str,
    status: str,
    summary_json: str,
    correlation_id: str | None,
) -> AuditEventEnvelope:
    """Build a canonical audit event for demo run lifecycle changes."""

    failed = status in {DemoRunStatus.FAILED, DemoRunStatus.CANCELED}
    return AuditEventEnvelope(
        organization_id=organization_id,
        environment_id=environment_id,
        event_type=event_type,
        source_component="demo-lab",
        actor_type="user",
        actor_id=actor_id,
        resource_type="demo_run",
        resource_id=run_id,
        decision="deny" if failed else "allow",
        severity="warning" if failed else "info",
        correlation_id=correlation_id,
        payload_json={
            "scenario_id": scenario_id,
            "status": status,
            "summary_json": summary_json,
        },
    )
