"""Artifact metadata repository."""

from __future__ import annotations

import base64
import builtins
import binascii
import json
import re
from product_platform.db.postgres import Connection, IntegrityError, Row

from product_platform.artifacts.models import (
    ArtifactAttestationCreateRequest,
    ArtifactAttestationResponse,
    ArtifactCreateRequest,
    ArtifactDownloadResponse,
    ArtifactLinkCreateRequest,
    ArtifactLinkResponse,
    ArtifactResponse,
)
from product_platform.artifacts.storage import LocalArtifactProvider, calculate_sha256
from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso


SUPPORTED_ARTIFACT_TARGET_TYPES = {
    "audit_export",
    "compliance_report",
    "evidence_item",
    "mcp_tool_call",
    "observability_eval_result",
    "observability_span",
    "observability_trace",
    "plugin_assessment",
    "runtime_action",
    "runtime_session",
    "tool_runtime_action",
    "workflow_run",
}


class ArtifactNotFoundError(ValueError):
    """Raised when an artifact is outside tenant scope."""


class ArtifactValidationError(ValueError):
    """Raised when artifact metadata is invalid."""


class ArtifactRepository:
    """Store artifact metadata and links."""

    def __init__(
        self,
        connection: Connection,
        organization_id: str,
        environment_id: str,
        storage: LocalArtifactProvider,
        *,
        max_size_bytes: int | None = None,
    ) -> None:
        self.connection = connection
        self.organization_id = organization_id
        self.environment_id = environment_id
        self.storage = storage
        self.max_size_bytes = max_size_bytes

    def create(self, body: ArtifactCreateRequest, *, actor_id: str) -> Row:
        artifact_id = generate_id("art")
        data = _decode_base64(body.content_base64, max_size_bytes=self.max_size_bytes)
        key = f"{self.organization_id}/{self.environment_id}/{artifact_id}/{_safe_name(body.name)}"
        storage_uri = self.storage.upload(key, data)
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO artifacts (
                id, organization_id, environment_id, artifact_type, name,
                content_type, storage_uri, checksum, digest_algorithm, size_bytes,
                retention_policy, redaction_classification, provenance_json,
                created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                self.organization_id,
                self.environment_id,
                body.artifact_type,
                body.name,
                body.content_type,
                storage_uri,
                calculate_sha256(data),
                "sha256",
                len(data),
                body.retention_policy,
                body.redaction_classification,
                json.dumps(body.provenance, sort_keys=True, separators=(",", ":")),
                actor_id,
                now,
            ),
        )
        row = self.get(artifact_id)
        if row is None:
            raise ArtifactNotFoundError("Created artifact could not be loaded.")
        return row

    def list(self, *, artifact_type: str | None = None) -> builtins.list[Row]:
        clauses = ["organization_id = ?", "environment_id = ?"]
        values: list[object] = [self.organization_id, self.environment_id]
        if artifact_type:
            clauses.append("artifact_type = ?")
            values.append(artifact_type)
        return self.connection.execute(
            f"""
            SELECT *
            FROM artifacts
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            """,
            values,
        ).fetchall()

    def get(self, artifact_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM artifacts
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
            """,
            (artifact_id, self.organization_id, self.environment_id),
        ).fetchone()

    def download(self, artifact_id: str) -> ArtifactDownloadResponse:
        row = self.get(artifact_id)
        if row is None:
            raise ArtifactNotFoundError("Artifact not found.")
        data = self.storage.download(row["storage_uri"])
        digest_verified = calculate_sha256(data) == row["checksum"]
        return ArtifactDownloadResponse(
            artifact=artifact_response(self, row),
            content_base64=base64.b64encode(data).decode("ascii"),
            metadata={
                "checksum_verified": digest_verified,
                "digest_verified": digest_verified,
                "digest_algorithm": row["digest_algorithm"] if "digest_algorithm" in row.keys() else "sha256",
            },
        )

    def create_link(self, artifact_id: str, body: ArtifactLinkCreateRequest) -> Row:
        if self.get(artifact_id) is None:
            raise ArtifactNotFoundError("Artifact not found.")
        if body.target_type not in SUPPORTED_ARTIFACT_TARGET_TYPES:
            supported = ", ".join(sorted(SUPPORTED_ARTIFACT_TARGET_TYPES))
            raise ArtifactValidationError(f"target_type must be one of: {supported}.")
        self._validate_target(body.target_type, body.target_id)
        link_id = generate_id("alink")
        try:
            self.connection.execute(
                """
                INSERT INTO artifact_links (
                    id, artifact_id, target_type, target_id, link_type, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (link_id, artifact_id, body.target_type, body.target_id, body.link_type, utc_now_iso()),
            )
        except IntegrityError:
            row = self.connection.execute(
                """
                SELECT *
                FROM artifact_links
                WHERE artifact_id = ?
                  AND target_type = ?
                  AND target_id = ?
                  AND link_type = ?
                """,
                (artifact_id, body.target_type, body.target_id, body.link_type),
            ).fetchone()
            if row is not None:
                return row
            raise
        row = self.connection.execute("SELECT * FROM artifact_links WHERE id = ?", (link_id,)).fetchone()
        if row is None:
            raise ArtifactNotFoundError("Artifact link could not be loaded.")
        return row

    def links_for_artifact(self, artifact_id: str) -> builtins.list[Row]:
        return self.connection.execute(
            """
            SELECT *
            FROM artifact_links
            WHERE artifact_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (artifact_id,),
        ).fetchall()

    def create_attestation(
        self,
        artifact_id: str,
        body: ArtifactAttestationCreateRequest,
        *,
        actor_id: str,
    ) -> Row:
        artifact = self.get(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundError("Artifact not found.")
        attestation_id = generate_id("aat")
        self.connection.execute(
            """
            INSERT INTO artifact_attestations (
                id, artifact_id, attested_by, statement, signature_ref,
                artifact_checksum, digest_algorithm, signer_user_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attestation_id,
                artifact_id,
                actor_id,
                body.statement,
                body.signature_ref,
                artifact["checksum"],
                artifact["digest_algorithm"] if "digest_algorithm" in artifact.keys() else "sha256",
                actor_id,
                utc_now_iso(),
            ),
        )
        row = self.connection.execute(
            """
            SELECT aa.*
            FROM artifact_attestations aa
            JOIN artifacts a ON a.id = aa.artifact_id
            WHERE aa.id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
            """,
            (attestation_id, self.organization_id, self.environment_id),
        ).fetchone()
        if row is None:
            raise ArtifactNotFoundError("Created artifact attestation could not be loaded.")
        return row

    def attestations_for_artifact(self, artifact_id: str) -> builtins.list[Row]:
        return self.connection.execute(
            """
            SELECT aa.*
            FROM artifact_attestations aa
            JOIN artifacts a ON a.id = aa.artifact_id
            WHERE aa.artifact_id = ?
              AND a.organization_id = ?
              AND a.environment_id = ?
            ORDER BY aa.created_at DESC, aa.id DESC
            """,
            (artifact_id, self.organization_id, self.environment_id),
        ).fetchall()

    def _validate_target(self, target_type: str, target_id: str) -> None:
        queries = {
            "workflow_run": (
                "SELECT 1 FROM workflow_runs WHERE id = ? AND organization_id = ? AND environment_id = ?",
                (target_id, self.organization_id, self.environment_id),
            ),
            "audit_export": (
                "SELECT 1 FROM audit_exports WHERE id = ? AND organization_id = ? AND environment_id = ?",
                (target_id, self.organization_id, self.environment_id),
            ),
            "compliance_report": (
                "SELECT 1 FROM compliance_reports WHERE id = ? AND organization_id = ? AND environment_id = ?",
                (target_id, self.organization_id, self.environment_id),
            ),
            "evidence_item": (
                "SELECT 1 FROM evidence_items WHERE id = ? AND organization_id = ? AND environment_id = ?",
                (target_id, self.organization_id, self.environment_id),
            ),
            "runtime_session": (
                "SELECT 1 FROM runtime_sessions WHERE id = ? AND organization_id = ? AND environment_id = ?",
                (target_id, self.organization_id, self.environment_id),
            ),
            "runtime_action": (
                """
                SELECT 1
                FROM runtime_actions a
                JOIN runtime_sessions s ON s.id = a.session_id
                WHERE a.id = ?
                  AND s.organization_id = ?
                  AND s.environment_id = ?
                """,
                (target_id, self.organization_id, self.environment_id),
            ),
            "tool_runtime_action": (
                "SELECT 1 FROM tool_runtime_actions WHERE id = ? AND organization_id = ? AND environment_id = ?",
                (target_id, self.organization_id, self.environment_id),
            ),
            "mcp_tool_call": (
                "SELECT 1 FROM mcp_tool_calls WHERE id = ? AND organization_id = ? AND environment_id = ?",
                (target_id, self.organization_id, self.environment_id),
            ),
            "observability_trace": (
                """
                SELECT 1
                FROM observability_traces
                WHERE (id = ? OR trace_id = ?)
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (target_id, target_id, self.organization_id, self.environment_id),
            ),
            "observability_span": (
                """
                SELECT 1
                FROM observability_spans
                WHERE (id = ? OR span_id = ?)
                  AND organization_id = ?
                  AND environment_id = ?
                """,
                (target_id, target_id, self.organization_id, self.environment_id),
            ),
            "observability_eval_result": (
                "SELECT 1 FROM observability_eval_results WHERE id = ? AND organization_id = ? AND environment_id = ?",
                (target_id, self.organization_id, self.environment_id),
            ),
            "plugin_assessment": (
                """
                SELECT 1
                FROM plugin_quality_assessments qa
                JOIN plugin_versions pv ON pv.id = qa.plugin_version_id
                JOIN plugins p ON p.id = pv.plugin_id
                WHERE qa.id = ? AND p.organization_id = ?
                """,
                (target_id, self.organization_id),
            ),
        }
        sql, values = queries[target_type]
        if self.connection.execute(sql, values).fetchone() is None:
            raise ArtifactValidationError("Artifact link target was not found.")


def artifact_response(repository: ArtifactRepository, row: Row) -> ArtifactResponse:
    return ArtifactResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        environment_id=row["environment_id"],
        artifact_type=row["artifact_type"],
        name=row["name"],
        content_type=row["content_type"],
        storage_uri=row["storage_uri"],
        checksum=row["checksum"],
        digest_algorithm=row["digest_algorithm"] if "digest_algorithm" in row.keys() else "sha256",
        size_bytes=row["size_bytes"],
        retention_policy=row["retention_policy"] if "retention_policy" in row.keys() else "standard",
        redaction_classification=row["redaction_classification"]
        if "redaction_classification" in row.keys()
        else "internal",
        provenance=json.loads(row["provenance_json"]) if "provenance_json" in row.keys() else {},
        created_by=row["created_by"],
        created_at=row["created_at"],
        links=[artifact_link_response(link) for link in repository.links_for_artifact(row["id"])],
        attestations=[
            artifact_attestation_response(attestation)
            for attestation in repository.attestations_for_artifact(row["id"])
        ],
    )


def artifact_link_response(row: Row) -> ArtifactLinkResponse:
    return ArtifactLinkResponse(
        id=row["id"],
        artifact_id=row["artifact_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        link_type=row["link_type"],
        created_at=row["created_at"],
    )


def artifact_attestation_response(row: Row) -> ArtifactAttestationResponse:
    return ArtifactAttestationResponse(
        id=row["id"],
        artifact_id=row["artifact_id"],
        attested_by=row["attested_by"],
        statement=row["statement"],
        signature_ref=row["signature_ref"],
        artifact_checksum=row["artifact_checksum"] if "artifact_checksum" in row.keys() else None,
        digest_algorithm=row["digest_algorithm"] if "digest_algorithm" in row.keys() else "sha256",
        signer_user_id=row["signer_user_id"] if "signer_user_id" in row.keys() else row["attested_by"],
        created_at=row["created_at"],
    )


def _decode_base64(content: str, *, max_size_bytes: int | None = None) -> bytes:
    if max_size_bytes is not None and max_size_bytes > 0:
        max_encoded_length = ((max_size_bytes + 2) // 3) * 4
        if len(content) > max_encoded_length + 4:
            raise ArtifactValidationError("Artifact content exceeds the configured size limit.")
    try:
        data = base64.b64decode(content, validate=True)
    except binascii.Error as exc:
        raise ArtifactValidationError("content_base64 must be valid base64.") from exc
    if max_size_bytes is not None and max_size_bytes > 0 and len(data) > max_size_bytes:
        raise ArtifactValidationError("Artifact content exceeds the configured size limit.")
    return data


def _safe_name(name: str) -> str:
    if "/" in name or "\\" in name or ".." in name:
        raise ArtifactValidationError("Artifact name must not contain path separators.")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip()) or "artifact.bin"
