"""Artifact metadata repository."""

from __future__ import annotations

import base64
import binascii
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
    "workflow_run",
    "plugin_assessment",
    "audit_export",
    "compliance_report",
    "evidence_item",
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
                content_type, storage_uri, checksum, size_bytes, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                len(data),
                actor_id,
                now,
            ),
        )
        row = self.get(artifact_id)
        if row is None:
            raise ArtifactNotFoundError("Created artifact could not be loaded.")
        return row

    def list(self, *, artifact_type: str | None = None) -> list[Row]:
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
        return ArtifactDownloadResponse(
            artifact=artifact_response(self, row),
            content_base64=base64.b64encode(data).decode("ascii"),
            metadata={"checksum_verified": calculate_sha256(data) == row["checksum"]},
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

    def links_for_artifact(self, artifact_id: str) -> list[Row]:
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
        if self.get(artifact_id) is None:
            raise ArtifactNotFoundError("Artifact not found.")
        attestation_id = generate_id("aat")
        self.connection.execute(
            """
            INSERT INTO artifact_attestations (
                id, artifact_id, attested_by, statement, signature_ref, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                attestation_id,
                artifact_id,
                actor_id,
                body.statement,
                body.signature_ref,
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

    def attestations_for_artifact(self, artifact_id: str) -> list[Row]:
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
        size_bytes=row["size_bytes"],
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
