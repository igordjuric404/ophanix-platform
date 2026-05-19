"""Marketplace catalog persistence."""

from __future__ import annotations

import json
from product_platform.db.postgres import Connection, IntegrityError, Row
from typing import Any

from product_platform.db.ids import generate_id
from product_platform.db.time import utc_now_iso
from product_platform.marketplace.models import (
    PluginInstallationCreateRequest,
    PluginInstallationResponse,
    NormalizedPluginManifest,
    PluginImportRequest,
    PluginPolicyCheckRequest,
    PluginPolicyResultResponse,
    PluginQualityAssessmentResponse,
    PluginResponse,
    PluginReviewDecisionRequest,
    PluginReviewResponse,
    PluginReviewSubmitRequest,
    PluginSigningKeyCreateRequest,
    PluginSigningKeyResponse,
    PluginTrustEventResponse,
    PluginTrustRecomputeRequest,
    PluginVersionResponse,
    normalize_plugin_manifest,
)
from product_platform.marketplace.policy import PluginPolicyInput, evaluate_plugin_policy
from product_platform.marketplace.quality import assess_plugin_quality
from product_platform.marketplace.signing import verify_plugin_signature_with_key
from product_platform.marketplace.usage_trust import (
    PluginUsageSignals,
    compute_usage_trust_delta,
    trust_tier_for_score,
)


class MarketplaceManifestError(ValueError):
    """Raised when a plugin manifest cannot be imported."""


class PluginNotFoundError(ValueError):
    """Raised when a plugin is not visible in tenant scope."""


class DuplicatePluginVersionError(ValueError):
    """Raised when a plugin version cannot be imported because of a conflict."""


class PluginInstallationBlockedError(ValueError):
    """Raised when marketplace policy blocks installation."""


class PluginInstallationNotFoundError(ValueError):
    """Raised when an installation is not visible in tenant scope."""


class PluginInstallationStateError(ValueError):
    """Raised when an installation lifecycle action is invalid."""


class PluginReviewNotFoundError(ValueError):
    """Raised when a plugin review is not visible in tenant scope."""


class PluginReviewStateError(ValueError):
    """Raised when a review transition is invalid."""


class PluginSigningKeyNotFoundError(ValueError):
    """Raised when a signing key is not visible in tenant scope."""


