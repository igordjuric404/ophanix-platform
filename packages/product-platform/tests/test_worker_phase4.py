from __future__ import annotations

import unittest
from typing import Any

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings
from product_platform.db.time import utc_now_iso


class WorkerPhase4ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=[
                    "operator@example.com",
                    "viewer@example.com",
                ],
                session_secret="test-secret",
            )
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.operator_headers = self._login("operator@example.com", ["Operator"])
        self.viewer_headers = self._login("viewer@example.com", ["Viewer"])

    def tearDown(self) -> None:
        database = getattr(self.app.state, "database", None)
        if database is not None:
            database.close()

    def _login(self, email: str, roles: list[str]) -> dict[str, str]:
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": email, "roles": roles},
        )
        self.assertEqual(login.status_code, 200)
        return {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-Environment-ID": "env_default",
        }

    def _create_job(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.client.post(
            "/api/v1/jobs",
            json=body or {"job_type": "demo.noop", "payload": {"source": "test"}},
            headers=self.operator_headers,
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def _register_test_environment(self, environment_id: str = "env_other") -> None:
        now = utc_now_iso()
        self.app.state.tenant_store.create_environment(
            organization_id="org_default",
            name="Other",
            slug="other",
            environment_type="development",
        )
        if self.app.state.database is None:
            self.client.get("/api/v1/jobs", headers=self.operator_headers)
        with self.app.state.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO environments (id, organization_id, name, slug, type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (environment_id, "org_default", "Other", "other", "development", now, now),
            )

    def test_operator_can_create_allowed_job(self) -> None:
        job = self._create_job()
        listed = self.client.get("/api/v1/jobs", headers=self.operator_headers)

        self.assertEqual(job["job_type"], "demo.noop")
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["payload"], {"source": "test"})
        self.assertEqual(job["runs"], [])
        self.assertEqual(listed.status_code, 200)
        self.assertIn(job["id"], {item["id"] for item in listed.json()})

    def test_unknown_api_job_type_is_rejected_before_persistence(self) -> None:
        response = self.client.post(
            "/api/v1/jobs",
            json={"job_type": "unknown.job", "payload": {}},
            headers=self.operator_headers,
        )

        self.assertEqual(response.status_code, 422)

    def test_viewer_cannot_cancel_job(self) -> None:
        job = self._create_job()

        response = self.client.post(
            f"/api/v1/jobs/{job['id']}/cancel",
            headers=self.viewer_headers,
        )

        self.assertEqual(response.status_code, 403)

    def test_job_completion_emits_audit_event(self) -> None:
        response = self.client.post(
            "/api/v1/jobs",
            json={
                "job_type": "demo.noop",
                "payload": {"source": "overall-validation"},
                "run_immediately": True,
            },
            headers=self.operator_headers,
        )
        job = response.json()
        events = self.client.get(
            "/api/v1/audit/events",
            params={"event_type": "workflow.run", "resource_id": job["id"]},
            headers=self.operator_headers,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["runs"][0]["result"]["ok"], True)
        self.assertEqual(events.status_code, 200)
        self.assertTrue(
            any(event["payload_json"]["status"] == "succeeded" for event in events.json())
        )

    def test_cancel_pending_job_does_not_execute(self) -> None:
        job = self._create_job()
        canceled = self.client.post(
            f"/api/v1/jobs/{job['id']}/cancel",
            headers=self.operator_headers,
        )
        fetched = self.client.get(f"/api/v1/jobs/{job['id']}", headers=self.operator_headers)

        self.assertEqual(canceled.status_code, 200)
        self.assertEqual(canceled.json()["status"], "canceled")
        self.assertEqual(canceled.json()["runs"], [])
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["status"], "canceled")
        self.assertEqual(fetched.json()["runs"], [])

    def test_schedule_create_list_and_patch(self) -> None:
        created = self.client.post(
            "/api/v1/job-schedules",
            json={
                "job_type": "demo.noop",
                "cron_expression": "interval:5m",
                "payload": {"scheduled": True},
                "next_run_at": "2026-04-30T10:00:00+00:00",
            },
            headers=self.operator_headers,
        )
        schedule_id = created.json()["id"]
        patched = self.client.patch(
            f"/api/v1/job-schedules/{schedule_id}",
            json={"enabled": False, "next_run_at": "2026-04-30T11:00:00+00:00"},
            headers=self.operator_headers,
        )
        listed = self.client.get("/api/v1/job-schedules", headers=self.operator_headers)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(patched.status_code, 200)
        self.assertFalse(patched.json()["enabled"])
        self.assertEqual(patched.json()["next_run_at"], "2026-04-30T11:00:00+00:00")
        self.assertIn(schedule_id, {item["id"] for item in listed.json()})

    def test_jobs_and_schedules_are_filtered_by_selected_environment(self) -> None:
        self._register_test_environment()
        default_job = self._create_job()
        other_headers = dict(self.operator_headers)
        other_headers["X-Environment-ID"] = "env_other"
        other_job = self.client.post(
            "/api/v1/jobs",
            json={"job_type": "demo.noop", "payload": {"environment": "other"}},
            headers=other_headers,
        ).json()
        other_schedule = self.client.post(
            "/api/v1/job-schedules",
            json={
                "job_type": "demo.noop",
                "cron_expression": "interval:5m",
                "payload": {"environment": "other"},
                "next_run_at": "2026-04-30T10:00:00+00:00",
            },
            headers=other_headers,
        ).json()

        default_jobs = self.client.get("/api/v1/jobs", headers=self.operator_headers)
        other_jobs = self.client.get("/api/v1/jobs", headers=other_headers)
        default_schedules = self.client.get("/api/v1/job-schedules", headers=self.operator_headers)
        blocked_patch = self.client.patch(
            f"/api/v1/job-schedules/{other_schedule['id']}",
            json={"enabled": False},
            headers=self.operator_headers,
        )

        self.assertEqual(default_jobs.status_code, 200)
        self.assertIn(default_job["id"], {item["id"] for item in default_jobs.json()})
        self.assertNotIn(other_job["id"], {item["id"] for item in default_jobs.json()})
        self.assertEqual(other_jobs.status_code, 200)
        self.assertEqual({item["id"] for item in other_jobs.json()}, {other_job["id"]})
        self.assertEqual(default_schedules.status_code, 200)
        self.assertNotIn(other_schedule["id"], {item["id"] for item in default_schedules.json()})
        self.assertEqual(blocked_patch.status_code, 404)

    def test_invalid_schedule_expression_is_rejected_at_api_boundary(self) -> None:
        response = self.client.post(
            "/api/v1/job-schedules",
            json={
                "job_type": "demo.noop",
                "cron_expression": "*/0 * * * *",
                "payload": {},
            },
            headers=self.operator_headers,
        )

        self.assertEqual(response.status_code, 422)

    def test_schedule_rejects_unknown_job_type_and_naive_next_run_time(self) -> None:
        unknown = self.client.post(
            "/api/v1/job-schedules",
            json={
                "job_type": "unknown.job",
                "cron_expression": "interval:5m",
                "payload": {},
                "next_run_at": "2026-04-30T10:00:00+00:00",
            },
            headers=self.operator_headers,
        )
        naive = self.client.post(
            "/api/v1/job-schedules",
            json={
                "job_type": "demo.noop",
                "cron_expression": "interval:5m",
                "payload": {},
                "next_run_at": "2026-04-30T10:00:00",
            },
            headers=self.operator_headers,
        )

        self.assertEqual(unknown.status_code, 422)
        self.assertEqual(naive.status_code, 422)


if __name__ == "__main__":
    unittest.main()
