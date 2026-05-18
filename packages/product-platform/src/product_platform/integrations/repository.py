"""Integration registry repositories."""

from __future__ import annotations

import json
from product_platform.db.postgres import Connection, Row
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.integrations.models import (
    FrameworkAgentLinkRequest,
    FrameworkAgentResponse,
    FrameworkInstanceCreateRequest,
    FrameworkInstancePatchRequest,
    FrameworkInstanceResponse,
    FrameworkIntegrationResponse,
    IntegrationHealthCheckCreateRequest,
    IntegrationHealthCheckResponse,
    ProviderCredentialCreateRequest,
    ProviderCredentialResponse,
)
from product_platform.integrations.health import ProviderHealthResult
from product_platform.integrations.secrets import SecretProvider


REQUIRED_CONFIG_KEYS_BY_FRAMEWORK = {
    "openai_agents": {"project"},
    "langchain": {"callback_namespace"},
    "crewai": {"crew_name"},
}

SECRET_KEY_MARKERS = {
    "api_key",
    "apikey",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
}


class FrameworkIntegrationNotFoundError(ValueError):
    """Raised when a framework catalog entry is missing."""


class FrameworkInstanceNotFoundError(ValueError):
    """Raised when a framework connector instance is missing."""


class FrameworkInstanceConfigError(ValueError):
    """Raised when connector configuration is unsafe or invalid."""


class FrameworkAgentNotFoundError(ValueError):
    """Raised when a framework-agent link is missing."""


class FrameworkAgentValidationError(ValueError):
    """Raised when a framework-agent link is invalid."""


class ProviderCredentialNotFoundError(ValueError):
    """Raised when a provider credential is missing."""


class ProviderCredentialSecretError(ValueError):
    """Raised when a provider credential secret source cannot be used safely."""