class MarketplaceCatalogRepository:
    """Tenant-scoped marketplace catalog repository."""

    def __init__(self, connection: Connection, organization_id: str) -> None:
        self.connection = connection
        self.organization_id = organization_id

    def import_plugin(self, body: PluginImportRequest) -> Row:
        """Import or update one plugin version from a validated manifest."""

        try:
            normalized = normalize_plugin_manifest(body)
        except ValueError as exc:
            raise MarketplaceManifestError(str(exc)) from exc

        plugin = self._get_plugin_by_identity(normalized.name, normalized.publisher)
        now = utc_now_iso()
        if plugin is None:
            plugin_id = generate_id("plug")
            self.connection.execute(
                """
                INSERT INTO plugins (
                    id, organization_id, name, description, publisher,
                    plugin_type, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plugin_id,
                    self.organization_id,
                    normalized.name,
                    normalized.description,
                    normalized.publisher,
                    normalized.plugin_type,
                    body.status,
                    now,
                    now,
                ),
            )
        else:
            plugin_id = plugin["id"]
            self.connection.execute(
                """
                UPDATE plugins
                SET description = ?,
                    plugin_type = ?,
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                  AND organization_id = ?
                """,
                (
                    normalized.description,
                    normalized.plugin_type,
                    body.status,
                    now,
                    plugin_id,
                    self.organization_id,
                ),
            )
        self._upsert_version(plugin_id, normalized, now=now)
        row = self.get_plugin(plugin_id)
        if row is None:
            raise PluginNotFoundError("Imported plugin could not be loaded.")
        return row

    def list_plugins(
        self,
        *,
        plugin_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List plugins visible to the organization."""

        clauses = ["organization_id = ?"]
        values: list[object] = [self.organization_id]
        if plugin_type:
            clauses.append("plugin_type = ?")
            values.append(plugin_type)
        if status:
            clauses.append("status = ?")
            values.append(status)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT *
            FROM plugins
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_plugin(self, plugin_id: str) -> Row | None:
        """Get one plugin in organization scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM plugins
            WHERE id = ?
              AND organization_id = ?
            """,
            (plugin_id, self.organization_id),
        ).fetchone()

    def list_versions(self, plugin_id: str) -> list[Row]:
        """List versions for one plugin in newest-first order."""

        plugin = self.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError("Plugin not found.")
        return self.connection.execute(
            """
            SELECT *
            FROM plugin_versions
            WHERE plugin_id = ?
            ORDER BY created_at DESC, version DESC, id DESC
            """,
            (plugin_id,),
        ).fetchall()

    def get_version(self, version_id: str) -> Row | None:
        """Get a plugin version in organization scope."""

        return self.connection.execute(
            """
            SELECT v.*
            FROM plugin_versions v
            JOIN plugins p ON p.id = v.plugin_id
            WHERE v.id = ?
              AND p.organization_id = ?
            """,
            (version_id, self.organization_id),
        ).fetchone()

    def check_policy(
        self,
        version_id: str,
        body: PluginPolicyCheckRequest,
    ) -> Row:
        """Evaluate and persist marketplace policy compatibility for a version."""

        version = self.get_version(version_id)
        if version is None:
            raise PluginNotFoundError("Plugin version not found.")
        plugin = self.connection.execute(
            """
            SELECT p.*
            FROM plugins p
            JOIN plugin_versions v ON v.plugin_id = p.id
            WHERE v.id = ?
              AND p.organization_id = ?
            """,
            (version_id, self.organization_id),
        ).fetchone()
        if plugin is None:
            raise PluginNotFoundError("Plugin not found.")
        manifest = json.loads(version["manifest_json"])
        if body.require_review_approval and bool(manifest.get("review_required")):
            latest_review = self._latest_review(version_id)
            manifest["review_status"] = latest_review["status"] if latest_review is not None else "not_submitted"
        evaluation = evaluate_plugin_policy(
            PluginPolicyInput(
                plugin_type=plugin["plugin_type"],
                signature_status=self.signature_status_for_version(version_id),
                required_capabilities=json.loads(version["required_capabilities_json"]),
                manifest=manifest,
            ),
            body,
        )
        result_id = generate_id("plugpol")
        created_at = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO plugin_policy_results (
                id, plugin_version_id, result, findings_json, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                result_id,
                version_id,
                evaluation.result,
                canonical_json(evaluation.findings),
                created_at,
            ),
        )
        row = self.get_policy_result(result_id)
        if row is None:
            raise PluginNotFoundError("Plugin policy result could not be loaded.")
        return row

    def get_policy_result(self, result_id: str) -> Row | None:
        """Get one policy result in organization scope."""

        return self.connection.execute(
            """
            SELECT r.*
            FROM plugin_policy_results r
            JOIN plugin_versions v ON v.id = r.plugin_version_id
            JOIN plugins p ON p.id = v.plugin_id
            WHERE r.id = ?
              AND p.organization_id = ?
            """,
            (result_id, self.organization_id),
        ).fetchone()

    def latest_policy_result_for_version(self, version_id: str) -> Row | None:
        """Return the latest policy result for a plugin version."""

        return self.connection.execute(
            """
            SELECT r.*
            FROM plugin_policy_results r
            JOIN plugin_versions v ON v.id = r.plugin_version_id
            JOIN plugins p ON p.id = v.plugin_id
            WHERE r.plugin_version_id = ?
              AND p.organization_id = ?
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT 1
            """,
            (version_id, self.organization_id),
        ).fetchone()

    def version_install_allowed(self, version_id: str) -> bool:
        """Return false when the latest policy result denies install."""

        latest = self.latest_policy_result_for_version(version_id)
        return latest is None or latest["result"] != "deny"

    def create_installation(
        self,
        body: PluginInstallationCreateRequest,
        *,
        installed_by: str,
    ) -> Row:
        """Install a plugin version into an environment or target agent."""

        if self.get_version(body.plugin_version_id) is None:
            raise PluginNotFoundError("Plugin version not found.")
        self._require_environment(body.environment_id)
        if body.target_agent_id:
            self._require_agent(body.target_agent_id, body.environment_id)
        if self._version_requires_review(body.plugin_version_id) and not self.version_review_approved(
            body.plugin_version_id
        ):
            raise PluginInstallationBlockedError("Plugin review approval is required before installation.")
        if self.latest_policy_result_for_version(body.plugin_version_id) is None:
            self.check_policy(body.plugin_version_id, PluginPolicyCheckRequest())
        if not self.version_install_allowed(body.plugin_version_id):
            raise PluginInstallationBlockedError("Plugin policy result denies installation.")
        if self._active_installation(
            body.plugin_version_id,
            body.environment_id,
            body.target_agent_id,
        ) is not None:
            raise PluginInstallationStateError("Plugin version is already installed for this target.")
        installation_id = generate_id("pluginst")
        now = utc_now_iso()
        try:
            self.connection.execute(
                """
                INSERT INTO plugin_installations (
                    id, plugin_version_id, environment_id, target_agent_id,
                    status, installed_by, installed_at, uninstalled_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    installation_id,
                    body.plugin_version_id,
                    body.environment_id,
                    body.target_agent_id,
                    "installed",
                    installed_by,
                    now,
                    None,
                ),
            )
        except IntegrityError as exc:
            raise PluginInstallationStateError("Plugin version is already installed for this target.") from exc
        row = self.get_installation(installation_id)
        if row is None:
            raise PluginInstallationNotFoundError("Created installation could not be loaded.")
        return row

    def list_installations(
        self,
        *,
        environment_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List plugin installations for an environment."""

        self._require_environment(environment_id)
        clauses = ["i.environment_id = ?", "p.organization_id = ?"]
        values: list[object] = [environment_id, self.organization_id]
        if status:
            clauses.append("i.status = ?")
            values.append(status)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                i.*,
                p.name AS plugin_name,
                v.version AS version,
                a.name AS target_agent_name
            FROM plugin_installations i
            JOIN plugin_versions v ON v.id = i.plugin_version_id
            JOIN plugins p ON p.id = v.plugin_id
            LEFT JOIN agents a ON a.id = i.target_agent_id
            WHERE {' AND '.join(clauses)}
            ORDER BY i.installed_at DESC, i.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_installation(self, installation_id: str) -> Row | None:
        """Get an installation visible to the organization."""

        return self.connection.execute(
            """
            SELECT
                i.*,
                p.name AS plugin_name,
                v.version AS version,
                a.name AS target_agent_name
            FROM plugin_installations i
            JOIN plugin_versions v ON v.id = i.plugin_version_id
            JOIN plugins p ON p.id = v.plugin_id
            LEFT JOIN agents a ON a.id = i.target_agent_id
            WHERE i.id = ?
              AND p.organization_id = ?
            """,
            (installation_id, self.organization_id),
        ).fetchone()

    def uninstall(self, installation_id: str) -> Row:
        """Mark an installed plugin as uninstalled."""

        existing = self.get_installation(installation_id)
        if existing is None:
            raise PluginInstallationNotFoundError("Plugin installation not found.")
        if existing["status"] != "installed":
            raise PluginInstallationStateError("Only installed plugins can be uninstalled.")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE plugin_installations
            SET status = ?,
                uninstalled_at = ?
            WHERE id = ?
            """,
            ("uninstalled", now, installation_id),
        )
        row = self.get_installation(installation_id)
        if row is None:
            raise PluginInstallationNotFoundError("Plugin installation not found.")
        return row

    def submit_review(self, version_id: str, body: PluginReviewSubmitRequest) -> Row:
        """Submit a plugin version for review."""

        if self.get_version(version_id) is None:
            raise PluginNotFoundError("Plugin version not found.")
        review_id = generate_id("plugrev")
        created_at = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO plugin_reviews (
                id, plugin_version_id, status, reviewer_id, findings_json,
                decision_reason, created_at, decided_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                version_id,
                "pending",
                None,
                canonical_json(body.findings),
                None,
                created_at,
                None,
            ),
        )
        row = self.get_review(review_id)
        if row is None:
            raise PluginReviewNotFoundError("Created plugin review could not be loaded.")
        return row

    def list_reviews(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Row]:
        """List plugin reviews in organization scope."""

        clauses = ["p.organization_id = ?"]
        values: list[object] = [self.organization_id]
        if status:
            clauses.append("r.status = ?")
            values.append(status)
        values.extend([limit, offset])
        return self.connection.execute(
            f"""
            SELECT
                r.*,
                p.name AS plugin_name,
                v.version AS version
            FROM plugin_reviews r
            JOIN plugin_versions v ON v.id = r.plugin_version_id
            JOIN plugins p ON p.id = v.plugin_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()

    def get_review(self, review_id: str) -> Row | None:
        """Get one review in organization scope."""

        return self.connection.execute(
            """
            SELECT
                r.*,
                p.name AS plugin_name,
                v.version AS version
            FROM plugin_reviews r
            JOIN plugin_versions v ON v.id = r.plugin_version_id
            JOIN plugins p ON p.id = v.plugin_id
            WHERE r.id = ?
              AND p.organization_id = ?
            """,
            (review_id, self.organization_id),
        ).fetchone()

    def decide_review(
        self,
        review_id: str,
        *,
        status: str,
        reviewer_id: str,
        body: PluginReviewDecisionRequest,
    ) -> Row:
        """Approve or reject a pending plugin review."""

        review = self.get_review(review_id)
        if review is None:
            raise PluginReviewNotFoundError("Plugin review not found.")
        if review["status"] != "pending":
            raise PluginReviewStateError("Only pending reviews can be decided.")
        if status == "rejected" and not body.decision_reason:
            raise PluginReviewStateError("Rejecting a plugin review requires a reason.")
        decided_at = utc_now_iso()
        self.connection.execute(
            """
            UPDATE plugin_reviews
            SET status = ?,
                reviewer_id = ?,
                decision_reason = ?,
                decided_at = ?
            WHERE id = ?
            """,
            (status, reviewer_id, body.decision_reason, decided_at, review_id),
        )
        row = self.get_review(review_id)
        if row is None:
            raise PluginReviewNotFoundError("Plugin review not found.")
        return row

    def version_review_approved(self, version_id: str) -> bool:
        """Return whether the latest review for a version is approved."""

        latest = self._latest_review(version_id)
        return latest is not None and latest["status"] == "approved"

    def create_signing_key(self, body: PluginSigningKeyCreateRequest, *, created_by: str) -> Row:
        """Create a plugin signing key."""

        key_id = generate_id("plugkey")
        created_at = utc_now_iso()
        revoked_at = created_at if body.status == "revoked" else None
        self.connection.execute(
            """
            INSERT INTO plugin_signing_keys (
                id, organization_id, name, public_key, status, created_by, created_at, revoked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key_id,
                self.organization_id,
                body.name,
                body.public_key,
                body.status,
                created_by,
                created_at,
                revoked_at,
            ),
        )
        row = self.get_signing_key(key_id)
        if row is None:
            raise PluginSigningKeyNotFoundError("Created signing key could not be loaded.")
        return row

    def list_signing_keys(self) -> list[Row]:
        """List signing keys in organization scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM plugin_signing_keys
            WHERE organization_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (self.organization_id,),
        ).fetchall()

    def get_signing_key(self, key_id: str) -> Row | None:
        """Get one signing key in organization scope."""

        return self.connection.execute(
            """
            SELECT *
            FROM plugin_signing_keys
            WHERE id = ?
              AND organization_id = ?
            """,
            (key_id, self.organization_id),
        ).fetchone()

    def revoke_signing_key(self, key_id: str) -> Row:
        """Revoke a signing key."""

        existing = self.get_signing_key(key_id)
        if existing is None:
            raise PluginSigningKeyNotFoundError("Signing key not found.")
        now = utc_now_iso()
        self.connection.execute(
            """
            UPDATE plugin_signing_keys
            SET status = ?,
                revoked_at = ?
            WHERE id = ?
              AND organization_id = ?
            """,
            ("revoked", now, key_id, self.organization_id),
        )
        row = self.get_signing_key(key_id)
        if row is None:
            raise PluginSigningKeyNotFoundError("Signing key not found.")
        return row

    def signature_status_for_version(self, version_id: str) -> str:
        """Validate a plugin version signature against configured active keys."""

        version = self.get_version(version_id)
        if version is None:
            raise PluginNotFoundError("Plugin version not found.")
        manifest = json.loads(version["manifest_json"])
        if not manifest.get("signature"):
            return "unsigned"
        keys = self.list_signing_keys()
        if not keys:
            return version["signature_status"]
        for key in keys:
            if verify_plugin_signature_with_key(
                manifest,
                public_key=key["public_key"],
                key_status=key["status"],
            ):
                return "signed"
        return "invalid"

    def assess_quality(self, version_id: str) -> Row:
        """Assess and persist quality for a plugin version."""

        version = self.get_version(version_id)
        if version is None:
            raise PluginNotFoundError("Plugin version not found.")
        assessment = assess_plugin_quality(json.loads(version["manifest_json"]))
        assessment_id = generate_id("plugqa")
        created_at = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO plugin_quality_assessments (
                id, plugin_version_id, score, dimensions_json, findings_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                assessment_id,
                version_id,
                assessment.score,
                canonical_json(assessment.dimensions),
                canonical_json(assessment.findings),
                created_at,
            ),
        )
        self.connection.execute(
            """
            UPDATE plugin_versions
            SET quality_score = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (assessment.score, created_at, version_id),
        )
        row = self.get_quality_assessment(assessment_id)
        if row is None:
            raise PluginNotFoundError("Plugin quality assessment could not be loaded.")
        return row

    def get_quality_assessment(self, assessment_id: str) -> Row | None:
        """Get one quality assessment in organization scope."""

        return self.connection.execute(
            """
            SELECT qa.*
            FROM plugin_quality_assessments qa
            JOIN plugin_versions v ON v.id = qa.plugin_version_id
            JOIN plugins p ON p.id = v.plugin_id
            WHERE qa.id = ?
              AND p.organization_id = ?
            """,
            (assessment_id, self.organization_id),
        ).fetchone()

    def latest_quality_assessment_for_version(self, version_id: str) -> Row | None:
        """Get latest quality assessment for a version."""

        return self.connection.execute(
            """
            SELECT qa.*
            FROM plugin_quality_assessments qa
            JOIN plugin_versions v ON v.id = qa.plugin_version_id
            JOIN plugins p ON p.id = v.plugin_id
            WHERE qa.plugin_version_id = ?
              AND p.organization_id = ?
            ORDER BY qa.created_at DESC, qa.id DESC
            LIMIT 1
            """,
            (version_id, self.organization_id),
        ).fetchone()

    def recompute_trust(self, version_id: str, body: PluginTrustRecomputeRequest) -> Row:
        """Recompute and persist usage trust for a plugin version."""

        if self.get_version(version_id) is None:
            raise PluginNotFoundError("Plugin version not found.")
        latest = self.latest_trust_event_for_version(version_id)
        score_before = int(latest["score_after"]) if latest is not None else 500
        delta, reason = compute_usage_trust_delta(
            PluginUsageSignals(
                daily_active_users=body.daily_active_users,
                total_invocations=body.total_invocations,
                error_count=body.error_count,
                incident_count=body.incident_count,
                days_since_update=body.days_since_update,
                adoption_trend=body.adoption_trend,
            )
        )
        score_after = max(0, min(1000, score_before + delta))
        trust_tier = trust_tier_for_score(score_after)
        event_id = generate_id("plugtrust")
        created_at = utc_now_iso()
        self.connection.execute(
            """
            INSERT INTO plugin_trust_events (
                id, plugin_version_id, source_event_id, delta, reason,
                score_before, score_after, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                version_id,
                body.source_event_id,
                delta,
                reason,
                score_before,
                score_after,
                created_at,
            ),
        )
        self.connection.execute(
            """
            UPDATE plugin_versions
            SET trust_tier = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (trust_tier, created_at, version_id),
        )
        row = self.get_trust_event(event_id)
        if row is None:
            raise PluginNotFoundError("Plugin trust event could not be loaded.")
        return row

    def latest_trust_event_for_version(self, version_id: str) -> Row | None:
        """Get latest trust event for a version."""

        return self.connection.execute(
            """
            SELECT e.*
            FROM plugin_trust_events e
            JOIN plugin_versions v ON v.id = e.plugin_version_id
            JOIN plugins p ON p.id = v.plugin_id
            WHERE e.plugin_version_id = ?
              AND p.organization_id = ?
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
            """,
            (version_id, self.organization_id),
        ).fetchone()

    def get_trust_event(self, event_id: str) -> Row | None:
        """Get one trust event in organization scope."""

        return self.connection.execute(
            """
            SELECT e.*, v.trust_tier AS trust_tier
            FROM plugin_trust_events e
            JOIN plugin_versions v ON v.id = e.plugin_version_id
            JOIN plugins p ON p.id = v.plugin_id
            WHERE e.id = ?
              AND p.organization_id = ?
            """,
            (event_id, self.organization_id),
        ).fetchone()

    def _upsert_version(
        self,
        plugin_id: str,
        normalized: NormalizedPluginManifest,
        *,
        now: str,
    ) -> None:
        existing = self.connection.execute(
            """
            SELECT id
            FROM plugin_versions
            WHERE plugin_id = ?
              AND version = ?
            """,
            (plugin_id, normalized.version),
        ).fetchone()
        values = (
            canonical_json(normalized.manifest),
            normalized.package_ref,
            normalized.signature_status,
            canonical_json(normalized.required_capabilities),
            canonical_json(normalized.permissions),
            now,
        )
        if existing is None:
            version_id = generate_id("plugver")
            try:
                self.connection.execute(
                    """
                    INSERT INTO plugin_versions (
                        id, plugin_id, version, manifest_json, package_ref,
                        signature_status, quality_score, trust_tier,
                        required_capabilities_json, permissions_json,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        plugin_id,
                        normalized.version,
                        values[0],
                        values[1],
                        values[2],
                        0,
                        "unrated",
                        values[3],
                        values[4],
                        now,
                        now,
                    ),
                )
            except IntegrityError as exc:
                raise DuplicatePluginVersionError("Plugin version already exists.") from exc
            return
        self.connection.execute(
            """
            UPDATE plugin_versions
            SET manifest_json = ?,
                package_ref = ?,
                signature_status = ?,
                required_capabilities_json = ?,
                permissions_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (*values, existing["id"]),
        )

    def _get_plugin_by_identity(self, name: str, publisher: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT *
            FROM plugins
            WHERE organization_id = ?
              AND name = ?
              AND publisher = ?
            """,
            (self.organization_id, name, publisher),
        ).fetchone()

    def _require_environment(self, environment_id: str) -> None:
        row = self.connection.execute(
            """
            SELECT id
            FROM environments
            WHERE id = ?
              AND organization_id = ?
            """,
            (environment_id, self.organization_id),
        ).fetchone()
        if row is None:
            raise PluginNotFoundError("Environment not found.")

    def _require_agent(self, agent_id: str, environment_id: str) -> None:
        row = self.connection.execute(
            """
            SELECT id
            FROM agents
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
            """,
            (agent_id, self.organization_id, environment_id),
        ).fetchone()
        if row is None:
            raise PluginNotFoundError("Target agent not found.")

    def _active_installation(
        self,
        version_id: str,
        environment_id: str,
        target_agent_id: str | None,
    ) -> Row | None:
        if target_agent_id is None:
            target_clause = "target_agent_id IS NULL"
            values: tuple[object, ...] = (version_id, environment_id)
        else:
            target_clause = "target_agent_id = ?"
            values = (version_id, environment_id, target_agent_id)
        return self.connection.execute(
            f"""
            SELECT *
            FROM plugin_installations
            WHERE plugin_version_id = ?
              AND environment_id = ?
              AND status = 'installed'
              AND {target_clause}
            ORDER BY installed_at DESC, id DESC
            LIMIT 1
            """,
            values,
        ).fetchone()

    def _version_requires_review(self, version_id: str) -> bool:
        version = self.get_version(version_id)
        if version is None:
            raise PluginNotFoundError("Plugin version not found.")
        manifest = json.loads(version["manifest_json"])
        if bool(manifest.get("review_required")):
            return True
        return self._latest_review(version_id) is not None

    def _latest_review(self, version_id: str) -> Row | None:
        return self.connection.execute(
            """
            SELECT r.*
            FROM plugin_reviews r
            JOIN plugin_versions v ON v.id = r.plugin_version_id
            JOIN plugins p ON p.id = v.plugin_id
            WHERE r.plugin_version_id = ?
              AND p.organization_id = ?
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT 1
            """,
            (version_id, self.organization_id),
        ).fetchone()


