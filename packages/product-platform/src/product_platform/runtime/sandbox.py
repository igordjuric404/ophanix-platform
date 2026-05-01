"""Sandbox profile persistence and validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from sqlite3 import Connection, IntegrityError, Row
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.runtime.models import (
    SUBPROCESS_SANDBOX_WARNING,
    SUPPORTED_SANDBOX_PROFILE_STATUSES,
    SUPPORTED_SANDBOX_PROVIDER_TYPES,
    SandboxDecisionResponse,
    SandboxProfileCreateRequest,
    SandboxProfilePatchRequest,
    SandboxProfileResponse,
    SandboxProfileTestRequest,
    SandboxViolationResponse,
)


class SandboxProfileNotFoundError(ValueError):
    """Raised when a sandbox profile is not visible in tenant scope."""


class SandboxProfileValidationError(ValueError):
    """Raised when a sandbox profile request is invalid."""


class DuplicateSandboxProfileNameError(ValueError):
    """Raised when a sandbox profile name already exists in tenant scope."""


class SandboxProfileRepository:
    """Tenant-scoped sandbox profile repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_profile(self, body: SandboxProfileCreateRequest) -> Row:
        """Create a sandbox profile."""

        _validate_provider_type(body.provider_type)
        _validate_status(body.status)
        profile_id = generate_id("sbxprof")
        now = utc_now_iso()
        try:
            self.connection.execute(
                """
                INSERT INTO sandbox_profiles (
                    id, organization_id, environment_id, name, provider_type,
                    allowed_imports_json, blocked_imports_json, allowed_paths_json,
                    network_policy_json, resource_limits_json, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    self.organization_id,
                    self.environment_id,
                    body.name,
                    body.provider_type,
                    json.dumps(body.allowed_imports, sort_keys=True),
                    json.dumps(body.blocked_imports, sort_keys=True),
                    json.dumps(body.allowed_paths, sort_keys=True),
                    json.dumps(body.network_policy, sort_keys=True),
                    json.dumps(body.resource_limits, sort_keys=True),
                    body.status,
                    now,
                    now,
                ),
            )
        except IntegrityError as exc:
            raise DuplicateSandboxProfileNameError("Sandbox profile name already exists.") from exc
        row = self.get_profile(profile_id)
        if row is None:
            raise SandboxProfileNotFoundError("Created sandbox profile could not be loaded.")
        return row

    def get_profile(self, profile_id: str) -> Row | None:
        """Get one sandbox profile."""

        return self.connection.execute(
            """
            SELECT *
            FROM sandbox_profiles
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (profile_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_profiles(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List sandbox profiles."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            _validate_status(status)
            clauses.append("status = ?")
            values.append(status)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM sandbox_profiles
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def patch_profile(self, profile_id: str, body: SandboxProfilePatchRequest) -> Row:
        """Patch a sandbox profile."""

        existing = self.get_profile(profile_id)
        if existing is None:
            raise SandboxProfileNotFoundError("Sandbox profile not found.")
        next_values = {
            "name": body.name if body.name is not None else existing["name"],
            "provider_type": body.provider_type if body.provider_type is not None else existing["provider_type"],
            "allowed_imports": body.allowed_imports
            if body.allowed_imports is not None
            else json.loads(existing["allowed_imports_json"]),
            "blocked_imports": body.blocked_imports
            if body.blocked_imports is not None
            else json.loads(existing["blocked_imports_json"]),
            "allowed_paths": body.allowed_paths
            if body.allowed_paths is not None
            else json.loads(existing["allowed_paths_json"]),
            "network_policy": body.network_policy
            if body.network_policy is not None
            else json.loads(existing["network_policy_json"]),
            "resource_limits": body.resource_limits
            if body.resource_limits is not None
            else json.loads(existing["resource_limits_json"]),
            "status": body.status if body.status is not None else existing["status"],
        }
        _validate_provider_type(str(next_values["provider_type"]))
        _validate_status(str(next_values["status"]))
        try:
            self.connection.execute(
                """
                UPDATE sandbox_profiles
                SET name = ?,
                    provider_type = ?,
                    allowed_imports_json = ?,
                    blocked_imports_json = ?,
                    allowed_paths_json = ?,
                    network_policy_json = ?,
                    resource_limits_json = ?,
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (
                    next_values["name"],
                    next_values["provider_type"],
                    json.dumps(next_values["allowed_imports"], sort_keys=True),
                    json.dumps(next_values["blocked_imports"], sort_keys=True),
                    json.dumps(next_values["allowed_paths"], sort_keys=True),
                    json.dumps(next_values["network_policy"], sort_keys=True),
                    json.dumps(next_values["resource_limits"], sort_keys=True),
                    next_values["status"],
                    utc_now_iso(),
                    profile_id,
                    self.organization_id,
                    self.environment_id,
                ),
            )
        except IntegrityError as exc:
            raise DuplicateSandboxProfileNameError("Sandbox profile name already exists.") from exc
        row = self.get_profile(profile_id)
        if row is None:
            raise SandboxProfileNotFoundError("Updated sandbox profile could not be loaded.")
        return row

    def create_decision(
        self,
        profile_id: str,
        *,
        decision: str,
        reason: str,
        agent_id: str | None = None,
        action_name: str | None = None,
    ) -> Row:
        """Persist one sandbox test decision."""

        if self.get_profile(profile_id) is None:
            raise SandboxProfileNotFoundError("Sandbox profile not found.")
        if agent_id:
            self._require_agent(agent_id)
        decision_id = generate_id("sbxdcsn")
        self.connection.execute(
            """
            INSERT INTO sandbox_decisions (
                id, profile_id, agent_id, action_name, decision, reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (decision_id, profile_id, agent_id, action_name, decision, reason, utc_now_iso()),
        )
        row = self.connection.execute("SELECT * FROM sandbox_decisions WHERE id = ?", (decision_id,)).fetchone()
        if row is None:
            raise SandboxProfileValidationError("Created sandbox decision could not be loaded.")
        return row

    def _require_agent(self, agent_id: str) -> None:
        row = self.connection.execute(
            """
            SELECT 1
            FROM agents
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise SandboxProfileValidationError("Sandbox decision agent not found.")


class SandboxTestAdapter:
    """Evaluate sample code with the Agent OS sandbox static validator."""

    def __init__(self, repository: SandboxProfileRepository) -> None:
        self.repository = repository

    def test_profile(self, profile_id: str, body: SandboxProfileTestRequest) -> SandboxDecisionResponse:
        """Return an allow/deny decision and persist it when tied to a real action."""

        profile = self.repository.get_profile(profile_id)
        if profile is None:
            raise SandboxProfileNotFoundError("Sandbox profile not found.")
        ExecutionSandbox, SandboxConfig = _load_agent_os_sandbox_classes()
        config = SandboxConfig(
            blocked_modules=json.loads(profile["blocked_imports_json"]),
            allowed_paths=json.loads(profile["allowed_paths_json"]),
        )
        sandbox = ExecutionSandbox(config=config)
        violations = sandbox.validate_code(body.code)
        violation_responses = [
            SandboxViolationResponse(
                line=violation.line,
                column=violation.column,
                violation_type=violation.violation_type,
                description=violation.description,
                severity=violation.severity,
            )
            for violation in violations
        ]
        decision = "denied" if violations else "allowed"
        reason = (
            "; ".join(violation.description for violation in violations)
            if violations
            else "Sandbox static validation passed."
        )
        persisted = None
        if body.agent_id or body.action_name:
            persisted = self.repository.create_decision(
                profile_id,
                decision=decision,
                reason=reason,
                agent_id=body.agent_id,
                action_name=body.action_name,
            )
        return sandbox_decision_response(
            profile,
            decision=decision,
            reason=reason,
            violations=violation_responses,
            persisted=persisted,
            agent_id=body.agent_id,
            action_name=body.action_name,
        )


def sandbox_profile_response(row: Row) -> SandboxProfileResponse:
    """Serialize a sandbox profile row."""

    return SandboxProfileResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        name=row["name"],
        provider_type=row["provider_type"],
        allowed_imports=json.loads(row["allowed_imports_json"]),
        blocked_imports=json.loads(row["blocked_imports_json"]),
        allowed_paths=json.loads(row["allowed_paths_json"]),
        network_policy=json.loads(row["network_policy_json"]),
        resource_limits=json.loads(row["resource_limits_json"]),
        status=row["status"],
        provider_warning=_provider_warning(row["provider_type"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def sandbox_decision_response(
    profile: Row,
    *,
    decision: str,
    reason: str,
    violations: list[SandboxViolationResponse],
    persisted: Row | None = None,
    agent_id: str | None = None,
    action_name: str | None = None,
) -> SandboxDecisionResponse:
    """Serialize a sandbox decision, persisted or synthetic."""

    return SandboxDecisionResponse(
        id=persisted["id"] if persisted is not None else None,
        profile_id=profile["id"],
        agent_id=persisted["agent_id"] if persisted is not None else agent_id,
        action_name=persisted["action_name"] if persisted is not None else action_name,
        decision=persisted["decision"] if persisted is not None else decision,
        reason=persisted["reason"] if persisted is not None else reason,
        violations=violations,
        provider_warning=_provider_warning(profile["provider_type"]),
        created_at=persisted["created_at"] if persisted is not None else None,
    )


def _validate_provider_type(provider_type: str) -> None:
    if provider_type not in SUPPORTED_SANDBOX_PROVIDER_TYPES:
        supported = ", ".join(sorted(SUPPORTED_SANDBOX_PROVIDER_TYPES))
        raise SandboxProfileValidationError(f"Unsupported sandbox provider_type. Supported values: {supported}.")


def _validate_status(status: str) -> None:
    if status not in SUPPORTED_SANDBOX_PROFILE_STATUSES:
        supported = ", ".join(sorted(SUPPORTED_SANDBOX_PROFILE_STATUSES))
        raise SandboxProfileValidationError(f"Unsupported sandbox profile status. Supported values: {supported}.")


def _provider_warning(provider_type: str) -> str | None:
    if provider_type == "subprocess":
        return SUBPROCESS_SANDBOX_WARNING
    return None


def _load_agent_os_sandbox_classes() -> tuple[Any, Any]:
    try:
        from agent_os.sandbox import ExecutionSandbox, SandboxConfig

        return ExecutionSandbox, SandboxConfig
    except ModuleNotFoundError:
        agent_os_src = Path(__file__).resolve().parents[4] / "agent-os" / "src"
        if str(agent_os_src) not in sys.path:
            sys.path.insert(0, str(agent_os_src))
        from agent_os.sandbox import ExecutionSandbox, SandboxConfig

        return ExecutionSandbox, SandboxConfig
