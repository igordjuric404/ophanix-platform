"""Demo-safe saga execution backed by persisted product state."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Row
from typing import Any, Iterable

from product_platform.runtime.sagas import SagaNotFoundError, SagaRepository


class SagaExecutionError(ValueError):
    """Raised when a saga cannot be executed safely."""


@dataclass(frozen=True)
class SagaExecutionResult:
    """Normalized result for one saga execution attempt."""

    saga_id: str
    status: str
    message: str
    executed_step_ids: list[str] = field(default_factory=list)
    compensated_step_ids: list[str] = field(default_factory=list)
    failed_step_id: str | None = None


@dataclass(frozen=True)
class SagaCompensationResult:
    """Summary of reverse-order compensation."""

    compensated_step_ids: list[str]
    failed_step_ids: list[str]


class DemoSafeActionRunner:
    """Deterministic action runner for demo workflows only."""

    SAFE_ACTIONS = {
        "claims.lookup_order",
        "claims.issue_refund",
        "claims.reverse_refund",
        "claims.release_lookup_hold",
        "notifications.send_email",
        "notifications.retract_email",
    }

    def __init__(self, *, failure_actions: Iterable[str] | None = None) -> None:
        self.failure_actions = set(failure_actions or [])

    async def run(self, action_name: str, *, saga: Row, step: Row, compensation: bool = False) -> dict:
        """Run one deterministic safe action or raise a configured failure."""

        if action_name not in self.SAFE_ACTIONS:
            raise SagaExecutionError(f"Action is not demo-safe: {action_name}.")
        if action_name in self.failure_actions:
            raise SagaExecutionError(f"Configured demo failure for action: {action_name}.")
        return {
            "action_name": action_name,
            "mode": "compensation" if compensation else "execute",
            "saga_id": saga["id"],
            "step_id": step["id"],
            "correlation_id": saga["correlation_id"],
            "target_agent_id": step["target_agent_id"],
            "demo_safe": True,
        }


class SagaExecutionService:
    """Execute persisted saga definitions with hypervisor saga semantics."""

    def __init__(
        self,
        repository: SagaRepository,
        *,
        action_runner: DemoSafeActionRunner | None = None,
    ) -> None:
        SagaOrchestrator, _StepState = _load_hypervisor_saga_classes()
        self.repository = repository
        self.action_runner = action_runner or DemoSafeActionRunner()
        self._orchestrator_cls = SagaOrchestrator

    async def execute(self, saga_id: str) -> SagaExecutionResult:
        """Execute all pending saga steps in order."""

        saga = self.repository.get_saga(saga_id)
        if saga is None:
            raise SagaNotFoundError("Saga not found.")
        steps = self.repository.list_steps(saga_id)
        if not steps:
            raise SagaExecutionError("Saga must have at least one step before execution.")
        if saga["status"] in {"running", "compensating"}:
            raise SagaExecutionError("Saga is already executing.")

        self.repository.update_saga_status(saga_id, "running", mark_started=True)
        self.repository.create_event(
            saga_id,
            event_type="saga.started",
            message="Saga execution started.",
            payload={"step_count": len(steps)},
        )

        orchestrator = self._orchestrator_cls()
        hypervisor_saga = orchestrator.create_saga(saga["runtime_session_id"] or saga["id"])
        step_pairs = []
        step_by_hypervisor_id: dict[str, Row] = {}
        for step in steps:
            hypervisor_step = orchestrator.add_step(
                hypervisor_saga.saga_id,
                action_id=step["action_name"],
                agent_did=step["target_agent_id"],
                execute_api=step["action_name"],
                undo_api=step["compensation_action"],
                timeout_seconds=step["timeout_seconds"],
                max_retries=step["retry_count"],
            )
            step_pairs.append((step, hypervisor_step))
            step_by_hypervisor_id[hypervisor_step.step_id] = step

        executed_step_ids: list[str] = []
        for step, hypervisor_step in step_pairs:
            self.repository.update_step_status(
                step["id"],
                "executing",
                result={"action_name": step["action_name"]},
            )
            self.repository.create_event(
                saga_id,
                step_id=step["id"],
                event_type="saga.step.started",
                message=f"Step {step['step_order']} started.",
                payload={"action_name": step["action_name"]},
            )
            try:
                result = await orchestrator.execute_step(
                    hypervisor_saga.saga_id,
                    hypervisor_step.step_id,
                    lambda step=step: self.action_runner.run(
                        step["action_name"],
                        saga=saga,
                        step=step,
                    ),
                )
            except Exception as exc:
                self.repository.update_step_status(
                    step["id"],
                    "failed",
                    result={"action_name": step["action_name"], "error": str(exc)},
                )
                self.repository.create_event(
                    saga_id,
                    step_id=step["id"],
                    event_type="saga.step.failed",
                    message=f"Step {step['step_order']} failed.",
                    payload={"action_name": step["action_name"], "error": str(exc)},
                )
                compensation = await self._compensate(
                    orchestrator,
                    hypervisor_saga.saga_id,
                    saga=saga,
                    step_by_hypervisor_id=step_by_hypervisor_id,
                )
                if compensation.failed_step_ids:
                    final_status = "compensation_failed"
                elif compensation.compensated_step_ids:
                    final_status = "compensated"
                else:
                    final_status = "failed"
                self.repository.update_saga_status(saga_id, final_status, mark_finished=True)
                self.repository.create_event(
                    saga_id,
                    event_type=f"saga.{final_status}",
                    message="Saga execution ended after failure.",
                    payload={
                        "failed_step_id": step["id"],
                        "compensated_step_ids": compensation.compensated_step_ids,
                        "compensation_failed_step_ids": compensation.failed_step_ids,
                    },
                )
                return SagaExecutionResult(
                    saga_id=saga_id,
                    status=final_status,
                    message="Saga execution ended after failure.",
                    executed_step_ids=executed_step_ids,
                    compensated_step_ids=compensation.compensated_step_ids,
                    failed_step_id=step["id"],
                )

            executed_step_ids.append(step["id"])
            self.repository.update_step_status(
                step["id"],
                "committed",
                result=result,
            )
            self.repository.create_event(
                saga_id,
                step_id=step["id"],
                event_type="saga.step.committed",
                message=f"Step {step['step_order']} committed.",
                payload={"action_name": step["action_name"], "result": result},
            )

        self.repository.update_saga_status(saga_id, "completed", mark_finished=True)
        self.repository.create_event(
            saga_id,
            event_type="saga.completed",
            message="Saga execution completed.",
            payload={"executed_step_ids": executed_step_ids},
        )
        return SagaExecutionResult(
            saga_id=saga_id,
            status="completed",
            message="Saga execution completed.",
            executed_step_ids=executed_step_ids,
        )

    async def _compensate(
        self,
        orchestrator: Any,
        hypervisor_saga_id: str,
        *,
        saga: Row,
        step_by_hypervisor_id: dict[str, Row],
    ) -> SagaCompensationResult:
        """Run reverse compensation through the hypervisor orchestrator."""

        self.repository.update_saga_status(saga["id"], "compensating")
        self.repository.create_event(
            saga["id"],
            event_type="saga.compensating",
            message="Saga compensation started.",
            payload={},
        )
        compensated_step_ids: list[str] = []
        failed_step_ids: list[str] = []

        async def compensator(hypervisor_step: Any) -> dict:
            step = step_by_hypervisor_id[hypervisor_step.step_id]
            action_name = step["compensation_action"]
            self.repository.update_step_status(
                step["id"],
                "compensating",
                result={"compensation_action": action_name},
            )
            self.repository.create_event(
                saga["id"],
                step_id=step["id"],
                event_type="saga.step.compensating",
                message=f"Step {step['step_order']} compensation started.",
                payload={"compensation_action": action_name},
            )
            try:
                result = await self.action_runner.run(
                    action_name,
                    saga=saga,
                    step=step,
                    compensation=True,
                )
            except Exception as exc:
                failed_step_ids.append(step["id"])
                self.repository.update_step_status(
                    step["id"],
                    "compensation_failed",
                    result={"compensation_action": action_name, "error": str(exc)},
                )
                self.repository.create_event(
                    saga["id"],
                    step_id=step["id"],
                    event_type="saga.step.compensation_failed",
                    message=f"Step {step['step_order']} compensation failed.",
                    payload={"compensation_action": action_name, "error": str(exc)},
                )
                raise
            self.repository.update_step_status(step["id"], "compensated", result=result)
            self.repository.create_event(
                saga["id"],
                step_id=step["id"],
                event_type="saga.step.compensated",
                message=f"Step {step['step_order']} compensated.",
                payload={"compensation_action": action_name, "result": result},
            )
            compensated_step_ids.append(step["id"])
            return result

        failed_hypervisor_steps = await orchestrator.compensate(hypervisor_saga_id, compensator)
        for hypervisor_step in failed_hypervisor_steps:
            step = step_by_hypervisor_id.get(hypervisor_step.step_id)
            if step is None or step["id"] in failed_step_ids:
                continue
            failed_step_ids.append(step["id"])
            self.repository.update_step_status(
                step["id"],
                "compensation_failed",
                result={
                    "compensation_action": step["compensation_action"],
                    "error": hypervisor_step.error or "Compensation failed.",
                },
            )
            self.repository.create_event(
                saga["id"],
                step_id=step["id"],
                event_type="saga.step.compensation_failed",
                message=f"Step {step['step_order']} compensation failed.",
                payload={
                    "compensation_action": step["compensation_action"],
                    "error": hypervisor_step.error or "Compensation failed.",
                },
            )
        return SagaCompensationResult(
            compensated_step_ids=compensated_step_ids,
            failed_step_ids=failed_step_ids,
        )


def _load_hypervisor_saga_classes() -> tuple[Any, Any]:
    try:
        from hypervisor.saga.orchestrator import SagaOrchestrator
        from hypervisor.saga.state_machine import StepState

        return SagaOrchestrator, StepState
    except ModuleNotFoundError:
        hypervisor_src = Path(__file__).resolve().parents[4] / "agent-hypervisor" / "src"
        if str(hypervisor_src) not in sys.path:
            sys.path.insert(0, str(hypervisor_src))
        from hypervisor.saga.orchestrator import SagaOrchestrator
        from hypervisor.saga.state_machine import StepState

        return SagaOrchestrator, StepState
