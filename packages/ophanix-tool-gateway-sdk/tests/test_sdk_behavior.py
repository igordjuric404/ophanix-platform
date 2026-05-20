from __future__ import annotations

import asyncio
import unittest
from collections.abc import Callable
from collections.abc import Mapping
from unittest.mock import patch
from typing import Any
from typing import cast

import httpx
import ophanix_tool_gateway as sdk

from ophanix_tool_gateway import (
    AsyncGatewayHttpClient,
    AsyncOphanixToolGatewayClient,
    EnvironmentTokenProvider,
    GatewayCompatibility,
    OphanixToolGatewayClient,
    RuntimeCheckpointReference,
    RuntimeEvent,
    RuntimeRun,
    RuntimeRunStep,
    RuntimeSession,
    StaticTokenProvider,
    SyncGatewayHttpClient,
    ToolDeniedError,
    ToolGatewayClientConfig,
    ToolGatewayClientOptions,
    ToolGatewayError,
    ToolGatewayValidationError,
)


TOOL_FIXTURE = {
    "id": "tool_claims_lookup",
    "name": "claims.lookup",
    "display_name": "Claims Lookup",
    "description": "Lookup claim state.",
    "owner_team": "Claims",
    "status": "active",
    "required_scope": "claims.lookup:read",
    "input_schema_json": {"type": "object"},
    "output_schema_json": {"type": "object"},
}
TRACE_ID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
PARENT_SPAN_ID = "bbbbbbbbbbbbbbbb"
TRACEPARENT = f"00-{TRACE_ID}-{PARENT_SPAN_ID}-01"


