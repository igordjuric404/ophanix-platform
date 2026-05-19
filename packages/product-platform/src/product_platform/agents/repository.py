"""Repositories for product agent registry data."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from product_platform.db.postgres import Connection, Row

from product_platform.agents.models import (
    AgentCapabilityRequest,
    AgentCapabilityResponse,
    AgentDetailResponse,
    AgentHeartbeatResponse,
    AgentInventorySummary,
    AgentPatchRequest,
    AgentIdentityResponse,
    AgentPolicySelectionRequest,
    AgentPolicySelectionResponse,
    AgentProtocolResponse,
    AgentTimelineEvent,
    AgentRegistrationDraftCreate,
    AgentRegistrationDraftPatch,
    AgentRegistrationDraftResponse,
)
from product_platform.agents.identity import CreatedAgentIdentity
from product_platform.agents.lifecycle import AgentLifecycleAdapter
from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso


class DuplicateAgentNameError(ValueError):
    """Raised when an agent name is already used in a tenant environment."""


class AgentNotFoundError(ValueError):
    """Raised when an agent is not visible in the tenant scope."""


class AgentRegistryRepository:
    """Persistence for tenant-scoped agents."""

    def __init__(self, connection: Connection, organization_id: str, environment_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id

    def create_registration_draft(
        self,
        body: AgentRegistrationDraftCreate,
        *,
        created_by: str,
    ) -> Row:
        """Create a draft agent registration record."""

        self._ensure_unique_name(body.name)
        now = utc_now_iso()
        agent_id = generate_id("agent")
        self.connection.execute(
            """
            INSERT INTO agents (
                id, organization_id, environment_id, name, description, framework,
                runtime_type, endpoint_url, owner_user_id, sponsor_user_id, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                self.organization_id,
                self.environment_id,
                body.name,
                body.description,
                body.framework,
                body.runtime_type,
                body.endpoint_url,
                body.owner_user_id,
                body.sponsor_user_id,
                "draft",
                now,
                now,
            ),
        )
        self.connection.execute(
            """
            INSERT INTO agent_lifecycle_events (
                id, agent_id, previous_state, next_state, actor_id, reason,
                metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_id("life"),
                agent_id,
                None,
                "draft",
                created_by,
                "registration draft created",
                "{}",
                now,
            ),
        )
        row = self.get(agent_id)
        if row is None:
            raise AgentNotFoundError("Created agent draft could not be loaded.")
        return row

    def update_registration_draft(
        self,
        draft_id: str,
        body: AgentRegistrationDraftPatch,
    ) -> Row:
        """Update mutable fields on a draft agent registration."""

        existing = self.get(draft_id)
        if existing is None or existing["status"] != "draft":
            raise AgentNotFoundError("Registration draft not found.")
        values = body.model_dump(
            exclude_unset=True,
            exclude={"capabilities", "policy_selections"},
        )
        if not values:
            return existing
        if "name" in values and values["name"] != existing["name"]:
            self._ensure_unique_name(str(values["name"]), exclude_agent_id=draft_id)
        assignments = [f"{column} = ?" for column in values]
        sql_values = [values[column] for column in values]
        sql_values.extend([utc_now_iso(), draft_id, self.organization_id, self.environment_id])
        self.connection.execute(
            f"""
            UPDATE agents
            SET {', '.join(assignments)}, updated_at = ?
            WHERE id = ? AND organization_id = ? AND environment_id = ? AND deleted_at IS NULL
            """,
            sql_values,
        )
        row = self.get(draft_id)
        if row is None:
            raise AgentNotFoundError("Registration draft not found.")
        return row

    def replace_capabilities(
        self,
        agent_id: str,
        capabilities: list[AgentCapabilityRequest],
        *,
        requested_by: str,
    ) -> list[Row]:
        """Replace pending capability requests for a draft."""

        agent = self.get(agent_id)
        if agent is None or agent["status"] != "draft":
            raise AgentNotFoundError("Registration draft not found.")
        self.connection.execute("DELETE FROM agent_capabilities WHERE agent_id = ?", (agent_id,))
        now = utc_now_iso()
        seen: set[tuple[str, str]] = set()
        for capability in capabilities:
            key = (capability.capability_name, capability.resource_type)
            if key in seen:
                continue
            seen.add(key)
            self.connection.execute(
                """
                INSERT INTO agent_capabilities (
                    id, agent_id, capability_name, resource_type, status,
                    requested_by, approved_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_id("cap"),
                    agent_id,
                    capability.capability_name,
                    capability.resource_type,
                    "pending",
                    requested_by,
                    None,
                    now,
                ),
            )
        return self.list_capabilities(agent_id)

    def replace_policy_selections(
        self,
        agent_id: str,
        policy_selections: list[AgentPolicySelectionRequest],
    ) -> list[Row]:
        """Replace policy selections for a draft."""

        agent = self.get(agent_id)
        if agent is None or agent["status"] != "draft":
            raise AgentNotFoundError("Registration draft not found.")
        for selection in policy_selections:
            if not self._policy_exists(selection.policy_id):
                raise ValueError(f"Policy selection not found: {selection.policy_id}")
        self.connection.execute("DELETE FROM agent_policy_selections WHERE agent_id = ?", (agent_id,))
        now = utc_now_iso()
        seen: set[tuple[str, str]] = set()
        for selection in policy_selections:
            key = (selection.policy_id, selection.selection_type)
            if key in seen:
                continue
            seen.add(key)
            self.connection.execute(
                """
                INSERT INTO agent_policy_selections (
                    id, agent_id, policy_id, selection_type, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_id("aps"),
                    agent_id,
                    selection.policy_id,
                    selection.selection_type,
                    "selected",
                    now,
                ),
            )
        return self.list_policy_selections(agent_id)

    def get(self, agent_id: str) -> Row | None:
        """Get an agent by tenant scope."""

        return self.connection.execute(
            """
            SELECT * FROM agents
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()

    def create_identity(self, agent_id: str, created: CreatedAgentIdentity) -> Row:
        """Persist public identity metadata for an agent."""

        agent = self.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Registration draft not found.")
        existing = self.get_identity(agent_id)
        if existing is not None:
            return existing
        now = utc_now_iso()
        identity_id = generate_id("ident")
        self.connection.execute(
            """
            INSERT INTO agent_identities (
                id, agent_id, did, public_key_fingerprint, key_type,
                identity_status, bootstrap_material_json, bootstrap_retrieved_at,
                proof_type, issuer, audience, subject, environment_binding,
                trusted_root_id, trusted_root_version, key_reference,
                certificate_chain_json, proof_metadata_json, verified_at,
                rotated_at, revoked_at, rotation_count, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identity_id,
                agent_id,
                created.did,
                created.public_key_fingerprint,
                created.key_type,
                "active",
                None,
                now,
                created.proof.proof_type,
                created.proof.issuer,
                created.proof.audience,
                created.proof.subject,
                created.proof.environment_binding,
                created.proof.trusted_root_id,
                created.proof.trusted_root_version,
                created.proof.key_reference,
                json.dumps(created.proof.certificate_chain, sort_keys=True),
                json.dumps(created.proof.proof_metadata, sort_keys=True),
                created.proof.verified_at,
                None,
                None,
                0,
                now,
            ),
        )
        row = self.get_identity(agent_id)
        if row is None:
            raise AgentNotFoundError("Created identity could not be loaded.")
        return row

    def rotate_identity(
        self,
        agent_id: str,
        created: CreatedAgentIdentity,
        *,
        actor_id: str,
        reason: str,
    ) -> Row:
        """Rotate an agent identity and preserve historical evidence."""

        agent = self.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        existing = self.get_identity(agent_id)
        if existing is None:
            raise AgentNotFoundError("Agent identity not found.")
        now = utc_now_iso()
        rotation_count = int(existing["rotation_count"] or 0) + 1
        self.connection.execute(
            """
            UPDATE agent_identities
            SET did = ?,
                public_key_fingerprint = ?,
                key_type = ?,
                identity_status = ?,
                bootstrap_material_json = ?,
                bootstrap_retrieved_at = ?,
                proof_type = ?,
                issuer = ?,
                audience = ?,
                subject = ?,
                environment_binding = ?,
                trusted_root_id = ?,
                trusted_root_version = ?,
                key_reference = ?,
                certificate_chain_json = ?,
                proof_metadata_json = ?,
                verified_at = ?,
                rotated_at = ?,
                revoked_at = ?,
                rotation_count = ?
            WHERE agent_id = ?
            """,
            (
                created.did,
                created.public_key_fingerprint,
                created.key_type,
                "active",
                None,
                now,
                created.proof.proof_type,
                created.proof.issuer,
                created.proof.audience,
                created.proof.subject,
                created.proof.environment_binding,
                created.proof.trusted_root_id,
                created.proof.trusted_root_version,
                created.proof.key_reference,
                json.dumps(created.proof.certificate_chain, sort_keys=True),
                json.dumps(created.proof.proof_metadata, sort_keys=True),
                created.proof.verified_at,
                now,
                None,
                rotation_count,
                agent_id,
            ),
        )
        self.connection.execute(
            """
            INSERT INTO agent_lifecycle_events (
                id, agent_id, previous_state, next_state, actor_id, reason,
                metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_id("life"),
                agent_id,
                agent["status"],
                agent["status"],
                actor_id,
                "identity rotated",
                json.dumps(
                    {
                        "previous_did": existing["did"],
                        "previous_public_key_fingerprint": existing["public_key_fingerprint"],
                        "new_did": created.did,
                        "new_public_key_fingerprint": created.public_key_fingerprint,
                        "reason": reason,
                        "trusted_root_id": created.proof.trusted_root_id,
                        "trusted_root_version": created.proof.trusted_root_version,
                    },
                    sort_keys=True,
                ),
                now,
            ),
        )
        row = self.get_identity(agent_id)
        if row is None:
            raise AgentNotFoundError("Rotated identity could not be loaded.")
        return row

    def transition_status(
        self,
        agent_id: str,
        *,
        next_status: str,
        actor_id: str,
        reason: str | None = None,
        metadata_json: str = "{}",
    ) -> Row:
        """Transition an agent status and persist a lifecycle event."""

        agent = self.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        previous_status = agent["status"]
        AgentLifecycleAdapter().validate_transition(previous_status, next_status)
        now = utc_now_iso()
        decommissioned_at = now if next_status == "decommissioned" else agent["decommissioned_at"]
        self.connection.execute(
            """
            UPDATE agents
            SET status = ?, updated_at = ?, decommissioned_at = ?
            WHERE id = ? AND organization_id = ? AND environment_id = ? AND deleted_at IS NULL
            """,
            (
                next_status,
                now,
                decommissioned_at,
                agent_id,
                self.organization_id,
                self.environment_id,
            ),
        )
        self.connection.execute(
            """
            INSERT INTO agent_lifecycle_events (
                id, agent_id, previous_state, next_state, actor_id, reason,
                metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_id("life"),
                agent_id,
                previous_status,
                next_status,
                actor_id,
                reason,
                metadata_json,
                now,
            ),
        )
        row = self.get(agent_id)
        if row is None:
            raise AgentNotFoundError("Agent not found.")
        return row

    def approve_pending_capabilities(self, agent_id: str, *, approved_by: str) -> list[Row]:
        """Approve all pending capabilities for an agent."""

        agent = self.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        self.connection.execute(
            """
            UPDATE agent_capabilities
            SET status = ?, approved_by = ?
            WHERE agent_id = ? AND status = ?
            """,
            ("approved", approved_by, agent_id, "pending"),
        )
        return self.list_capabilities(agent_id)

    def change_owner(
        self,
        agent_id: str,
        *,
        new_owner_user_id: str,
        actor_id: str,
        reason: str | None = None,
    ) -> Row:
        """Transfer agent ownership and record a lifecycle event."""

        agent = self.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        now = utc_now_iso()
        old_owner = agent["owner_user_id"]
        self.connection.execute(
            """
            UPDATE agents
            SET owner_user_id = ?, updated_at = ?
            WHERE id = ? AND organization_id = ? AND environment_id = ? AND deleted_at IS NULL
            """,
            (new_owner_user_id, now, agent_id, self.organization_id, self.environment_id),
        )
        self.connection.execute(
            """
            INSERT INTO agent_lifecycle_events (
                id, agent_id, previous_state, next_state, actor_id, reason,
                metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generate_id("life"),
                agent_id,
                agent["status"],
                agent["status"],
                actor_id,
                reason,
                json.dumps({"old_owner": old_owner, "new_owner": new_owner_user_id}, sort_keys=True),
                now,
            ),
        )
        row = self.get(agent_id)
        if row is None:
            raise AgentNotFoundError("Agent not found.")
        return row

    def record_heartbeat(
        self,
        agent_id: str,
        *,
        status: str,
        metadata_json: dict,
    ) -> Row:
        """Persist heartbeat and update the agent freshness field."""

        agent = self.get(agent_id)
        if agent is None:
            raise AgentNotFoundError("Agent not found.")
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO agent_heartbeats (id, agent_id, observed_at, status, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (generate_id("hb"), agent_id, now, status, json.dumps(metadata_json, sort_keys=True)),
        )
        self.connection.execute(
            """
            UPDATE agents
            SET last_heartbeat_at = ?, updated_at = ?
            WHERE id = ? AND organization_id = ? AND environment_id = ? AND deleted_at IS NULL
            """,
            (now, now, agent_id, self.organization_id, self.environment_id),
        )
        row = self.get(agent_id)
        if row is None:
            raise AgentNotFoundError("Agent not found.")
        return row

    def orphan_candidates(self, *, threshold_hours: int) -> list[Row]:
        """Return active agents stale beyond threshold or missing an owner."""

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=threshold_hours)).isoformat()
        return self.connection.execute(
            """
            SELECT *
            FROM agents
            WHERE organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
              AND status = 'active'
              AND (
                owner_user_id = ''
                OR last_heartbeat_at IS NULL
                OR last_heartbeat_at < ?
              )
            ORDER BY name ASC, id ASC
            """,
            (self.organization_id, self.environment_id, cutoff),
        ).fetchall()

    def get_identity(self, agent_id: str) -> Row | None:
        """Get public identity metadata for an agent."""

        return self.connection.execute(
            """
            SELECT i.*
            FROM agent_identities i
            JOIN agents a ON a.id = i.agent_id
            WHERE i.agent_id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_capabilities(self, agent_id: str) -> list[Row]:
        """List capability requests for an agent."""

        return self.connection.execute(
            """
            SELECT c.*
            FROM agent_capabilities c
            JOIN agents a ON a.id = c.agent_id
            WHERE c.agent_id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            ORDER BY c.created_at ASC, c.id ASC
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchall()

    def list_policy_selections(self, agent_id: str) -> list[Row]:
        """List policy selections for an agent."""

        return self.connection.execute(
            """
            SELECT s.*
            FROM agent_policy_selections s
            JOIN agents a ON a.id = s.agent_id
            WHERE s.agent_id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            ORDER BY s.created_at ASC, s.id ASC
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchall()

    def list_inventory(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        owner_user_id: str | None = None,
        sponsor_user_id: str | None = None,
        framework: str | None = None,
        protocol: str | None = None,
        trust_tier: str | None = None,
        capability: str | None = None,
        environment_filter: str | None = None,
        sort: str = "name",
    ) -> list[Row]:
        """List inventory summaries for the selected environment."""

        clauses = [
            "a.organization_id = ?",
            "a.environment_id = ?",
            "a.deleted_at IS NULL",
        ]
        values: list[object] = [self.organization_id, self.environment_id]
        if environment_filter is not None:
            clauses.append("a.environment_id = ?")
            values.append(environment_filter)
        for column, value in [
            ("a.status", status),
            ("a.owner_user_id", owner_user_id),
            ("a.sponsor_user_id", sponsor_user_id),
            ("a.framework", framework),
            ("a.trust_tier", trust_tier),
        ]:
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        if protocol:
            clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM agent_protocols p
                    WHERE p.agent_id = a.id AND p.protocol = ?
                )
                """
            )
            values.append(protocol)
        if capability:
            clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM agent_capabilities c
                    WHERE c.agent_id = a.id AND c.capability_name = ?
                )
                """
            )
            values.append(capability)
        order_by = _inventory_order_by(sort)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                a.*,
                i.did,
                COALESCE(capabilities.capability_count, 0) AS capability_count,
                COALESCE(protocols.protocol_count, 0) AS protocol_count
            FROM agents a
            LEFT JOIN agent_identities i ON i.agent_id = a.id
            LEFT JOIN (
                SELECT agent_id, COUNT(*) AS capability_count
                FROM agent_capabilities
                GROUP BY agent_id
            ) capabilities ON capabilities.agent_id = a.id
            LEFT JOIN (
                SELECT agent_id, COUNT(*) AS protocol_count
                FROM agent_protocols
                GROUP BY agent_id
            ) protocols ON protocols.agent_id = a.id
            WHERE {' AND '.join(clauses)}
            {order_by}
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_inventory_summary(self, agent_id: str) -> Row | None:
        """Return one inventory summary row by ID."""

        rows = self.list_inventory(limit=1, offset=0)
        for row in rows:
            if row["id"] == agent_id:
                return row
        return self.connection.execute(
            """
            SELECT
                a.*,
                i.did,
                COALESCE(capabilities.capability_count, 0) AS capability_count,
                COALESCE(protocols.protocol_count, 0) AS protocol_count
            FROM agents a
            LEFT JOIN agent_identities i ON i.agent_id = a.id
            LEFT JOIN (
                SELECT agent_id, COUNT(*) AS capability_count
                FROM agent_capabilities
                GROUP BY agent_id
            ) capabilities ON capabilities.agent_id = a.id
            LEFT JOIN (
                SELECT agent_id, COUNT(*) AS protocol_count
                FROM agent_protocols
                GROUP BY agent_id
            ) protocols ON protocols.agent_id = a.id
            WHERE a.id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()

    def list_protocols(self, agent_id: str) -> list[Row]:
        """List protocol endpoints for an agent."""

        return self.connection.execute(
            """
            SELECT p.*
            FROM agent_protocols p
            JOIN agents a ON a.id = p.agent_id
            WHERE p.agent_id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            ORDER BY p.protocol ASC, p.endpoint ASC
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchall()

    def latest_heartbeat(self, agent_id: str) -> Row | None:
        """Return latest heartbeat row for an agent."""

        return self.connection.execute(
            """
            SELECT h.*
            FROM agent_heartbeats h
            JOIN agents a ON a.id = h.agent_id
            WHERE h.agent_id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            ORDER BY h.observed_at DESC, h.id DESC
            LIMIT 1
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchone()

    def patch_agent(self, agent_id: str, body: AgentPatchRequest) -> Row:
        """Patch editable agent fields."""

        existing = self.get(agent_id)
        if existing is None:
            raise AgentNotFoundError("Agent not found.")
        values = body.model_dump(exclude_unset=True)
        if not values:
            summary = self.get_inventory_summary(agent_id)
            if summary is None:
                raise AgentNotFoundError("Agent not found.")
            return summary
        assignments = [f"{column} = ?" for column in values]
        sql_values = [values[column] for column in values]
        sql_values.extend([utc_now_iso(), agent_id, self.organization_id, self.environment_id])
        self.connection.execute(
            f"""
            UPDATE agents
            SET {', '.join(assignments)}, updated_at = ?
            WHERE id = ? AND organization_id = ? AND environment_id = ? AND deleted_at IS NULL
            """,
            sql_values,
        )
        summary = self.get_inventory_summary(agent_id)
        if summary is None:
            raise AgentNotFoundError("Agent not found.")
        return summary

    def lifecycle_events(self, agent_id: str) -> list[Row]:
        """Return lifecycle events in chronological order."""

        return self.connection.execute(
            """
            SELECT e.*
            FROM agent_lifecycle_events e
            JOIN agents a ON a.id = e.agent_id
            WHERE e.agent_id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
              AND a.deleted_at IS NULL
            ORDER BY e.created_at ASC, e.id ASC
            """,
            (agent_id, self.organization_id, self.environment_id),
        ).fetchall()

    def _ensure_unique_name(self, name: str, *, exclude_agent_id: str | None = None) -> None:
        clauses = [
            "organization_id = ?",
            "environment_id = ?",
            "lower(name) = lower(?)",
            "deleted_at IS NULL",
        ]
        values: list[object] = [self.organization_id, self.environment_id, name]
        if exclude_agent_id is not None:
            clauses.append("id != ?")
            values.append(exclude_agent_id)
        row = self.connection.execute(
            f"SELECT id FROM agents WHERE {' AND '.join(clauses)} LIMIT 1",
            values,
        ).fetchone()
        if row is not None:
            raise DuplicateAgentNameError("Agent name already exists in this environment.")

    def _policy_exists(self, policy_id: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1 FROM policy_placeholders
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
            """,
            (policy_id, self.organization_id, self.environment_id),
        ).fetchone()
        return row is not None


def agent_registration_draft_response(
    row: Row,
    *,
    capabilities: list[Row] | None = None,
    policy_selections: list[Row] | None = None,
) -> AgentRegistrationDraftResponse:
    """Serialize a draft agent row."""

    return AgentRegistrationDraftResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        name=row["name"],
        description=row["description"],
        framework=row["framework"],
        runtime_type=row["runtime_type"],
        endpoint_url=row["endpoint_url"],
        owner_user_id=row["owner_user_id"],
        sponsor_user_id=row["sponsor_user_id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        capabilities=[agent_capability_response(row) for row in capabilities or []],
        policy_selections=[
            agent_policy_selection_response(row) for row in policy_selections or []
        ],
    )


def agent_identity_response(row: Row) -> AgentIdentityResponse:
    """Serialize persisted public identity metadata."""

    return AgentIdentityResponse(
        id=row["id"],
        agent_id=row["agent_id"],
        did=row["did"],
        public_key_fingerprint=row["public_key_fingerprint"],
        key_type=row["key_type"],
        identity_status=row["identity_status"],
        proof_type=row["proof_type"],
        issuer=row["issuer"],
        audience=row["audience"],
        subject=row["subject"],
        environment_binding=row["environment_binding"],
        trusted_root_id=row["trusted_root_id"],
        trusted_root_version=row["trusted_root_version"],
        key_reference=row["key_reference"],
        certificate_chain=json.loads(row["certificate_chain_json"]),
        proof_metadata=json.loads(row["proof_metadata_json"]),
        verified_at=row["verified_at"],
        rotated_at=row["rotated_at"],
        revoked_at=row["revoked_at"],
        rotation_count=int(row["rotation_count"] or 0),
        created_at=row["created_at"],
    )


def agent_capability_response(row: Row) -> AgentCapabilityResponse:
    """Serialize a capability request row."""

    return AgentCapabilityResponse(
        id=row["id"],
        agent_id=row["agent_id"],
        capability_name=row["capability_name"],
        resource_type=row["resource_type"],
        status=row["status"],
        requested_by=row["requested_by"],
        approved_by=row["approved_by"],
        created_at=row["created_at"],
    )


def agent_policy_selection_response(row: Row) -> AgentPolicySelectionResponse:
    """Serialize a policy selection row."""

    return AgentPolicySelectionResponse(
        id=row["id"],
        agent_id=row["agent_id"],
        policy_id=row["policy_id"],
        selection_type=row["selection_type"],
        status=row["status"],
        created_at=row["created_at"],
    )


def agent_inventory_summary(row: Row) -> AgentInventorySummary:
    """Serialize an agent inventory summary row."""

    return AgentInventorySummary(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        name=row["name"],
        description=row["description"],
        framework=row["framework"],
        runtime_type=row["runtime_type"],
        endpoint_url=row["endpoint_url"],
        owner_user_id=row["owner_user_id"],
        sponsor_user_id=row["sponsor_user_id"],
        status=row["status"],
        trust_score=row["trust_score"],
        trust_tier=row["trust_tier"],
        credential_status=row["credential_status"],
        credential_expires_at=row["credential_expires_at"],
        last_heartbeat_at=row["last_heartbeat_at"],
        did=row["did"],
        capability_count=int(row["capability_count"]),
        protocol_count=int(row["protocol_count"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def agent_protocol_response(row: Row) -> AgentProtocolResponse:
    """Serialize protocol rows."""

    return AgentProtocolResponse(
        id=row["id"],
        agent_id=row["agent_id"],
        protocol=row["protocol"],
        endpoint=row["endpoint"],
        status=row["status"],
    )


def agent_heartbeat_response(row: Row) -> AgentHeartbeatResponse:
    """Serialize heartbeat rows."""

    return AgentHeartbeatResponse(
        id=row["id"],
        agent_id=row["agent_id"],
        observed_at=row["observed_at"],
        status=row["status"],
        metadata_json=json.loads(row["metadata_json"]),
    )


def agent_detail_response(repository: AgentRegistryRepository, row: Row) -> AgentDetailResponse:
    """Build an aggregate detail response from repository sections."""

    agent_id = row["id"]
    lifecycle_rows = repository.lifecycle_events(agent_id)
    latest_lifecycle = lifecycle_rows[-1] if lifecycle_rows else None
    states: dict[str, int] = {}
    for lifecycle_row in lifecycle_rows:
        state = lifecycle_row["next_state"]
        states[state] = states.get(state, 0) + 1
    heartbeat = repository.latest_heartbeat(agent_id)
    identity = repository.get_identity(agent_id)
    return AgentDetailResponse(
        summary=agent_inventory_summary(row),
        identity=agent_identity_response(identity) if identity else None,
        capabilities=[
            agent_capability_response(capability)
            for capability in repository.list_capabilities(agent_id)
        ],
        protocols=[agent_protocol_response(protocol) for protocol in repository.list_protocols(agent_id)],
        policy_selections=[
            agent_policy_selection_response(selection)
            for selection in repository.list_policy_selections(agent_id)
        ],
        latest_heartbeat=agent_heartbeat_response(heartbeat) if heartbeat else None,
        lifecycle_summary={
            "current_state": row["status"],
            "latest_transition_at": latest_lifecycle["created_at"] if latest_lifecycle else None,
            "event_count": len(lifecycle_rows),
            "states": states,
        },
    )


def lifecycle_timeline_event(row: Row) -> AgentTimelineEvent:
    """Serialize lifecycle row as a timeline event."""

    return AgentTimelineEvent(
        id=row["id"],
        source="lifecycle",
        event_type="agent.lifecycle",
        created_at=row["created_at"],
        previous_state=row["previous_state"],
        next_state=row["next_state"],
        actor_id=row["actor_id"],
        payload_json=json.loads(row["metadata_json"]),
    )


def _inventory_order_by(sort: str) -> str:
    descending = sort.startswith("-")
    field = sort[1:] if descending else sort
    columns = {
        "name": "lower(a.name)",
        "status": "a.status",
        "trust_score": "a.trust_score",
        "credential_expiry": "a.credential_expires_at",
        "last_heartbeat": "a.last_heartbeat_at",
    }
    column = columns.get(field, "lower(a.name)")
    direction = "DESC" if descending else "ASC"
    if field == "name":
        return f"ORDER BY {column} {direction}, a.id ASC"
    return f"ORDER BY ({column} IS NULL) ASC, {column} {direction}, lower(a.name) ASC, a.id ASC"