def canonical_json(value: Any) -> str:
    """Serialize a JSON-compatible value deterministically."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def plugin_response(repository: MarketplaceCatalogRepository, row: Row) -> PluginResponse:
    """Build a plugin API response."""

    return PluginResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        name=row["name"],
        description=row["description"],
        publisher=row["publisher"],
        plugin_type=row["plugin_type"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        versions=[plugin_version_response(version) for version in repository.list_versions(row["id"])],
    )


def plugin_version_response(row: Row) -> PluginVersionResponse:
    """Build a plugin version API response."""

    return PluginVersionResponse(
        id=row["id"],
        plugin_id=row["plugin_id"],
        version=row["version"],
        manifest=json.loads(row["manifest_json"]),
        package_ref=row["package_ref"],
        signature_status=row["signature_status"],
        quality_score=float(row["quality_score"]),
        trust_tier=row["trust_tier"],
        required_capabilities=json.loads(row["required_capabilities_json"]),
        permissions=json.loads(row["permissions_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def plugin_policy_result_response(row: Row) -> PluginPolicyResultResponse:
    """Build a plugin policy result API response."""

    return PluginPolicyResultResponse(
        id=row["id"],
        plugin_version_id=row["plugin_version_id"],
        result=row["result"],
        findings=json.loads(row["findings_json"]),
        created_at=row["created_at"],
    )


def plugin_installation_response(row: Row) -> PluginInstallationResponse:
    """Build a plugin installation API response."""

    return PluginInstallationResponse(
        id=row["id"],
        plugin_version_id=row["plugin_version_id"],
        plugin_name=row["plugin_name"],
        version=row["version"],
        environment_id=row["environment_id"],
        target_agent_id=row["target_agent_id"],
        target_agent_name=row["target_agent_name"],
        status=row["status"],
        installed_by=row["installed_by"],
        installed_at=row["installed_at"],
        uninstalled_at=row["uninstalled_at"],
    )


def plugin_review_response(row: Row) -> PluginReviewResponse:
    """Build a plugin review API response."""

    return PluginReviewResponse(
        id=row["id"],
        plugin_version_id=row["plugin_version_id"],
        plugin_name=row["plugin_name"],
        version=row["version"],
        status=row["status"],
        reviewer_id=row["reviewer_id"],
        findings=json.loads(row["findings_json"]),
        decision_reason=row["decision_reason"],
        created_at=row["created_at"],
        decided_at=row["decided_at"],
    )


def plugin_signing_key_response(row: Row) -> PluginSigningKeyResponse:
    """Build a plugin signing key API response."""

    return PluginSigningKeyResponse(
        id=row["id"],
        organization_id=row["organization_id"],
        name=row["name"],
        public_key=row["public_key"],
        status=row["status"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        revoked_at=row["revoked_at"],
    )


def plugin_quality_assessment_response(row: Row) -> PluginQualityAssessmentResponse:
    """Build a plugin quality assessment response."""

    return PluginQualityAssessmentResponse(
        id=row["id"],
        plugin_version_id=row["plugin_version_id"],
        score=float(row["score"]),
        dimensions=json.loads(row["dimensions_json"]),
        findings=json.loads(row["findings_json"]),
        created_at=row["created_at"],
    )


def plugin_trust_event_response(row: Row) -> PluginTrustEventResponse:
    """Build a plugin trust event response."""

    return PluginTrustEventResponse(
        id=row["id"],
        plugin_version_id=row["plugin_version_id"],
        source_event_id=row["source_event_id"],
        delta=int(row["delta"]),
        reason=row["reason"],
        score_before=int(row["score_before"]),
        score_after=int(row["score_after"]),
        trust_tier=row["trust_tier"],
        created_at=row["created_at"],
    )
