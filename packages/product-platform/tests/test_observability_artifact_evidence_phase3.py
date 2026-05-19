from __future__ import annotations

import base64
import json
import tempfile
import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.artifacts.storage import calculate_sha256
from product_platform.audit.events import AuditEventEnvelope
from product_platform.audit.store import AuditEventRepository
from product_platform.db.seed import seed_demo_data
from product_platform.db.testing import create_migrated_test_database
from product_platform.tool_gateway.runtime_audit import (
    ToolRuntimeActionCreate,
    ToolRuntimeActionRepository,
)


TRACE_ID = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
PARENT_SPAN_ID = "ffffffffffffffff"
SPAN_ID = "1111111111111111"
TRACEPARENT = f"00-{TRACE_ID}-{PARENT_SPAN_ID}-01"
ARTIFACT_CONTENT = b'{"evidence": "runtime artifact", "redacted": true}\n'


class ObservabilityArtifactEvidencePhase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact_root = tempfile.TemporaryDirectory()
        self.addCleanup(self.artifact_root.cleanup)
        self.database = create_migrated_test_database()
        with self.database.transaction() as connection:
            seed_demo_data(connection)
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-05-20T00:00:00Z",
                dev_login_allowed_emails=["artifact-evidence@example.com"],
                session_secret="test-secret",
                artifact_storage_path=self.artifact_root.name,
            ),
            database=self.database,
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "artifact-evidence@example.com", "roles": ["Platform Admin"]},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.token = login.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Environment-ID": "env_default",
            "X-Correlation-ID": "corr-artifact-evidence",
            "traceparent": TRACEPARENT,
        }

    def _upload_artifact(self) -> dict:
        response = self.client.post(
            "/api/v1/artifacts",
            headers=self._headers(),
            json={
                "artifact_type": "runtime.output",
                "name": "runtime-evidence.json",
                "content_type": "application/json",
                "content_base64": base64.b64encode(ARTIFACT_CONTENT).decode("ascii"),
                "retention_policy": "retain_90d",
                "redaction_classification": "redacted",
                "provenance": {"source": "tool_runtime_action", "trace_id": TRACE_ID},
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _create_trace_span_and_eval(self) -> tuple[dict, dict, dict]:
        trace = self.client.post(
            "/api/v1/observability/traces",
            headers=self._headers(),
            json={
                "trace_id": TRACE_ID,
                "name": "Artifact evidence trace",
                "status": "ok",
                "metadata": {"scenario": "artifact-evidence"},
            },
        )
        self.assertEqual(trace.status_code, 201, trace.text)
        span = self.client.post(
            f"/api/v1/observability/traces/{TRACE_ID}/spans",
            headers=self._headers(),
            json={
                "span_id": SPAN_ID,
                "parent_span_id": PARENT_SPAN_ID,
                "span_kind": "tool",
                "name": "render_artifact",
                "status": "ok",
                "attributes": {"artifact.name": "runtime-evidence.json"},
            },
        )
        self.assertEqual(span.status_code, 201, span.text)
        eval_result = self.client.post(
            "/api/v1/observability/eval-results",
            headers=self._headers(),
            json={
                "trace_id": TRACE_ID,
                "span_id": SPAN_ID,
                "dataset_id": "dataset_artifact_evidence",
                "dataset_name": "Artifact Evidence QA",
                "evaluator_name": "artifact_integrity",
                "score": 1.0,
                "passed": True,
            },
        )
        self.assertEqual(eval_result.status_code, 201, eval_result.text)
        return trace.json(), span.json(), eval_result.json()

    def _create_tool_runtime_action(self, *, correlation_id: str = "corr-artifact-evidence") -> str:
        with self.database.transaction() as connection:
            row = ToolRuntimeActionRepository(connection, "org_default", "env_default").create_action(
                ToolRuntimeActionCreate(
                    request_id=f"req_{correlation_id}",
                    correlation_id=correlation_id,
                    trace_id=TRACE_ID,
                    span_id=SPAN_ID,
                    parent_span_id=PARENT_SPAN_ID,
                    traceparent=TRACEPARENT,
                    action_status="completed",
                    reason_code="allowed",
                    latency_ms=25,
                    payload_summary={"tool": "render_artifact"},
                    response_summary={"artifact": "runtime-evidence.json"},
                )
            )
        return row["id"]

    def test_runtime_trace_eval_artifact_links_are_queryable_from_trace(self) -> None:
        trace, span, eval_result = self._create_trace_span_and_eval()
        tool_action_id = self._create_tool_runtime_action()
        artifact = self._upload_artifact()

        for target_type, target_id in [
            ("tool_runtime_action", tool_action_id),
            ("observability_trace", trace["trace_id"]),
            ("observability_span", span["id"]),
            ("observability_eval_result", eval_result["id"]),
        ]:
            linked = self.client.post(
                f"/api/v1/artifacts/{artifact['id']}/links",
                headers=self._headers(),
                json={"target_type": target_type, "target_id": target_id, "link_type": "evidence"},
            )
            self.assertEqual(linked.status_code, 201, linked.text)

        detail = self.client.get(f"/api/v1/artifacts/{artifact['id']}", headers=self._headers())
        self.assertEqual(detail.status_code, 200, detail.text)
        link_targets = {(link["target_type"], link["target_id"]) for link in detail.json()["links"]}
        self.assertIn(("tool_runtime_action", tool_action_id), link_targets)
        self.assertIn(("observability_eval_result", eval_result["id"]), link_targets)

        trace_detail = self.client.get(f"/api/v1/observability/traces/{TRACE_ID}", headers=self._headers())
        self.assertEqual(trace_detail.status_code, 200, trace_detail.text)
        artifacts = trace_detail.json()["artifacts"]
        self.assertEqual(artifacts[0]["id"], artifact["id"])
        self.assertEqual(artifacts[0]["checksum"], calculate_sha256(ARTIFACT_CONTENT))
        self.assertEqual(artifacts[0]["links"][0]["target_type"], "tool_runtime_action")

    def test_digest_download_and_attestation_bind_artifact_checksum(self) -> None:
        artifact = self._upload_artifact()

        self.assertEqual(artifact["checksum"], calculate_sha256(ARTIFACT_CONTENT))
        self.assertEqual(artifact["digest_algorithm"], "sha256")
        self.assertEqual(artifact["retention_policy"], "retain_90d")
        self.assertEqual(artifact["redaction_classification"], "redacted")
        self.assertEqual(artifact["provenance"]["trace_id"], TRACE_ID)

        downloaded = self.client.get(
            f"/api/v1/artifacts/{artifact['id']}/download",
            headers=self._headers(),
        )
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        metadata = downloaded.json()["metadata"]
        self.assertTrue(metadata["checksum_verified"])
        self.assertTrue(metadata["digest_verified"])
        self.assertEqual(metadata["digest_algorithm"], "sha256")

        attested = self.client.post(
            f"/api/v1/artifacts/{artifact['id']}/attest",
            headers=self._headers(),
            json={"statement": "Artifact digest verified for runtime evidence.", "signature_ref": "sig-runtime-1"},
        )
        self.assertEqual(attested.status_code, 201, attested.text)
        attestation = attested.json()
        self.assertEqual(attestation["artifact_checksum"], artifact["checksum"])
        self.assertEqual(attestation["digest_algorithm"], "sha256")
        self.assertEqual(attestation["signer_user_id"], attestation["attested_by"])

    def test_audit_export_includes_linked_runtime_artifacts(self) -> None:
        correlation_id = "corr-artifact-export"
        tool_action_id = self._create_tool_runtime_action(correlation_id=correlation_id)
        artifact = self._upload_artifact()
        linked = self.client.post(
            f"/api/v1/artifacts/{artifact['id']}/links",
            headers=self._headers(),
            json={"target_type": "tool_runtime_action", "target_id": tool_action_id, "link_type": "evidence"},
        )
        self.assertEqual(linked.status_code, 201, linked.text)
        with self.database.transaction() as connection:
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id="org_default",
                    environment_id="env_default",
                    event_type="policy.decision",
                    source_component="policy-engine",
                    actor_type="agent",
                    actor_id="agent_artifact",
                    resource_type="runtime_action",
                    resource_id=tool_action_id,
                    decision="allow",
                    correlation_id=correlation_id,
                    trace_id=TRACE_ID,
                    payload_json={"tool_runtime_action_id": tool_action_id},
                )
            )

        exported = self.client.post(
            "/api/v1/audit/export",
            headers=self._headers(),
            json={"format": "json", "filters": {"correlation_id": correlation_id}},
        )
        self.assertEqual(exported.status_code, 201, exported.text)
        artifacts = self.client.get(
            "/api/v1/artifacts",
            headers=self._headers(),
            params={"artifact_type": "audit.export"},
        )
        self.assertEqual(artifacts.status_code, 200, artifacts.text)
        download = self.client.get(
            f"/api/v1/artifacts/{artifacts.json()[0]['id']}/download",
            headers=self._headers(),
        )
        self.assertEqual(download.status_code, 200, download.text)
        content = json.loads(base64.b64decode(download.json()["content_base64"]))
        linked_artifacts = content["integrity"]["chain_proof"]["linked_artifacts"]
        self.assertEqual(linked_artifacts[0]["id"], artifact["id"])
        self.assertEqual(linked_artifacts[0]["target_id"], tool_action_id)
        self.assertTrue(linked_artifacts[0]["digest_verified"])


if __name__ == "__main__":
    unittest.main()
