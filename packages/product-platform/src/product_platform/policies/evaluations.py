"""Policy evaluation adapter for simulator and live decision feeds."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from product_platform.db.postgres import Connection, Row
from typing import Any

from product_platform.policies.bindings import PolicyBindingRepository
from product_platform.policies.models import (
    PolicyBindingResolutionContext,
    PolicyEvaluationRequest,
    PolicyEvaluationResponse,
)
from product_platform.policies.repository import PolicyNotFoundError, PolicyRepository


@dataclass(frozen=True)
class PolicyBackendDecision:
    """Backend-neutral decision produced by a policy evaluator."""

    allowed: bool
    action: str
    reason: str
    matched_rule: str | None = None
    audit_entry: dict[str, Any] | None = None


PolicyBackendEvaluator = Callable[[Row, dict[str, Any]], PolicyBackendDecision]


class PolicyEvaluationAdapter:
    """Resolve policy versions and evaluate them with a selected backend."""

    def __init__(
        self,
        connection: Connection,
        organization_id: str,
        environment_id: str,
        *,
        backend_evaluators: dict[str, PolicyBackendEvaluator] | None = None,
    ) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id
        self._backend_evaluators: dict[str, PolicyBackendEvaluator] = {"native": self._evaluate_native}
        if backend_evaluators:
            self._backend_evaluators.update(backend_evaluators)

    def evaluate(
        self,
        request: PolicyEvaluationRequest,
        *,
        correlation_id: str | None = None,
        now: str | None = None,
    ) -> PolicyEvaluationResponse:
        """Evaluate a policy request and return a normalized decision."""

        started = time.perf_counter()
        binding: Row | None = None
        version: Row | None = None
        backend = request.backend or "native"
        context = self._evaluation_context(request, correlation_id=correlation_id)
        try:
            binding, version = self._resolve_version(request, correlation_id=correlation_id, now=now)
            if version is None:
                return self._response(
                    request,
                    context=context,
                    started=started,
                    correlation_id=correlation_id,
                    decision="allow",
                    action="allow",
                    reason="No active policy binding matched; default allow.",
                    backend=backend,
                )

            backend = request.backend or str(version["backend"])
            evaluator = self._backend_evaluators.get(backend)
            if evaluator is None:
                raise ValueError(f"No local evaluator is registered for backend '{backend}'.")
            decision = evaluator(version, context)
            policy_action = decision.action.strip().lower() or ("allow" if decision.allowed else "deny")
            return self._response(
                request,
                context=context,
                started=started,
                correlation_id=correlation_id,
                decision="allow" if decision.allowed else "deny",
                action=policy_action,
                reason=decision.reason,
                backend=backend,
                binding=binding,
                version=version,
                matched_rule=decision.matched_rule,
                audit_preview=decision.audit_entry or {},
                error=bool((decision.audit_entry or {}).get("error")),
            )
        except Exception as exc:
            return self._response(
                request,
                context=context,
                started=started,
                correlation_id=correlation_id,
                decision="deny",
                action="deny",
                reason=f"Policy evaluation failed closed: {exc}",
                backend=backend,
                binding=binding,
                version=version,
                error=True,
                audit_preview={"error": True, "message": str(exc)},
            )

    def _resolve_version(
        self,
        request: PolicyEvaluationRequest,
        *,
        correlation_id: str | None,
        now: str | None,
    ) -> tuple[Row | None, Row | None]:
        policy_repository = PolicyRepository(self.connection, self.organization_id)
        if request.policy_id:
            if policy_repository.get_policy(request.policy_id) is None:
                raise PolicyNotFoundError("Policy not found.")
            version = policy_repository.latest_export_version(
                request.policy_id,
                request.policy_version_id,
            )
            if version is None:
                raise PolicyNotFoundError("Policy version not found.")
            return None, version

        target_type = request.target_type
        target_id = request.target_id
        if target_type is None or target_id is None:
            raise ValueError("target_type and target_id are required for binding resolution.")
        binding_repository = PolicyBindingRepository(
            self.connection,
            self.organization_id,
            self.environment_id,
        )
        bindings = binding_repository.resolve_bindings(
            PolicyBindingResolutionContext(
                organization_id=self.organization_id,
                environment_id=self.environment_id,
                target_type=target_type,
                target_id=target_id,
                agent_id=request.agent_id,
                correlation_id=correlation_id,
            ),
            now=now,
        )
        if not bindings:
            return None, None
        binding = bindings[0]
        version = policy_repository.get_version(binding["policy_id"], binding["policy_version_id"])
        if version is None:
            raise PolicyNotFoundError("Bound policy version not found.")
        return binding, version

    def _evaluate_native(self, version: Row, context: dict[str, Any]) -> PolicyBackendDecision:
        body_format = str(version["body_format"]).strip().lower()
        if body_format not in {"yaml", "json"}:
            raise ValueError(f"Native evaluator does not support '{body_format}' policy bodies.")
        PolicyEvaluator, PolicyDocument = _load_agent_os_policy_classes()
        document = PolicyDocument.model_validate(_parse_policy_body(str(version["body_text"]), body_format))
        result = PolicyEvaluator([document]).evaluate(context)
        return PolicyBackendDecision(
            allowed=bool(result.allowed),
            action=str(result.action),
            reason=str(result.reason),
            matched_rule=result.matched_rule,
            audit_entry=dict(result.audit_entry),
        )

    def _evaluation_context(
        self,
        request: PolicyEvaluationRequest,
        *,
        correlation_id: str | None,
    ) -> dict[str, Any]:
        context = dict(request.context)
        context.update(
            {
                "action": request.action,
                "organization_id": self.organization_id,
                "environment_id": self.environment_id,
            }
        )
        for key, value in {
            "agent_id": request.agent_id,
            "target_type": request.target_type,
            "target_id": request.target_id,
            "resource_type": request.resource_type,
            "resource_id": request.resource_id,
            "correlation_id": correlation_id,
        }.items():
            if value is not None:
                context[key] = value
        if "tool_name" not in context and request.target_type == "mcp-tool" and request.target_id:
            context["tool_name"] = request.target_id
        return context

    def _response(
        self,
        request: PolicyEvaluationRequest,
        *,
        context: dict[str, Any],
        started: float,
        correlation_id: str | None,
        decision: str,
        action: str,
        reason: str,
        backend: str,
        binding: Row | None = None,
        version: Row | None = None,
        matched_rule: str | None = None,
        error: bool = False,
        audit_preview: dict[str, Any] | None = None,
    ) -> PolicyEvaluationResponse:
        latency_ms = max((time.perf_counter() - started) * 1000, 0.0)
        policy_id = request.policy_id or (str(binding["policy_id"]) if binding is not None else None)
        policy_version_id = (
            str(version["id"])
            if version is not None
            else request.policy_version_id
        )
        return PolicyEvaluationResponse(
            organization_id=self.organization_id,
            environment_id=self.environment_id,
            policy_id=policy_id,
            policy_version_id=policy_version_id,
            binding_id=str(binding["id"]) if binding is not None else None,
            binding_mode=str(binding["mode"]) if binding is not None else None,
            agent_id=request.agent_id,
            target_type=request.target_type,
            target_id=request.target_id,
            action=request.action,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            context=context,
            decision=decision,
            policy_action=action,
            matched_rule=matched_rule,
            reason=reason,
            latency_ms=round(latency_ms, 3),
            mode=request.mode,
            correlation_id=correlation_id,
            backend=backend,
            error=error,
            audit_preview=audit_preview or {},
        )


def _parse_policy_body(body_text: str, body_format: str) -> dict[str, Any]:
    if body_format == "json":
        parsed = json.loads(body_text)
    else:
        import yaml

        parsed = yaml.safe_load(body_text)
    if not isinstance(parsed, dict):
        raise ValueError("Policy body must be a mapping/object.")
    return parsed


def _load_agent_os_policy_classes() -> tuple[Any, Any]:
    try:
        from agent_os.policies.evaluator import PolicyEvaluator
        from agent_os.policies.schema import PolicyDocument

        return PolicyEvaluator, PolicyDocument
    except ImportError:
        agent_os_src = Path(__file__).resolve().parents[4] / "agent-os" / "src"
        if agent_os_src.exists() and str(agent_os_src) not in sys.path:
            sys.path.insert(0, str(agent_os_src))
        from agent_os.policies.evaluator import PolicyEvaluator
        from agent_os.policies.schema import PolicyDocument

        return PolicyEvaluator, PolicyDocument