class StandaloneSdkBehaviorTests(unittest.TestCase):
    def test_public_api_snapshot_includes_mvp_sdk_types(self) -> None:
        expected_exports = {
            "AsyncOphanixToolGatewayClient",
            "AsyncGatewayHttpClient",
            "EnvironmentTokenProvider",
            "GatewayCompatibility",
            "OphanixToolGatewayClient",
            "RuntimeCheckpointReference",
            "RuntimeEvent",
            "RuntimeRun",
            "RuntimeRunStep",
            "RuntimeSession",
            "StaticTokenProvider",
            "SyncGatewayHttpClient",
            "TelemetryEventHook",
            "ToolGatewayClientConfig",
            "ToolGatewayClientOptions",
            "ToolGatewayValidationError",
        }

        self.assertTrue(expected_exports.issubset(set(sdk.__all__)))
        self.assertIs(sdk.GatewayCompatibility, GatewayCompatibility)
        self.assertIs(sdk.RuntimeCheckpointReference, RuntimeCheckpointReference)
        self.assertIs(sdk.RuntimeEvent, RuntimeEvent)
        self.assertIs(sdk.RuntimeRun, RuntimeRun)
        self.assertIs(sdk.RuntimeRunStep, RuntimeRunStep)
        self.assertIs(sdk.RuntimeSession, RuntimeSession)
        self.assertIs(sdk.ToolGatewayClientConfig, ToolGatewayClientConfig)
        self.assertIs(sdk.ToolGatewayClientOptions, ToolGatewayClientOptions)
        self.assertIs(sdk.SyncGatewayHttpClient, SyncGatewayHttpClient)
        self.assertIs(sdk.AsyncGatewayHttpClient, AsyncGatewayHttpClient)

    def test_call_tool_returns_typed_result(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                json={
                    "request_id": "req-sdk",
                    "correlation_id": "corr-sdk",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "result": {"status": "succeeded"},
                    "error": None,
                },
            )
        )

        result = client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(result.request_id, "req-sdk")
        self.assertEqual(result.result, {"status": "succeeded"})
        self.assertEqual(result.body, {"status": "succeeded"})
        self.assertEqual(result.raw["request_id"], "req-sdk")
        self.assertNotIn("result", result.raw)

    def test_call_tool_can_opt_into_full_raw_success_response(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                json={
                    "request_id": "req-sdk",
                    "correlation_id": "corr-sdk",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "result": {"status": "succeeded"},
                    "error": None,
                },
            ),
            include_raw_response=True,
        )

        result = client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(result.raw["result"], {"status": "succeeded"})

    def test_call_tool_body_unwraps_gateway_execution_envelope(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                json={
                    "request_id": "req-sdk",
                    "correlation_id": "corr-sdk",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "result": {
                        "status": "succeeded",
                        "body": {"claim_status": "open"},
                        "upstream_status_code": 200,
                    },
                    "error": None,
                },
            )
        )

        result = client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(result.body, {"claim_status": "open"})

    def test_owned_http_clients_ignore_environment_proxy_defaults(self) -> None:
        client = OphanixToolGatewayClient(
            base_url="https://gateway.example.com",
            token_provider=StaticTokenProvider("token"),
        )
        try:
            self.assertFalse(client._http_client.trust_env)
        finally:
            client.close()

        async def exercise_async_client() -> None:
            async_client = AsyncOphanixToolGatewayClient(
                base_url="https://gateway.example.com",
                token_provider=StaticTokenProvider("token"),
            )
            try:
                self.assertFalse(async_client._http_client.trust_env)
            finally:
                await async_client.close()

        asyncio.run(exercise_async_client())

    def test_call_tool_sends_idempotency_key_and_retries_retryable_status(self) -> None:
        calls: list[httpx.Request] = []
        events: list[Mapping[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(503, json={"error": {"code": "try_again"}})
            return httpx.Response(
                200,
                json={
                    "request_id": "req-idem",
                    "correlation_id": "corr-idem",
                    "tool_name": "claims.lookup",
                    "result": {"ok": True},
                    "error": None,
                },
            )

        client = _client(handler, event_hook=events.append)
        client.invocation_retry_backoff_seconds = 0.0
        client.invocation_retry_jitter_ratio = 0.0

        result = client.call_tool(
            "claims.lookup",
            {"claim_id": "claim_123"},
            idempotency_key="idem-sdk-1",
        )

        self.assertEqual(result.result, {"ok": True})
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].headers["Idempotency-Key"], "idem-sdk-1")
        self.assertEqual(calls[1].headers["Idempotency-Key"], "idem-sdk-1")
        self.assertEqual(
            [event["event"] for event in events if event["event"] == "tool_call.retry"],
            ["tool_call.retry"],
        )

    def test_call_tool_sends_w3c_trace_context_headers(self) -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(
                200,
                json={
                    "request_id": "req-trace",
                    "correlation_id": "corr-trace",
                    "tool_name": "claims.lookup",
                    "result": {"ok": True},
                    "error": None,
                },
            )

        client = _client(handler)

        result = client.call_tool(
            "claims.lookup",
            {"claim_id": "claim_123"},
            correlation_id="corr-trace",
            traceparent=TRACEPARENT,
            tracestate="vendor=sdk",
            baggage="tenant=demo,tool=claims",
        )

        self.assertEqual(result.result, {"ok": True})
        self.assertEqual(calls[0].headers["traceparent"], TRACEPARENT)
        self.assertEqual(calls[0].headers["tracestate"], "vendor=sdk")
        self.assertEqual(calls[0].headers["baggage"], "tenant=demo,tool=claims")
        self.assertEqual(calls[0].headers["X-Correlation-ID"], "corr-trace")

    def test_runtime_session_methods_create_runs_and_thread_tool_context(self) -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if request.method == "POST" and request.url.path == "/api/v1/runtime/sessions":
                return httpx.Response(
                    201,
                    json={
                        "id": "rtssn_sdk",
                        "organization_id": "org_default",
                        "environment_id": "env_default",
                        "agent_id": "agent_claims",
                        "agent_name": "Claims Agent",
                        "state": "active",
                        "ring": 2,
                        "sponsor_user_id": None,
                        "created_by_user_id": "user_sdk",
                        "memory_scope": "session",
                        "thread_id": "thread-sdk",
                        "started_at": "2026-05-20T00:00:00+00:00",
                        "ended_at": None,
                        "metadata": {"purpose": "sdk"},
                        "trace_id": TRACE_ID,
                        "span_id": "dddddddddddddddd",
                        "parent_span_id": PARENT_SPAN_ID,
                        "traceparent": TRACEPARENT,
                        "tracestate": "vendor=sdk",
                        "baggage": "tenant=demo",
                        "actions": [],
                    },
                )
            if request.method == "GET" and request.url.path == "/api/v1/runtime/sessions/rtssn_sdk/runs":
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": "rtrun_sdk",
                            "organization_id": "org_default",
                            "environment_id": "env_default",
                            "session_id": "rtssn_sdk",
                            "thread_id": "thread-sdk",
                            "run_type": "session",
                            "status": "running",
                            "source_type": None,
                            "source_id": None,
                            "started_by_user_id": "user_sdk",
                            "trace_id": TRACE_ID,
                            "span_id": "dddddddddddddddd",
                            "parent_span_id": PARENT_SPAN_ID,
                            "correlation_id": "corr-runtime-sdk",
                            "recovery_state": {"checkpoint_count": 1},
                            "metadata": {"purpose": "sdk"},
                            "started_at": "2026-05-20T00:00:00+00:00",
                            "ended_at": None,
                            "updated_at": "2026-05-20T00:00:00+00:00",
                            "steps": [
                                {
                                    "id": "rtstep_sdk",
                                    "run_id": "rtrun_sdk",
                                    "session_id": "rtssn_sdk",
                                    "parent_step_id": None,
                                    "runtime_action_id": "rtact_sdk",
                                    "saga_id": None,
                                    "saga_step_id": None,
                                    "checkpoint_id": "sgchk_sdk",
                                    "policy_decision_id": "rtdcsn_sdk",
                                    "step_order": 1,
                                    "step_type": "runtime_action",
                                    "name": "claims.lookup",
                                    "status": "allow",
                                    "trace_id": TRACE_ID,
                                    "span_id": "eeeeeeeeeeeeeeee",
                                    "parent_span_id": "dddddddddddddddd",
                                    "correlation_id": "corr-runtime-sdk",
                                    "artifact_links": [],
                                    "metadata": {"resource_type": "claim"},
                                    "started_at": "2026-05-20T00:00:00+00:00",
                                    "ended_at": "2026-05-20T00:00:00+00:00",
                                    "updated_at": "2026-05-20T00:00:00+00:00",
                                }
                            ],
                        }
                    ],
                )
            if request.method == "POST" and request.url.path == "/api/v1/tools/claims.lookup/invoke":
                return httpx.Response(
                    200,
                    json={
                        "request_id": "req-runtime-sdk",
                        "correlation_id": "corr-runtime-sdk",
                        "tool_name": "claims.lookup",
                        "result": {"ok": True},
                        "error": None,
                    },
                )
            if request.method == "GET" and request.url.path == "/api/v1/audit/events/stream":
                self.assertEqual(request.url.params.get("event_type"), "runtime.session.started")
                self.assertEqual(request.url.params.get("last_event_id"), "evt_previous")
                self.assertEqual(request.url.params.get("limit"), "10")
                event_data = (
                    '{"id":"evt_runtime_sdk","organization_id":"org_default",'
                    '"environment_id":"env_default","event_type":"runtime.session.started",'
                    '"source_component":"runtime-control","actor_type":"user",'
                    '"actor_id":"user_sdk","agent_id":"agent_claims",'
                    '"resource_type":"runtime_session","resource_id":"rtssn_sdk",'
                    '"decision":"allow","severity":"info",'
                    '"correlation_id":"corr-runtime-sdk","trace_id":"'
                    + TRACE_ID
                    + '","payload_json":{"session_id":"rtssn_sdk","run_id":"rtrun_sdk"},'
                    '"created_at":"2026-05-20T00:00:00+00:00"}'
                )
                return httpx.Response(
                    200,
                    text=f"id: evt_runtime_sdk\nevent: audit_event\ndata: {event_data}\n\n",
                    headers={"content-type": "text/event-stream"},
                )
            return httpx.Response(404, json={"error": {"code": "not_found"}})

        client = _client(handler)

        session = client.create_runtime_session(
            agent_id="agent_claims",
            environment_id="env_default",
            ring=2,
            metadata={"purpose": "sdk", "thread_id": "thread-sdk", "memory_scope": "session"},
            correlation_id="corr-runtime-sdk",
            traceparent=TRACEPARENT,
            tracestate="vendor=sdk",
            baggage="tenant=demo",
        )
        runs = client.list_runtime_session_runs(
            session.id,
            environment_id="env_default",
            correlation_id="corr-runtime-sdk",
        )
        result = client.call_tool(
            "claims.lookup",
            {"claim_id": "claim_123"},
            correlation_id="corr-runtime-sdk",
            idempotency_key="idem-runtime-sdk",
            runtime_session_id=session.id,
            runtime_run_id=runs[0].id,
        )
        checkpoints = client.list_runtime_checkpoints(
            session.id,
            environment_id="env_default",
            correlation_id="corr-runtime-sdk",
        )
        events = client.stream_runtime_events(
            environment_id="env_default",
            event_type="runtime.session.started",
            last_event_id="evt_previous",
            limit=10,
            runtime_session_id=session.id,
            runtime_run_id=runs[0].id,
            correlation_id="corr-runtime-sdk",
        )

        self.assertEqual(session.thread_id, "thread-sdk")
        self.assertEqual(runs[0].steps[0].checkpoint_id, "sgchk_sdk")
        self.assertEqual(result.result, {"ok": True})
        self.assertEqual(checkpoints[0].checkpoint_id, "sgchk_sdk")
        self.assertEqual(checkpoints[0].recovery_state["checkpoint_count"], 1)
        self.assertEqual(events[0].id, "evt_runtime_sdk")
        self.assertEqual(events[0].payload_json["run_id"], "rtrun_sdk")
        self.assertEqual(calls[0].headers["X-Environment-ID"], "env_default")
        self.assertEqual(calls[1].headers["X-Environment-ID"], "env_default")
        self.assertEqual(calls[2].headers["X-Runtime-Session-ID"], "rtssn_sdk")
        self.assertEqual(calls[2].headers["X-Runtime-Run-ID"], "rtrun_sdk")
        self.assertEqual(calls[4].headers["X-Environment-ID"], "env_default")

    def test_async_runtime_session_methods_thread_tool_context(self) -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if request.method == "POST" and request.url.path == "/api/v1/runtime/sessions":
                return httpx.Response(
                    201,
                    json={
                        "id": "rtssn_async_sdk",
                        "organization_id": "org_default",
                        "environment_id": "env_default",
                        "agent_id": "agent_claims",
                        "agent_name": "Claims Agent",
                        "state": "active",
                        "ring": 2,
                        "created_by_user_id": "user_sdk",
                        "memory_scope": "session",
                        "thread_id": "thread-async-sdk",
                        "started_at": "2026-05-20T00:00:00+00:00",
                        "metadata": {},
                        "actions": [],
                    },
                )
            if request.method == "GET" and request.url.path == "/api/v1/runtime/sessions/rtssn_async_sdk/runs":
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": "rtrun_async_sdk",
                            "organization_id": "org_default",
                            "environment_id": "env_default",
                            "session_id": "rtssn_async_sdk",
                            "thread_id": "thread-async-sdk",
                            "run_type": "session",
                            "status": "running",
                            "recovery_state": {},
                            "metadata": {},
                            "started_at": "2026-05-20T00:00:00+00:00",
                            "updated_at": "2026-05-20T00:00:00+00:00",
                            "steps": [],
                        }
                    ],
                )
            if request.method == "POST" and request.url.path == "/api/v1/tools/claims.lookup/invoke":
                return httpx.Response(
                    200,
                    json={
                        "request_id": "req-async-runtime-sdk",
                        "correlation_id": "corr-async-runtime-sdk",
                        "tool_name": "claims.lookup",
                        "result": {"ok": True},
                        "error": None,
                    },
                )
            return httpx.Response(404, json={"error": {"code": "not_found"}})

        async def exercise() -> None:
            client = _async_client(handler)
            try:
                session = await client.create_runtime_session(
                    agent_id="agent_claims",
                    environment_id="env_default",
                    metadata={"thread_id": "thread-async-sdk"},
                )
                runs = await client.list_runtime_session_runs(
                    session.id,
                    environment_id="env_default",
                )
                result = await client.call_tool(
                    "claims.lookup",
                    {"claim_id": "claim_123"},
                    correlation_id="corr-async-runtime-sdk",
                    idempotency_key="idem-async-runtime-sdk",
                    runtime_session_id=session.id,
                    runtime_run_id=runs[0].id,
                )
            finally:
                await client.close()
            self.assertEqual(session.thread_id, "thread-async-sdk")
            self.assertEqual(runs[0].id, "rtrun_async_sdk")
            self.assertEqual(result.result, {"ok": True})

        asyncio.run(exercise())
        self.assertEqual(calls[0].headers["X-Environment-ID"], "env_default")
        self.assertEqual(calls[1].headers["X-Environment-ID"], "env_default")
        self.assertEqual(calls[2].headers["X-Runtime-Session-ID"], "rtssn_async_sdk")
        self.assertEqual(calls[2].headers["X-Runtime-Run-ID"], "rtrun_async_sdk")

    def test_call_tool_does_not_retry_retryable_status_without_idempotency_key(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(503, json={"error": {"code": "try_again"}})

        client = _client(handler)

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(calls, 1)
        self.assertEqual(raised.exception.code, "try_again")

    def test_call_tool_does_not_retry_idempotency_persistence_failure(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                503,
                headers={"Idempotency-Persistence": "failed"},
                json={
                    "request_id": "req-idem-persist-fail",
                    "correlation_id": "corr-idem-persist-fail",
                    "tool_name": "claims.lookup",
                    "reason_code": "idempotency_persistence_failed",
                    "result": None,
                    "error": {
                        "code": "idempotency_persistence_failed",
                        "message": "Tool execution completed, but the outcome is unknown.",
                    },
                },
            )

        client = _client(handler)
        client.invocation_retry_backoff_seconds = 0.0
        client.invocation_retry_jitter_ratio = 0.0

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool(
                "claims.lookup",
                {"claim_id": "claim_123"},
                idempotency_key="idem-sdk-persist-fail",
            )

        self.assertEqual(calls, 1)
        self.assertEqual(raised.exception.code, "idempotency_persistence_failed")
        self.assertIn("outcome is unknown", str(raised.exception))

    def test_call_tool_does_not_retry_terminal_upstream_execution_failure(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                502,
                json={
                    "request_id": "req-upstream-error",
                    "correlation_id": "corr-upstream-error",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "result": None,
                    "error": {
                        "code": "upstream_error",
                        "message": "Upstream returned status 503.",
                    },
                },
            )

        client = _client(handler)
        client.invocation_retry_backoff_seconds = 0.0
        client.invocation_retry_jitter_ratio = 0.0

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool(
                "claims.lookup",
                {"claim_id": "claim_123"},
                idempotency_key="idem-terminal-upstream-error",
            )

        self.assertEqual(calls, 1)
        self.assertEqual(raised.exception.code, "upstream_error")

    def test_call_tool_does_not_retry_replayed_retryable_response(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                503,
                headers={"Idempotency-Replayed": "true"},
                json={"error": {"code": "try_again"}},
            )

        client = _client(handler)
        client.invocation_retry_backoff_seconds = 0.0
        client.invocation_retry_jitter_ratio = 0.0

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool(
                "claims.lookup",
                {"claim_id": "claim_123"},
                idempotency_key="idem-replayed-retryable",
            )

        self.assertEqual(calls, 1)
        self.assertEqual(raised.exception.code, "try_again")

    def test_async_call_tool_does_not_retry_terminal_upstream_execution_failure(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                502,
                json={
                    "request_id": "req-async-upstream-error",
                    "correlation_id": "corr-async-upstream-error",
                    "tool_name": "claims.lookup",
                    "reason_code": "allowed",
                    "result": None,
                    "error": {
                        "code": "upstream_error",
                        "message": "Upstream returned status 503.",
                    },
                },
            )

        async def exercise() -> None:
            client = _async_client(handler)
            client.invocation_retry_backoff_seconds = 0.0
            client.invocation_retry_jitter_ratio = 0.0
            try:
                with self.assertRaises(ToolGatewayError) as raised:
                    await client.call_tool(
                        "claims.lookup",
                        {"claim_id": "claim_123"},
                        idempotency_key="idem-async-terminal-upstream-error",
                    )
            finally:
                await client.close()
            self.assertEqual(raised.exception.code, "upstream_error")

        asyncio.run(exercise())
        self.assertEqual(calls, 1)

    def test_call_tool_rejects_invalid_idempotency_key_locally(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json={}))

        with self.assertRaisesRegex(ToolGatewayValidationError, "idempotency_key"):
            client.call_tool(
                "claims.lookup",
                {"claim_id": "claim_123"},
                idempotency_key="bad key",
            )

    def test_list_tools_returns_isolated_schema_copies_from_cache(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler, cache_tools=True)

        first = client.list_tools()[0]
        self.assertIsNotNone(first.input_schema_json)
        assert first.input_schema_json is not None
        first.input_schema_json["mutated"] = True
        second = client.list_tools()[0]

        self.assertEqual(calls, 1)
        self.assertEqual(second.input_schema_json, {"type": "object"})

    def test_cached_discovery_does_not_bypass_invocation_denial(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, json=[TOOL_FIXTURE])
            return httpx.Response(
                403,
                json={
                    "request_id": "req-revoked",
                    "correlation_id": "corr-revoked",
                    "tool_name": "claims.lookup",
                    "reason_code": "permission_revoked",
                    "error": {"code": "permission_revoked"},
                },
            )

        client = _client(handler, cache_tools=True)

        self.assertEqual(client.get_tool("claims.lookup").name, "claims.lookup")
        with self.assertRaises(ToolDeniedError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.reason_code, "permission_revoked")

    def test_top_level_gateway_error_code_is_preserved(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                500,
                json={"code": "GATEWAY_UNAVAILABLE", "message": "Gateway down."},
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "GATEWAY_UNAVAILABLE")

    def test_retry_after_header_is_exposed_on_gateway_errors(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                429,
                json={"code": "RATE_LIMITED", "message": "Retry later."},
                headers={"Retry-After": "5"},
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.retry_after_seconds, 5.0)

    def test_generic_403_remains_gateway_error(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                403,
                json={"error": {"code": "forbidden", "message": "Proxy denied."}},
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertNotIsInstance(raised.exception, ToolDeniedError)
        self.assertEqual(raised.exception.code, "forbidden")

    def test_structured_policy_403_raises_denied_error(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                403,
                json={
                    "request_id": "req-denied",
                    "correlation_id": "corr-denied",
                    "tool_name": "claims.lookup",
                    "decision": {"decision": "deny"},
                    "reason_code": "permission_missing",
                    "error": {"code": "permission_missing"},
                },
            )
        )

        with self.assertRaises(ToolDeniedError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.reason_code, "permission_missing")

    def test_check_compatibility_reads_authenticated_capabilities_contract(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/api/v1/gateway/capabilities")
            return httpx.Response(
                200,
                json={
                    "gateway_contract_version": "tool-gateway.v1",
                    "min_sdk_version": "0.1.0",
                    "sdk_package": "ophanix-tool-gateway-sdk",
                    "max_payload_bytes": 1_000_000,
                    "max_response_bytes": 1_000_000,
                    "max_discovery_page_size": 200,
                    "supported_pagination_modes": ["cursor", "offset"],
                    "supports_idempotency": True,
                    "idempotency_in_progress_ttl_seconds": 600,
                    "idempotency_replay_retention_seconds": 604800,
                },
            )

        client = _client(handler)

        compatibility = client.check_compatibility()

        self.assertTrue(compatibility.compatible)
        self.assertEqual(compatibility.gateway_contract_version, "tool-gateway.v1")
        self.assertEqual(compatibility.expected_gateway_contract_version, "tool-gateway.v1")
        self.assertTrue(compatibility.min_sdk_version_satisfied)
        self.assertIsNone(compatibility.incompatibility_reason)
        self.assertEqual(compatibility.max_payload_bytes, 1_000_000)
        self.assertEqual(compatibility.max_response_bytes, 1_000_000)
        self.assertEqual(compatibility.max_discovery_page_size, 200)
        self.assertEqual(compatibility.supported_pagination_modes, ("cursor", "offset"))
        self.assertTrue(compatibility.supports_idempotency)
        self.assertEqual(compatibility.idempotency_in_progress_ttl_seconds, 600)
        self.assertEqual(compatibility.idempotency_replay_retention_seconds, 604800)

    def test_check_compatibility_respects_gateway_min_sdk_version(self) -> None:
        client = _client(
            lambda request: httpx.Response(
                200,
                json={
                    "gateway_contract_version": "tool-gateway.v1",
                    "min_sdk_version": "999.0.0",
                    "sdk_package": "ophanix-tool-gateway-sdk",
                },
            )
        )

        compatibility = client.check_compatibility()

        self.assertFalse(compatibility.compatible)
        self.assertFalse(compatibility.min_sdk_version_satisfied)
        self.assertEqual(compatibility.incompatibility_reason, "sdk_version_below_gateway_minimum")

    def test_require_compatible_gateway_checks_once_before_runtime_calls(self) -> None:
        paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            paths.append(request.url.path)
            if request.url.path == "/api/v1/gateway/capabilities":
                return httpx.Response(
                    200,
                    json={
                        "gateway_contract_version": "tool-gateway.v1",
                        "min_sdk_version": "0.1.0",
                        "sdk_package": "ophanix-tool-gateway-sdk",
                    },
                )
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler, require_compatible_gateway=True)

        self.assertEqual([tool.name for tool in client.list_tools()], ["claims.lookup"])
        self.assertEqual([tool.name for tool in client.list_tools()], ["claims.lookup"])
        self.assertEqual(paths.count("/api/v1/gateway/capabilities"), 1)

    def test_require_compatible_gateway_fails_before_invocation_when_contract_mismatches(self) -> None:
        paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            paths.append(request.url.path)
            if request.url.path == "/api/v1/gateway/capabilities":
                return httpx.Response(
                    200,
                    json={
                        "gateway_contract_version": "tool-gateway.v0",
                        "min_sdk_version": "0.1.0",
                        "sdk_package": "ophanix-tool-gateway-sdk",
                    },
                )
            return httpx.Response(200, json={})

        client = _client(handler, require_compatible_gateway=True)

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "gateway_contract_version_mismatch")
        self.assertNotIn("/api/v1/tools/claims.lookup/invoke", paths)

    def test_from_config_constructs_client_without_repeating_every_option(self) -> None:
        config = ToolGatewayClientConfig(
            timeout_seconds=2.5,
            cache_tools=True,
            cache_ttl_seconds=10.0,
            discovery_max_retries=0,
            require_compatible_gateway=True,
            include_raw_response=True,
        )

        client = OphanixToolGatewayClient.from_config(
            base_url="https://gateway.example.test",
            token_provider=StaticTokenProvider("sdk-token"),
            config=config,
            http_client=httpx.Client(
                transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=[]))
            ),
        )

        self.assertEqual(client.timeout_seconds, 2.5)
        self.assertTrue(client.cache_tools)
        self.assertEqual(client.cache_ttl_seconds, 10.0)
        self.assertEqual(client.discovery_max_retries, 0)
        self.assertTrue(client.require_compatible_gateway)
        self.assertTrue(client.include_raw_response)

    def test_list_all_tools_enforces_max_total(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            offset = int(request.url.params.get("offset", "0"))
            tool = {**TOOL_FIXTURE, "id": f"tool_{offset}", "name": f"claims.lookup.{offset}"}
            return httpx.Response(200, json=[tool])

        client = _client(handler)

        with self.assertRaises(ToolGatewayError) as raised:
            client.list_all_tools(page_size=1, max_total=1)

        self.assertEqual(raised.exception.code, "tool_discovery_too_large")

    def test_list_all_tools_has_default_total_cap(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            offset = int(request.url.params.get("offset", "0"))
            return httpx.Response(
                200,
                json=[
                    {**TOOL_FIXTURE, "id": f"tool_{offset}_{index}", "name": f"claims.lookup.{offset}.{index}"}
                    for index in range(200)
                ],
            )

        client = _client(handler)

        with self.assertRaises(ToolGatewayError) as raised:
            client.list_all_tools()

        self.assertEqual(raised.exception.code, "tool_discovery_too_large")
        self.assertLessEqual(calls, 51)

    def test_call_tool_rejects_payloads_above_depth_cap(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json={}))
        payload: dict[str, Any] = {}
        cursor = payload
        for index in range(60):
            cursor["next"] = {}
            cursor = cursor["next"]

        with self.assertRaisesRegex(ToolGatewayValidationError, "maximum nesting depth"):
            client.call_tool("claims.lookup", payload)

    def test_streaming_response_cap_blocks_body_without_content_length(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                200,
                content=b"x" * 11,
                headers={"content-type": "application/json"},
            ),
        )
        client.max_response_bytes = 10

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.code, "response_too_large")

    def test_list_tools_status_argument_warns_as_deprecated(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json=[]))

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(client.list_tools(status="active"), [])

    def test_token_provider_rejects_bearer_prefixed_token_locally(self) -> None:
        client = OphanixToolGatewayClient(
            base_url="https://gateway.example.test",
            token_provider=StaticTokenProvider("Bearer sdk-token"),
            http_client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200))),
        )

        with self.assertRaisesRegex(ToolGatewayValidationError, "without the Bearer prefix"):
            client.list_tools()

    def test_token_provider_rejects_tokens_above_gateway_cap_locally(self) -> None:
        client = OphanixToolGatewayClient(
            base_url="https://gateway.example.test",
            token_provider=StaticTokenProvider("a" * 4097),
            http_client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200))),
        )

        with self.assertRaisesRegex(ToolGatewayValidationError, "4096 characters or fewer"):
            client.list_tools()

    def test_environment_token_provider_reads_current_environment_value(self) -> None:
        provider = EnvironmentTokenProvider("OPHANIX_TEST_GATEWAY_TOKEN")

        with patch.dict("os.environ", {"OPHANIX_TEST_GATEWAY_TOKEN": "first-token"}):
            self.assertEqual(provider.get_token(), "first-token")
        with patch.dict("os.environ", {"OPHANIX_TEST_GATEWAY_TOKEN": "second-token"}):
            self.assertEqual(provider.get_token(), "second-token")

    def test_get_tool_not_found_sanitizes_lookup_text(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json=[]))

        with self.assertRaises(ToolGatewayError) as raised:
            client.get_tool("token=super-secret-value-that-should-not-be-logged")

        self.assertEqual(raised.exception.code, "tool_not_visible")
        self.assertIn("token=[redacted]", raised.exception.message)
        self.assertNotIn("super-secret-value", raised.exception.message)

    def test_calls_after_close_raise_stable_sdk_error(self) -> None:
        client = _client(lambda _request: httpx.Response(200, json=[]))
        client.close()

        with self.assertRaises(ToolGatewayError) as raised:
            client.list_tools()

        self.assertEqual(raised.exception.code, "client_closed")

    def test_custom_http_client_without_stream_is_rejected_by_default(self) -> None:
        with self.assertRaisesRegex(ToolGatewayValidationError, "must provide stream"):
            OphanixToolGatewayClient(
                base_url="https://gateway.example.test",
                token_provider=StaticTokenProvider("sdk-token"),
                http_client=cast(httpx.Client, _BufferedOnlyClient()),
            )

    def test_strict_event_hook_mode_surfaces_hook_failures(self) -> None:
        def failing_hook(_event: Mapping[str, Any]) -> None:
            raise RuntimeError("hook down")

        client = _client(
            lambda _request: httpx.Response(200, json=[]),
            event_hook=failing_hook,
            raise_event_hook_errors=True,
        )

        with self.assertRaisesRegex(RuntimeError, "hook down"):
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

    def test_list_all_tools_deduplicates_offset_page_overlap(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            offset = int(request.url.params.get("offset", "0"))
            if offset < 2:
                return httpx.Response(200, json=[TOOL_FIXTURE])
            return httpx.Response(200, json=[])

        client = _client(handler)

        tools = client.list_all_tools(page_size=1)

        self.assertEqual([tool.id for tool in tools], ["tool_claims_lookup"])

    def test_list_all_tools_prefers_cursor_pages_when_gateway_supports_them(self) -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            self.assertEqual(request.url.params.get("pagination"), "cursor")
            if "cursor" not in request.url.params:
                return httpx.Response(
                    200,
                    json={
                        "tools": [{**TOOL_FIXTURE, "id": "tool_1", "name": "claims.lookup.one"}],
                        "next_cursor": "cursor-2",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "tools": [{**TOOL_FIXTURE, "id": "tool_2", "name": "claims.lookup.two"}],
                    "next_cursor": None,
                },
            )

        client = _client(handler)

        tools = client.list_all_tools(page_size=1)

        self.assertEqual([tool.name for tool in tools], ["claims.lookup.one", "claims.lookup.two"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1].url.params["cursor"], "cursor-2")

    def test_event_hook_receives_retry_and_elapsed_telemetry(self) -> None:
        events: list[Mapping[str, Any]] = []
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(503, json={"error": {"code": "try_again"}})
            return httpx.Response(200, json=[TOOL_FIXTURE])

        client = _client(handler, event_hook=events.append)
        client.discovery_max_retries = 1
        client.discovery_retry_backoff_seconds = 0.0

        self.assertEqual([tool.name for tool in client.list_tools()], ["claims.lookup"])

        retry_events = [event for event in events if event["event"] == "tool_discovery.retry"]
        self.assertEqual(len(retry_events), 1)
        self.assertEqual(retry_events[0]["attempt"], 1)
        self.assertEqual(retry_events[0]["status_code"], 503)

    def test_success_event_hook_includes_elapsed_ms(self) -> None:
        events: list[Mapping[str, Any]] = []
        client = _client(
            lambda _request: httpx.Response(
                200,
                json={
                    "request_id": "req-sdk",
                    "correlation_id": "corr-sdk",
                    "tool_name": "claims.lookup",
                    "result": {"ok": True},
                    "error": None,
                },
            ),
            event_hook=events.append,
        )

        client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        success = [event for event in events if event["event"] == "tool_call.success"][0]
        self.assertIsInstance(success["elapsed_ms"], float)
        self.assertEqual(success["schema_version"], "tool-gateway-sdk.telemetry.v1")

    def test_error_event_hook_includes_response_request_and_correlation_ids(self) -> None:
        events: list[Mapping[str, Any]] = []
        client = _client(
            lambda _request: httpx.Response(
                502,
                json={
                    "request_id": "req-error-event",
                    "correlation_id": "corr-error-event",
                    "error": {"code": "upstream_error"},
                },
            ),
            event_hook=events.append,
        )

        with self.assertRaises(ToolGatewayError):
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        error = [event for event in events if event["event"] == "tool_call.error"][0]
        self.assertEqual("req-error-event", error["request_id"])
        self.assertEqual("corr-error-event", error["correlation_id"])

    def test_denied_event_hook_includes_response_request_and_correlation_ids(self) -> None:
        events: list[Mapping[str, Any]] = []
        client = _client(
            lambda _request: httpx.Response(
                403,
                json={
                    "request_id": "req-denied-event",
                    "correlation_id": "corr-denied-event",
                    "reason_code": "tool_policy_denied",
                    "error": {
                        "code": "tool_call_denied",
                        "message": "Tool call denied.",
                    },
                },
            ),
            event_hook=events.append,
        )

        with self.assertRaises(ToolDeniedError):
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        denied = [event for event in events if event["event"] == "tool_call.denied"][0]
        self.assertEqual("req-denied-event", denied["request_id"])
        self.assertEqual("corr-denied-event", denied["correlation_id"])

    def test_allow_insecure_http_for_non_local_gateway_warns(self) -> None:
        with self.assertWarns(RuntimeWarning):
            _client(
                lambda _request: httpx.Response(200, json=[]),
                base_url="http://gateway.example.test",
                allow_insecure_http=True,
            )

    def test_allow_buffered_custom_http_client_option_warns_but_does_not_bypass_stream_requirement(self) -> None:
        with self.assertWarns(DeprecationWarning):
            with self.assertRaisesRegex(ToolGatewayValidationError, "must provide stream"):
                OphanixToolGatewayClient(
                    base_url="https://gateway.example.test",
                    token_provider=StaticTokenProvider("sdk-token"),
                    http_client=cast(httpx.Client, _BufferedOnlyClient()),
                    allow_buffered_custom_http_client=True,
                )

    def test_error_response_sanitization_redacts_common_pii_keys(self) -> None:
        client = _client(
            lambda _request: httpx.Response(
                500,
                json={
                    "error": {
                        "code": "upstream_failed",
                        "email": "patient@example.test",
                        "message": "email: patient@example.test",
                        "ssn": "123-45-6789",
                    }
                },
            )
        )

        with self.assertRaises(ToolGatewayError) as raised:
            client.call_tool("claims.lookup", {"claim_id": "claim_123"})

        self.assertEqual(raised.exception.response_body["error"]["email"], "[redacted]")
        self.assertEqual(raised.exception.response_body["error"]["ssn"], "[redacted]")
        self.assertNotIn("patient@example.test", str(raised.exception.response_body))


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    base_url: str = "https://gateway.example.test",
    cache_tools: bool = False,
    event_hook: Callable[[Mapping[str, Any]], None] | None = None,
    raise_event_hook_errors: bool = False,
    allow_insecure_http: bool = False,
    require_compatible_gateway: bool = False,
    include_raw_response: bool = False,
) -> OphanixToolGatewayClient:
    return OphanixToolGatewayClient(
        base_url=base_url,
        token_provider=StaticTokenProvider("sdk-token"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        cache_tools=cache_tools,
        event_hook=event_hook,
        raise_event_hook_errors=raise_event_hook_errors,
        allow_insecure_http=allow_insecure_http,
        require_compatible_gateway=require_compatible_gateway,
        include_raw_response=include_raw_response,
    )


def _async_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> AsyncOphanixToolGatewayClient:
    return AsyncOphanixToolGatewayClient(
        base_url="https://gateway.example.test",
        token_provider=StaticTokenProvider("sdk-token"),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


class _BufferedOnlyClient:
    def get(self, *_args: Any, **_kwargs: Any) -> httpx.Response:
        return httpx.Response(200, json=[])

    def post(self, *_args: Any, **_kwargs: Any) -> httpx.Response:
        return httpx.Response(200, json={})

    def close(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
