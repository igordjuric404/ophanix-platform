from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from product_platform import create_app
from product_platform.audit.events import AuditEventEnvelope
from product_platform.api.settings import Settings


class AuditPhase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            Settings(
                app_name="Ophanix Test Platform",
                environment="test",
                build_sha="test-sha",
                build_time="2026-04-30T00:00:00Z",
                dev_login_allowed_emails=["admin@example.com"],
                session_secret="test-secret",
            )
        )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        login = self.client.post(
            "/api/v1/auth/dev-login",
            json={"email": "admin@example.com", "roles": ["Platform Admin"]},
        )
        self.headers = {
            "Authorization": f"Bearer {login.json()['access_token']}",
            "X-Environment-ID": "env_default",
        }

    def tearDown(self) -> None:
        database = getattr(self.app.state, "database", None)
        if database is not None:
            database.close()

    def test_stream_receives_inserted_event(self) -> None:
        event = _event("evt_stream_a", "stream.match")
        created = self.client.post(
            "/api/v1/audit/events",
            json=event.model_dump(),
            headers=self.headers,
        )

        response = self.client.get("/api/v1/audit/events/stream", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn(f"id: {created.json()['id']}", response.text)
        self.assertIn('"event_type": "stream.match"', response.text)

    def test_stream_filter_only_receives_matching_event_type(self) -> None:
        match = self.client.post(
            "/api/v1/audit/events",
            json=_event("evt_stream_match", "stream.match").model_dump(),
            headers=self.headers,
        )
        self.client.post(
            "/api/v1/audit/events",
            json=_event("evt_stream_other", "stream.other").model_dump(),
            headers=self.headers,
        )

        response = self.client.get(
            "/api/v1/audit/events/stream?event_type=stream.match",
            headers=self.headers,
        )

        self.assertIn(f"id: {match.json()['id']}", response.text)
        self.assertNotIn("stream.other", response.text)

    def test_reconnect_resumes_from_last_event_id(self) -> None:
        first = self.client.post(
            "/api/v1/audit/events",
            json=_event("evt_stream_first", "stream.resume", created_at="2026-04-30T00:00:01+00:00").model_dump(),
            headers=self.headers,
        )
        second = self.client.post(
            "/api/v1/audit/events",
            json=_event("evt_stream_second", "stream.resume", created_at="2026-04-30T00:00:02+00:00").model_dump(),
            headers=self.headers,
        )

        response = self.client.get(
            f"/api/v1/audit/events/stream?last_event_id={first.json()['id']}",
            headers=self.headers,
        )

        self.assertNotIn(f"id: {first.json()['id']}", response.text)
        self.assertIn(f"id: {second.json()['id']}", response.text)


def _event(
    event_id: str,
    event_type: str,
    *,
    created_at: str = "2026-04-30T00:00:00+00:00",
) -> AuditEventEnvelope:
    return AuditEventEnvelope(
        id=event_id,
        organization_id="org_default",
        environment_id="env_default",
        event_type=event_type,
        source_component="tests",
        actor_type="system",
        payload_json={"event_id": event_id},
        created_at=created_at,
    )


if __name__ == "__main__":
    unittest.main()