class IntegrationRegistryRepository:
    """Read and manage framework integration metadata."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def list_frameworks(self, *, status: str | None = None) -> list[Row]:
        """List supported agent frameworks."""

        clauses = ["integration_type = ?"]
        values: list[object] = ["framework"]
        if status:
            clauses.append("status = ?")
            values.append(status)
        return self.connection.execute(
            f"""
            SELECT *
            FROM integrations
            WHERE {' AND '.join(clauses)}
            ORDER BY
                CASE status
                    WHEN 'primary_demo' THEN 0
                    WHEN 'supported' THEN 1
                    WHEN 'experimental' THEN 2
                    ELSE 3
                END,
                name ASC
            """,
            values,
        ).fetchall()

    def create_provider_credential(
        self,
        body: ProviderCredentialCreateRequest,
        *,
        created_by: str,
        secret_provider: SecretProvider,
    ) -> Row:
        """Create provider credential metadata after storing the raw secret externally."""

        if body.secret_ref is not None:
            secret_ref = body.secret_ref
        elif body.secret_value is not None:
            try:
                secret_ref = secret_provider.store(body.secret_value)
            except RuntimeError as exc:
                raise ProviderCredentialSecretError(
                    "Configured secret provider cannot store secret values; submit a pre-created secret_ref."
                ) from exc
        else:
            raise ProviderCredentialSecretError("Exactly one of secret_value or secret_ref is required.")
        now = utc_now_iso()
        credential_id = generate_id("provcred")
        self.connection.execute(
            """
            INSERT INTO provider_credentials (
                id, organization_id, name, provider_type, secret_ref,
                status, created_by, created_at, last_used_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                credential_id,
                self.organization_id,
                body.name,
                body.provider_type,
                secret_ref,
                body.status,
                created_by,
                now,
                None,
            ),
        )
        row = self.get_provider_credential(credential_id)
        if row is None:
            raise ProviderCredentialNotFoundError("Created provider credential could not be loaded.")
        return row

    def list_provider_credentials(
        self,
        *,
        provider_type: str | None = None,
        status: str | None = None,
    ) -> list[Row]:
        """List provider credential metadata for the organization."""

        clauses = ["organization_id = ?"]
        values: list[object] = [self.organization_id]
        if provider_type:
            clauses.append("provider_type = ?")
            values.append(provider_type)
        if status:
            clauses.append("status = ?")
            values.append(status)
        return self.connection.execute(
            f"""
            SELECT *
            FROM provider_credentials
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            """,
            values,
        ).fetchall()

    def get_provider_credential(self, credential_id: str) -> Row | None:
        """Get one provider credential in organization scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM provider_credentials
            WHERE id = ?
              AND organization_id = ?
            """,
            (credential_id, self.organization_id),
        ).fetchone()

    def mark_provider_credential_used(self, credential_id: str, used_at: str) -> None:
        """Record last credential use timestamp."""

        self.connection.execute(
            """
            UPDATE provider_credentials
            SET last_used_at = ?
            WHERE id = ?
              AND organization_id = ?
            """,
            (used_at, credential_id, self.organization_id),
        )

    def create_health_check(
        self,
        body: IntegrationHealthCheckCreateRequest,
        *,
        checked_at: str | None = None,
    ) -> Row:
        """Persist one health check."""

        health_id = generate_id("inthealth")
        now = checked_at or utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO integration_health_checks (
                id, organization_id, environment_id, target_type, target_id,
                status, latency_ms, message, details_json, checked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                health_id,
                self.organization_id,
                self.environment_id,
                body.target_type,
                body.target_id,
                body.status,
                body.latency_ms,
                body.message,
                json.dumps(body.details, sort_keys=True, separators=(",", ":")),
                now,
            ),
        )
        row = self.get_health_check(health_id)
        if row is None:
            raise ProviderCredentialNotFoundError("Created health check could not be loaded.")
        return row

    def create_provider_credential_health_check(
        self,
        credential: Row,
        result: ProviderHealthResult,
    ) -> Row:
        """Persist a provider credential health-test result."""

        checked_at = utc_now_iso()
        self.mark_provider_credential_used(credential["id"], checked_at)
        return self.create_health_check(
            IntegrationHealthCheckCreateRequest(
                target_type="provider_credential",
                target_id=credential["id"],
                status=result.status,
                latency_ms=result.latency_ms,
                message=result.message,
                details=result.details,
            ),
            checked_at=checked_at,
        )

    def list_health_checks(
        self,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Row]:
        """List health checks."""

        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if target_type:
            clauses.append("target_type = ?")
            values.append(target_type)
        if target_id:
            clauses.append("target_id = ?")
            values.append(target_id)
        if status:
            clauses.append("status = ?")
            values.append(status)
        values.append(limit)
        return self.connection.execute(
            f"""
            SELECT *
            FROM integration_health_checks
            WHERE {' AND '.join(clauses)}
            ORDER BY checked_at DESC, id DESC
            LIMIT ?
            """,
            values,
        ).fetchall()

    def latest_health_checks(self) -> list[Row]:
        """Return newest health check per target."""

        rows = self.list_health_checks(limit=500)
        seen: set[tuple[str, str]] = set()
        latest: list[Row] = []
        for row in rows:
            key = (row["target_type"], row["target_id"])
            if key in seen:
                continue
            seen.add(key)
            latest.append(row)
        return latest

    def run_scheduled_health_checks(self) -> list[Row]:
        """Record scheduled health checks for framework connector instances."""

        rows: list[Row] = []
        for instance in self.list_instances():
            status = "healthy" if instance["status"] == "active" else "failed"
            message = (
                "Connector instance accepted scheduled no-op validation."
                if status == "healthy"
                else "Connector instance is not active."
            )
            rows.append(
                self.create_health_check(
                    IntegrationHealthCheckCreateRequest(
                        target_type="framework_instance",
                        target_id=instance["id"],
                        status=status,
                        latency_ms=1,
                        message=message,
                        details={
                            "integration_id": instance["integration_id"],
                            "integration_name": instance["integration_name"],
                        },
                    )
                )
            )
        return rows

    def get_health_check(self, health_id: str) -> Row | None:
        """Get one health check."""

        return self.connection.execute(
            """
            SELECT *
            FROM integration_health_checks
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (health_id, self.organization_id, self.environment_id),
        ).fetchone()

    def get_framework(self, integration_id: str) -> Row | None:
        """Get one framework catalog entry."""

        return self.connection.execute(
            """
            SELECT *
            FROM integrations
            WHERE id = ?
              AND integration_type = ?
            """,
            (integration_id, "framework"),
        ).fetchone()

    def create_instance(self, body: FrameworkInstanceCreateRequest, *, created_by: str) -> Row:
        """Create a framework connector instance."""

        framework = self.get_framework(body.integration_id)
        if framework is None:
            raise FrameworkIntegrationNotFoundError("Framework integration not found.")
        _validate_framework_config(framework["id"], body.config)
        now = utc_now_iso()
        instance_id = generate_id("fwinst")
        self.connection.execute(
            """
            INSERT INTO integration_instances (
                id, organization_id, environment_id, integration_id, name,
                config_json, status, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                instance_id,
                self.organization_id,
                self.environment_id,
                body.integration_id,
                body.name,
                json.dumps(body.config, sort_keys=True, separators=(",", ":")),
                body.status,
                created_by,
                now,
                now,
            ),
        )
        row = self.get_instance(instance_id)
        if row is None:
            raise FrameworkInstanceNotFoundError("Created framework instance could not be loaded.")
        return row

    def patch_instance(self, instance_id: str, body: FrameworkInstancePatchRequest) -> Row:
        """Update a framework connector instance."""

        existing = self.get_instance(instance_id)
        if existing is None:
            raise FrameworkInstanceNotFoundError("Framework instance not found.")
        config = json.loads(existing["config_json"])
        if body.config is not None:
            _validate_framework_config(existing["integration_id"], body.config)
            config = body.config
        name = body.name or existing["name"]
        status = body.status or existing["status"]
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE integration_instances
            SET name = ?,
                config_json = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (
                name,
                json.dumps(config, sort_keys=True, separators=(",", ":")),
                status,
                now,
                instance_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        row = self.get_instance(instance_id)
        if row is None:
            raise FrameworkInstanceNotFoundError("Framework instance not found.")
        return row

    def list_instances(
        self,
        *,
        status: str | None = None,
        integration_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List framework connector instances in tenant scope."""

        clauses = ["i.organization_id = ?", "i.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if status:
            clauses.append("i.status = ?")
            values.append(status)
        if integration_id:
            clauses.append("i.integration_id = ?")
            values.append(integration_id)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT i.*, f.name AS integration_name
            FROM integration_instances i
            JOIN integrations f ON f.id = i.integration_id
            WHERE {' AND '.join(clauses)}
            ORDER BY i.updated_at DESC, i.created_at DESC, i.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_instance(self, instance_id: str) -> Row | None:
        """Get one framework connector instance in tenant scope."""

        return self.connection.execute(
            """
            SELECT i.*, f.name AS integration_name
            FROM integration_instances i
            JOIN integrations f ON f.id = i.integration_id
            WHERE i.id = ?
              AND i.organization_id = ?
              AND i.environment_id = ?
            """,
            (instance_id, self.organization_id, self.environment_id),
        ).fetchone()

    def link_agent(self, instance_id: str, body: FrameworkAgentLinkRequest) -> Row:
        """Link an agent to a framework connector instance."""

        instance = self.get_instance(instance_id)
        if instance is None:
            raise FrameworkInstanceNotFoundError("Framework instance not found.")
        if self._get_agent(body.agent_id) is None:
            raise FrameworkAgentValidationError("Agent is not visible in the selected environment.")
        now = utc_now_iso()
        existing = self._get_framework_agent_for_instance(instance_id, body.agent_id)
        if existing is None:
            link_id = generate_id("fwagent")
            self.connection.execute(
                """
                INSERT INTO framework_agents (
                    id, integration_instance_id, agent_id, framework_agent_ref,
                    sdk_version, telemetry_status, policy_coverage_status,
                    linked_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link_id,
                    instance_id,
                    body.agent_id,
                    body.framework_agent_ref,
                    body.sdk_version,
                    body.telemetry_status,
                    body.policy_coverage_status,
                    now,
                    now,
                ),
            )
        else:
            link_id = existing["id"]
            self.connection.execute(
                """
                UPDATE framework_agents
                SET framework_agent_ref = ?,
                    sdk_version = ?,
                    telemetry_status = ?,
                    policy_coverage_status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    body.framework_agent_ref,
                    body.sdk_version,
                    body.telemetry_status,
                    body.policy_coverage_status,
                    now,
                    link_id,
                ),
            )
        row = self.get_framework_agent(link_id)
        if row is None:
            raise FrameworkAgentNotFoundError("Created framework agent link could not be loaded.")
        return row

    def list_framework_agents(
        self,
        *,
        integration_instance_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[Row]:
        """List framework-agent links in tenant scope."""

        clauses = ["ii.organization_id = ?", "ii.environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if integration_instance_id:
            clauses.append("fa.integration_instance_id = ?")
            values.append(integration_instance_id)
        if agent_id:
            clauses.append("fa.agent_id = ?")
            values.append(agent_id)
        return self.connection.execute(
            f"""
            SELECT
                fa.*,
                f.name AS integration_name,
                a.name AS agent_name
            FROM framework_agents fa
            JOIN integration_instances ii ON ii.id = fa.integration_instance_id
            JOIN integrations f ON f.id = ii.integration_id
            JOIN agents a ON a.id = fa.agent_id
            WHERE {' AND '.join(clauses)}
            ORDER BY fa.updated_at DESC, fa.linked_at DESC, fa.id DESC
            """,
            values,
        ).fetchall()

    def get_framework_agent(self, link_id: str) -> Row | None:
        """Get one framework-agent link in tenant scope."""

        return self.connection.execute(
            """
            SELECT
                fa.*,
                f.name AS integration_name,
                a.name AS agent_name
            FROM framework_agents fa
            JOIN integration_instances ii ON ii.id = fa.integration_instance_id
            JOIN integrations f ON f.id = ii.integration_id
            JOIN agents a ON a.id = fa.agent_id
            WHERE fa.id = ?
              AND ii.organization_id = ?
              AND ii.environment_id = ?
            """,
            (link_id, self.organization_id, self.environment_id),
        ).fetchone()

    def unlink_framework_agent(self, link_id: str) -> Row:
        """Delete a framework-agent link."""

        row = self.get_framework_agent(link_id)
        if row is None:
            raise FrameworkAgentNotFoundError("Framework agent link not found.")
        self.connection.execute("DELETE FROM framework_agents WHERE id = ?", (link_id,))
        return row

    def _get_agent(self, agent_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM agents
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()

    def _get_framework_agent_for_instance(self, instance_id: str, agent_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM framework_agents
            WHERE integration_instance_id = ?
              AND agent_id = ?
            """,
            (instance_id, agent_id),
        ).fetchone()


def framework_integration_response(row: Row) -> FrameworkIntegrationResponse:
    """Build a framework catalog response."""

    return FrameworkIntegrationResponse(
        id=row["id"],
        integration_type=row["integration_type"],
        name=row["name"],
        description=row["description"],
        status=row["status"],
        supported_versions=list(json.loads(row["supported_versions_json"])),
        setup_doc_url=row["setup_doc_url"],
        example_path=row["example_path"],
        setup_snippet=row["setup_snippet"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def framework_instance_response(row: Row) -> FrameworkInstanceResponse:
    """Build a framework connector instance response."""

    return FrameworkInstanceResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        integration_id=row["integration_id"],
        integration_name=row["integration_name"],
        name=row["name"],
        config=json.loads(row["config_json"]),
        status=row["status"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def framework_agent_response(row: Row) -> FrameworkAgentResponse:
    """Build a framework-agent link response."""

    return FrameworkAgentResponse(
        id=row["id"],
        integration_instance_id=row["integration_instance_id"],
        integration_name=row["integration_name"],
        agent_id=row["agent_id"],
        agent_name=row["agent_name"],
        framework_agent_ref=row["framework_agent_ref"],
        sdk_version=row["sdk_version"],
        telemetry_status=row["telemetry_status"],
        policy_coverage_status=row["policy_coverage_status"],
        linked_at=row["linked_at"],
        updated_at=row["updated_at"],
    )


def provider_credential_response(row: Row) -> ProviderCredentialResponse:
    """Build a masked provider credential response."""

    return ProviderCredentialResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        name=row["name"],
        provider_type=row["provider_type"],
        secret_ref=row["secret_ref"],
        masked_secret="••••••••",
        status=row["status"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        last_used_at=row["last_used_at"],
    )


def integration_health_check_response(row: Row) -> IntegrationHealthCheckResponse:
    """Build a health check response."""

    return IntegrationHealthCheckResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        status=row["status"],
        latency_ms=int(row["latency_ms"]),
        message=row["message"],
        details=json.loads(row["details_json"]),
        checked_at=row["checked_at"],
    )


def _validate_framework_config(integration_id: str, config: dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise FrameworkInstanceConfigError("Connector config must be an object.")
    secret_path = _first_secret_like_path(config)
    if secret_path:
        raise FrameworkInstanceConfigError(f"Connector config must not contain secret-like value: {secret_path}.")
    required = REQUIRED_CONFIG_KEYS_BY_FRAMEWORK.get(integration_id, set())
    missing = sorted(key for key in required if not str(config.get(key, "")).strip())
    if missing:
        raise FrameworkInstanceConfigError(f"Connector config is missing required key(s): {', '.join(missing)}.")


def _first_secret_like_path(value: Any, *, path: str = "config") -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            child_path = f"{path}.{key}"
            if any(marker in key_text for marker in SECRET_KEY_MARKERS) and not key_text.endswith(("_id", "_ref")):
                return child_path
            secret_path = _first_secret_like_path(nested, path=child_path)
            if secret_path:
                return secret_path
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            secret_path = _first_secret_like_path(nested, path=f"{path}[{index}]")
            if secret_path:
                return secret_path
    elif isinstance(value, str):
        lowered = value.lower()
        if lowered.startswith("sk-") or "bearer " in lowered or "password=" in lowered:
            return path
    return None
