from __future__ import annotations

import unittest
from typing import Any

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.api.settings import Settings


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

    def test_operator_can_create_allowed_job(self) -> None:
        job = self._create_job()
        listed = self.client.get("/api/v1/jobs", headers=self.operator_headers)

        self.assertEqual(job["job_type"], "demo.noop")
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["payload"], {"source": "test"})
        self.assertEqual(job["runs"], [])
        self.assertEqual(listed.status_code, 200)
        self.assertIn(job["id"], {item["id"] for item in listed.json()})

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


if __name__ == "__main__":
    unittest.main()
