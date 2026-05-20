"""Demo-safe saga execution backed by persisted product state."""

from __future__ import annotations

import sys
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ContextManager, Iterable, Iterator

from product_platform.db.postgres import Connection, Row
from product_platform.runtime.saga_actions import SUPPORTED_SAGA_ACTIONS
from product_platform.runtime.sagas import (
    SAGA_EXECUTABLE_STATUSES,
    SAGA_RECOVERABLE_STATUSES,
    SagaNotFoundError,
    SagaRepository,
)


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
    replayed_step_ids: list[str] = field(default_factory=list)
    failed_step_id: str | None = None


@dataclass(frozen=True)
class SagaCompensationResult:
    """Summary of reverse-order compensation."""

    compensated_step_ids: list[str]
    failed_step_ids: list[str]


class DemoSafeActionRunner:
    """Deterministic action runner for demo workflows only."""

    SAFE_ACTIONS = SUPPORTED_SAGA_ACTIONS

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
        transaction_factory: Callable[[], ContextManager[Connection]] | None = None,
    ) -> None:
        SagaOrchestrator, _StepState = _load_hypervisor_saga_classes()
        self.repository = repository
        self.action_runner = action_runner or DemoSafeActionRunner()
        self.transaction_factory = transaction_factory
        self._orchestrator_cls = SagaOrchestrator

    async def execute(self, saga_id: str) -> SagaExecutionResult:
        """Execute all pending saga steps in order."""

        with self._repository_context() as repository:
            saga = repository.get_saga(saga_id)
            if saga is None:
                raise SagaNotFoundError("Saga not found.")
            steps = repository.list_steps(saga_id)
            if not steps:
                raise SagaExecutionError("Saga must have at least one step before execution.")
            recovering = saga["status"] in SAGA_RECOVERABLE_STATUSES
            if saga["status"] not in SAGA_EXECUTABLE_STATUSES | SAGA_RECOVERABLE_STATUSES:
                raise SagaExecutionError(f"Saga cannot be executed from status: {saga['status']}.")

            if recovering:
                repository.create_event(
                    saga_id,
                    event_type="saga.recovered",
                    message="Saga execution recovered from persisted state.",
                    payload={"step_count": len(steps)},
                )
            else:
                repository.update_saga_status(
                    saga_id,
                    "running",
                    mark_started=True,
                    expected_statuses=SAGA_EXECUTABLE_STATUSES,
                )
                repository.create_event(
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
        replayed_step_ids: list[str] = []
        for step, hypervisor_step in step_pairs:
            replayed = await self._replay_activity_result(
                orchestrator,
                hypervisor_saga.saga_id,
                hypervisor_step.step_id,
                saga=saga,
                step=step,
            )
            if replayed is not None:
                executed_step_ids.append(step["id"])
                replayed_step_ids.append(step["id"])
                continue

            with self._repository_context() as repository:
                repository.start_activity_result(
                    saga_id=saga_id,
                    step_id=step["id"],
                    mode="execute",
                    action_name=step["action_name"],
                )
                repository.update_step_status(
                    step["id"],
                    "executing",
                    result={"action_name": step["action_name"]},
                )
                repository.create_event(
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
                with self._repository_context() as repository:
                    repository.fail_activity_result(
                        saga_id=saga_id,
                        step_id=step["id"],
                        mode="execute",
                        action_name=step["action_name"],
                        error_message=str(exc),
                    )
                    repository.update_step_status(
                        step["id"],
                        "failed",
                        result={"action_name": step["action_name"], "error": str(exc)},
                    )
                    repository.create_event(
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
                with self._repository_context() as repository:
                    repository.update_saga_status(
                        saga_id,
                        final_status,
                        mark_finished=True,
                        expected_statuses={"running", "compensating"},
                    )
                    repository.create_event(
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
            with self._repository_context() as repository:
                repository.complete_activity_result(
                    saga_id=saga_id,
                    step_id=step["id"],
                    mode="execute",
                    action_name=step["action_name"],
                    result=result,
                )
                checkpoint = repository.create_checkpoint(
                    saga_id=saga_id,
                    step_id=step["id"],
                    mode="execute",
                    payload=_checkpoint_payload(
                        saga=saga,
                        step=step,
                        result=result,
                        side_effect_boundary="after_activity_before_step_commit",
                    ),
                    policy_snapshot=_policy_snapshot(step),
                    tool_calls=_tool_calls(step, mode="execute"),
                )
                repository.create_event(
                    saga_id,
                    step_id=step["id"],
                    event_type="saga.checkpoint.created",
                    message=f"Step {step['step_order']} checkpoint created.",
                    payload={
                        "checkpoint_id": checkpoint["id"],
                        "payload_hash": checkpoint["payload_hash"],
                        "mode": "execute",
                    },
                )
                repository.update_step_status(
                    step["id"],
                    "committed",
                    result=result,
                )
                repository.create_event(
                    saga_id,
                    step_id=step["id"],
                    event_type="saga.step.committed",
                    message=f"Step {step['step_order']} committed.",
                    payload={"action_name": step["action_name"], "result": result},
                )

        with self._repository_context() as repository:
            repository.update_saga_status(
                saga_id,
                "completed",
                mark_finished=True,
                expected_statuses={"running"},
            )
            repository.create_event(
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
            replayed_step_ids=replayed_step_ids,
        )

    async def _replay_activity_result(
        self,
        orchestrator: Any,
        hypervisor_saga_id: str,
        hypervisor_step_id: str,
        *,
        saga: Row,
        step: Row,
    ) -> dict | None:
        """Replay a completed activity result into the hypervisor state machine."""

        with self._repository_context() as repository:
            activity_result = repository.get_activity_result(step["id"], "execute")
            if activity_result is None and step["status"] == "committed":
                result = _loads_mapping(step["result_json"])
                activity_result = repository.complete_activity_result(
                    saga_id=saga["id"],
                    step_id=step["id"],
                    mode="execute",
                    action_name=step["action_name"],
                    result=result,
                )
            if activity_result is None or activity_result["status"] != "succeeded":
                return None
            result = _loads_mapping(activity_result["result_json"])
            checkpoint = repository.get_checkpoint(step["id"], "execute")
            if checkpoint is not None:
                checkpoint = repository.restore_checkpoint(step["id"], "execute")
                checkpoint_payload = _loads_mapping(checkpoint["payload_json"])
                checkpoint_result = checkpoint_payload.get("result")
                if isinstance(checkpoint_result, dict):
                    result = checkpoint_result
                repository.create_event(
                    saga["id"],
                    step_id=step["id"],
                    event_type="saga.checkpoint.restored",
                    message=f"Step {step['step_order']} checkpoint restored.",
                    payload={
                        "checkpoint_id": checkpoint["id"],
                        "payload_hash": checkpoint["payload_hash"],
                        "mode": "execute",
                    },
                )
            repository.create_event(
                saga["id"],
                step_id=step["id"],
                event_type="saga.activity.replayed",
                message=f"Step {step['step_order']} activity result replayed.",
                payload={
                    "action_name": step["action_name"],
                    "activity_result_id": activity_result["id"],
                    "mode": "execute",
                },
            )

        async def replay_activity() -> dict:
            return result

        replayed = await orchestrator.execute_step(
            hypervisor_saga_id,
            hypervisor_step_id,
            replay_activity,
        )
        with self._repository_context() as repository:
            repository.update_step_status(step["id"], "committed", result=replayed)
            repository.create_event(
                saga["id"],
                step_id=step["id"],
                event_type="saga.step.committed",
                message=f"Step {step['step_order']} committed from durable replay.",
                payload={
                    "action_name": step["action_name"],
                    "result": replayed,
                    "replayed": True,
                },
            )
        return replayed

    async def _compensate(
        self,
        orchestrator: Any,
        hypervisor_saga_id: str,
        *,
        saga: Row,
        step_by_hypervisor_id: dict[str, Row],
    ) -> SagaCompensationResult:
        """Run reverse compensation through the hypervisor orchestrator."""

        with self._repository_context() as repository:
            repository.update_saga_status(
                saga["id"],
                "compensating",
                expected_statuses={"running"},
            )
            repository.create_event(
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
            with self._repository_context() as repository:
                repository.update_step_status(
                    step["id"],
                    "compensating",
                    result={"compensation_action": action_name},
                )
                repository.create_event(
                    saga["id"],
                    step_id=step["id"],
                    event_type="saga.step.compensating",
                    message=f"Step {step['step_order']} compensation started.",
                        payload={"compensation_action": action_name},
                    )
            try:
                with self._repository_context() as repository:
                    existing = repository.get_activity_result(step["id"], "compensation")
                    if existing is not None and existing["status"] == "succeeded":
                        result = _loads_mapping(existing["result_json"])
                        checkpoint = repository.get_checkpoint(step["id"], "compensation")
                        if checkpoint is not None:
                            checkpoint = repository.restore_checkpoint(step["id"], "compensation")
                            checkpoint_payload = _loads_mapping(checkpoint["payload_json"])
                            checkpoint_result = checkpoint_payload.get("result")
                            if isinstance(checkpoint_result, dict):
                                result = checkpoint_result
                            repository.create_event(
                                saga["id"],
                                step_id=step["id"],
                                event_type="saga.checkpoint.restored",
                                message=f"Step {step['step_order']} compensation checkpoint restored.",
                                payload={
                                    "checkpoint_id": checkpoint["id"],
                                    "payload_hash": checkpoint["payload_hash"],
                                    "mode": "compensation",
                                },
                            )
                        repository.create_event(
                            saga["id"],
                            step_id=step["id"],
                            event_type="saga.activity.replayed",
                            message=f"Step {step['step_order']} compensation result replayed.",
                            payload={
                                "compensation_action": action_name,
                                "activity_result_id": existing["id"],
                                "mode": "compensation",
                            },
                        )
                    else:
                        repository.start_activity_result(
                            saga_id=saga["id"],
                            step_id=step["id"],
                            mode="compensation",
                            action_name=action_name,
                        )
                        existing = None
                if existing is not None:
                    result = _loads_mapping(existing["result_json"])
                else:
                    result = await self.action_runner.run(
                        action_name,
                        saga=saga,
                        step=step,
                        compensation=True,
                    )
                    with self._repository_context() as repository:
                        repository.complete_activity_result(
                            saga_id=saga["id"],
                            step_id=step["id"],
                            mode="compensation",
                            action_name=action_name,
                            result=result,
                        )
                        checkpoint = repository.create_checkpoint(
                            saga_id=saga["id"],
                            step_id=step["id"],
                            mode="compensation",
                            payload=_checkpoint_payload(
                                saga=saga,
                                step=step,
                                result=result,
                                side_effect_boundary="after_compensation_before_step_commit",
                            ),
                            policy_snapshot=_policy_snapshot(step),
                            tool_calls=_tool_calls(step, mode="compensation"),
                        )
                        repository.create_event(
                            saga["id"],
                            step_id=step["id"],
                            event_type="saga.checkpoint.created",
                            message=f"Step {step['step_order']} compensation checkpoint created.",
                            payload={
                                "checkpoint_id": checkpoint["id"],
                                "payload_hash": checkpoint["payload_hash"],
                                "mode": "compensation",
                            },
                        )
            except Exception as exc:
                failed_step_ids.append(step["id"])
                with self._repository_context() as repository:
                    repository.fail_activity_result(
                        saga_id=saga["id"],
                        step_id=step["id"],
                        mode="compensation",
                        action_name=action_name,
                        error_message=str(exc),
                    )
                    repository.update_step_status(
                        step["id"],
                        "compensation_failed",
                        result={"compensation_action": action_name, "error": str(exc)},
                    )
                    repository.create_event(
                        saga["id"],
                        step_id=step["id"],
                        event_type="saga.step.compensation_failed",
                        message=f"Step {step['step_order']} compensation failed.",
                        payload={"compensation_action": action_name, "error": str(exc)},
                    )
                raise
            with self._repository_context() as repository:
                repository.update_step_status(step["id"], "compensated", result=result)
                repository.create_event(
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
            with self._repository_context() as repository:
                repository.update_step_status(
                    step["id"],
                    "compensation_failed",
                    result={
                        "compensation_action": step["compensation_action"],
                        "error": hypervisor_step.error or "Compensation failed.",
                    },
                )
                repository.create_event(
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

    @contextmanager
    def _repository_context(self) -> Iterator[SagaRepository]:
        if self.transaction_factory is None:
            yield self.repository
            return
        with self.transaction_factory() as connection:
            yield SagaRepository(
                connection,
                self.repository.organization_id,
                self.repository.environment_id,
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

def _loads_mapping(value: str | bytes | bytearray | None) -> dict:
    if value is None:
        return {}
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {}


def _checkpoint_payload(
    *,
    saga: Row,
    step: Row,
    result: dict,
    side_effect_boundary: str,
) -> dict:
    return {
        "result": result,
        "side_effect_boundary": side_effect_boundary,
        "saga_id": saga["id"],
        "runtime_session_id": saga["runtime_session_id"],
        "step_id": step["id"],
        "action_name": step["action_name"],
        "correlation_id": saga["correlation_id"],
    }


def _policy_snapshot(step: Row) -> dict:
    return {
        "target_agent_id": step["target_agent_id"],
        "required_capability": step["required_capability"],
        "retry_count": step["retry_count"],
        "timeout_seconds": step["timeout_seconds"],
    }


def _tool_calls(step: Row, *, mode: str) -> list[dict]:
    action_name = step["compensation_action"] if mode == "compensation" else step["action_name"]
    return [
        {
            "action_name": action_name,
            "mode": mode,
            "target_agent_id": step["target_agent_id"],
        }
    ]
