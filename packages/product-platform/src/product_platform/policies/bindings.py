"""Policy binding persistence and target validation."""

from __future__ import annotations

import hashlib
from product_platform.db.postgres import Connection, Row

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.policies.models import (
    POLICY_BINDING_TARGET_TYPES,
    PolicyBindingCreateRequest,
    PolicyBindingPatchRequest,
    PolicyBindingPromoteRequest,
    PolicyBindingResolutionContext,
    PolicyBindingResponse,
    PolicyExceptionCreateRequest,
    PolicyExceptionResponse,
)
from product_platform.policies.repository import PolicyNotFoundError, PolicyRepository


class PolicyBindingNotFoundError(ValueError):
    """Raised when a binding is not visible in the tenant scope."""


class PolicyBindingTargetError(ValueError):
    """Raised when a binding target is invalid for the tenant scope."""


class PolicyBindingRepository:
    """Environment-scoped policy binding repository."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_binding(self, body: PolicyBindingCreateRequest, *, actor_id: str) -> Row:
        """Create a binding after validating target and policy version scope."""

        policy_repository = PolicyRepository(self.connection, self.organization_id)
        policy = policy_repository.get_policy(body.policy_id)
        if policy is None:
            raise PolicyNotFoundError("Policy not found.")
        version = (
            policy_repository.get_version(body.policy_id, body.policy_version_id)
            if body.policy_version_id
            else policy_repository.latest_export_version(body.policy_id)
        )
        if version is None:
            raise PolicyNotFoundError("Policy version not found.")
        self._validate_target(body.target_type, body.target_id)
        now = utc_now_iso()
        binding_id = generate_id("pbind")
        self.connection.execute(
            """
            INSERT INTO policy_bindings (
                id, organization_id, environment_id, policy_id, policy_version_id,
                target_type, target_id, mode, rollout_percentage, priority, status,
                created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                binding_id,
                self.organization_id,
                self.environment_id,
                body.policy_id,
                version["id"],
                body.target_type,
                body.target_id,
                body.mode,
                body.rollout_percentage,
                body.priority,
                body.status,
                actor_id,
                now,
                now,
            ),
        )
        row = self.get_binding(binding_id)
        if row is None:
            raise PolicyBindingNotFoundError("Created policy binding could not be loaded.")
        return row

    def list_bindings(
        self,
        *,
        policy_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        status: str | None = None,
    ) -> list[Row]:
        """List bindings in the selected organization/environment."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        for column, value in [
            ("policy_id", policy_id),
            ("target_type", target_type),
            ("target_id", target_id),
            ("status", status),
        ]:
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        return self.connection.execute(
            f"""
            SELECT *
            FROM policy_bindings
            WHERE {' AND '.join(clauses)}
            ORDER BY priority DESC, created_at DESC, id DESC
            """,
            values,
        ).fetchall()

    def get_binding(self, binding_id: str) -> Row | None:
        """Get one binding by tenant scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM policy_bindings
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (binding_id, self.organization_id, self.environment_id),
        ).fetchone()

    def update_binding(self, binding_id: str, body: PolicyBindingPatchRequest) -> Row:
        """Patch mutable binding fields."""

        existing = self.get_binding(binding_id)
        if existing is None:
            raise PolicyBindingNotFoundError("Policy binding not found.")
        values = body.model_dump(exclude_unset=True)
        if not values:
            return existing
        assignments = [f"{column} = ?" for column in values]
        sql_values = [values[column] for column in values]
        sql_values.extend([utc_now_iso(), binding_id, self.organization_id, self.environment_id])
        self.connection.execute(
            f"""
            UPDATE policy_bindings
            SET {', '.join(assignments)}, updated_at = ?
            WHERE id = ? AND organization_id = ? AND environment_id = ?
            """,
            sql_values,
        )
        row = self.get_binding(binding_id)
        if row is None:
            raise PolicyBindingNotFoundError("Policy binding not found.")
        return row

    def delete_binding(self, binding_id: str) -> Row:
        """Soft-delete a binding through status."""

        row = self.update_binding(
            binding_id,
            PolicyBindingPatchRequest(status="deleted"),
        )
        return row

    def promote_binding(
        self,
        binding_id: str,
        body: PolicyBindingPromoteRequest,
        *,
        actor_id: str,
    ) -> Row:
        """Promote a binding mode or rollout percentage and record a rollout event."""

        existing = self.get_binding(binding_id)
        if existing is None:
            raise PolicyBindingNotFoundError("Policy binding not found.")
        previous_percentage = int(existing["rollout_percentage"])
        next_percentage = (
            body.rollout_percentage
            if body.rollout_percentage is not None
            else previous_percentage
        )
        patch = PolicyBindingPatchRequest(
            mode=body.mode,
            rollout_percentage=body.rollout_percentage,
        )
        updated = self.update_binding(binding_id, patch)
        self.connection.execute(
            """
            INSERT INTO policy_rollout_events (
                id, binding_id, previous_percentage, next_percentage,
                actor_id, reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_id("proll"),
                binding_id,
                previous_percentage,
                next_percentage,
                actor_id,
                body.reason,
                utc_now_iso(),
            ),
        )
        return updated

    def create_exception(
        self,
        binding_id: str,
        body: PolicyExceptionCreateRequest,
        *,
        actor_id: str,
    ) -> Row:
        """Create an exception for a binding."""

        binding = self.get_binding(binding_id)
        if binding is None:
            raise PolicyBindingNotFoundError("Policy binding not found.")
        target_type = body.target_type or binding["target_type"]
        target_id = body.target_id or binding["target_id"]
        self._validate_target(target_type, target_id)
        exception_id = generate_id("pex")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO policy_exceptions (
                id, binding_id, target_type, target_id, reason, expires_at,
                created_by, approved_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exception_id,
                binding_id,
                target_type,
                target_id,
                body.reason,
                body.expires_at,
                actor_id,
                body.approved_by,
                now,
            ),
        )
        row = self.connection.execute(
            """
            SELECT e.*
            FROM policy_exceptions e
            JOIN policy_bindings b ON b.id = e.binding_id
            WHERE e.id = ?
              AND b.organization_id = ?
              AND b.environment_id = ?
            """,
            (exception_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise PolicyBindingNotFoundError("Created policy exception could not be loaded.")
        return row

    def list_exceptions(self, *, binding_id: str | None = None) -> list[Row]:
        """List exceptions for visible bindings."""

        clauses = ["b.organization_id = ?", "b.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if binding_id:
            clauses.append("e.binding_id = ?")
            values.append(binding_id)
        return self.connection.execute(
            f"""
            SELECT e.*
            FROM policy_exceptions e
            JOIN policy_bindings b ON b.id = e.binding_id
            WHERE {' AND '.join(clauses)}
            ORDER BY e.created_at DESC, e.id DESC
            """,
            values,
        ).fetchall()

    def resolve_bindings(
        self,
        context: PolicyBindingResolutionContext,
        *,
        now: str | None = None,
    ) -> list[Row]:
        """Resolve bindings that apply to an evaluation context."""

        if context.organization_id != self.organization_id:
            return []
        if context.environment_id != self.environment_id:
            return []
        rows = self.list_bindings(status="active")
        applicable: list[tuple[int, int, str, Row]] = []
        for row in rows:
            if row["mode"] == "disabled":
                continue
            specificity = _target_specificity(row, context)
            if specificity < 0:
                continue
            if not _rollout_includes(row, context):
                continue
            if self._has_active_exception(row, context, now=now):
                continue
            applicable.append((int(row["priority"]), specificity, row["id"], row))
        applicable.sort(key=lambda item: (-item[0], -item[1], item[2]))
        return [row for _, _, _, row in applicable]

    def _has_active_exception(
        self,
        binding: Row,
        context: PolicyBindingResolutionContext,
        *,
        now: str | None,
    ) -> bool:
        rows = self.connection.execute(
            """
            SELECT *
            FROM policy_exceptions
            WHERE binding_id = ?
            """,
            (binding["id"],),
        ).fetchall()
        timestamp = now or utc_now_iso()
        for row in rows:
            expires_at = row["expires_at"]
            if expires_at is not None and expires_at <= timestamp:
                continue
            if row["target_type"] == context.target_type and row["target_id"] == context.target_id:
                return True
            if context.agent_id and row["target_type"] == "agent" and row["target_id"] == context.agent_id:
                return True
        return False

    def _validate_target(self, target_type: str, target_id: str) -> None:
        if target_type not in POLICY_BINDING_TARGET_TYPES:
            raise PolicyBindingTargetError("Invalid policy binding target type.")
        if target_type == "agent":
            row = self.connection.execute(
                """
                SELECT id
                FROM agents
                WHERE id = ?
                  AND organization_id = ?
                  AND environment_id = ?
                  AND deleted_at IS NULL
                """,
                (target_id, self.organization_id, self.environment_id),
            ).fetchone()
            if row is None:
                raise PolicyBindingTargetError("Agent target not found in current environment.")
            return
        if target_type == "environment":
            row = self.connection.execute(
                """
                SELECT id
                FROM environments
                WHERE id = ?
                  AND organization_id = ?
                  AND deleted_at IS NULL
                """,
                (target_id, self.organization_id),
            ).fetchone()
            if row is None:
                raise PolicyBindingTargetError("Environment target not found in current organization.")


def policy_binding_response(row: Row) -> PolicyBindingResponse:
    """Serialize a policy binding row."""

    return PolicyBindingResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        policy_id=row["policy_id"],
        policy_version_id=row["policy_version_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        mode=row["mode"],
        rollout_percentage=row["rollout_percentage"],
        priority=row["priority"],
        status=row["status"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def policy_exception_response(row: Row) -> PolicyExceptionResponse:
    """Serialize a policy exception row."""

    return PolicyExceptionResponse(
        id=row["id"],
        binding_id=row["binding_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        reason=row["reason"],
        expires_at=row["expires_at"],
        created_by=row["created_by"],
        approved_by=row["approved_by"],
        created_at=row["created_at"],
    )


def _target_specificity(row: Row, context: PolicyBindingResolutionContext) -> int:
    if row["target_type"] == context.target_type and row["target_id"] == context.target_id:
        return 100
    if context.agent_id and row["target_type"] == "agent" and row["target_id"] == context.agent_id:
        return 90
    if row["target_type"] == "environment" and row["target_id"] == context.environment_id:
        return 10
    return -1


def _rollout_includes(row: Row, context: PolicyBindingResolutionContext) -> bool:
    percentage = int(row["rollout_percentage"])
    if percentage >= 100:
        return True
    if percentage <= 0:
        return False
    seed = context.correlation_id or context.agent_id or context.target_id
    digest = hashlib.sha256(f"{row['id']}:{seed}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < percentage
