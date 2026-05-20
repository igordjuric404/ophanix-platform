# SPDX-License-Identifier: MIT
"""Create a runtime session and call a governed tool inside its run."""

from __future__ import annotations

import os
from uuid import uuid4

from ophanix_tool_gateway import EnvironmentTokenProvider, OphanixToolGatewayClient


def main() -> None:
    base_url = os.environ.get("OPHANIX_GATEWAY_BASE_URL", "https://gateway.example.com")
    environment_id = os.environ.get("OPHANIX_ENVIRONMENT_ID", "env_default")
    agent_id = os.environ.get("OPHANIX_AGENT_ID", "agent_claims")
    claim_id = os.environ.get("OPHANIX_CLAIM_ID", "claim_123")
    correlation_id = f"runtime-session-example:{uuid4().hex}"

    with OphanixToolGatewayClient(
        base_url=base_url,
        token_provider=EnvironmentTokenProvider(),
    ) as client:
        session = client.create_runtime_session(
            agent_id=agent_id,
            environment_id=environment_id,
            metadata={"thread_id": claim_id, "memory_scope": "session"},
            correlation_id=correlation_id,
        )
        runs = client.list_runtime_session_runs(
            session.id,
            environment_id=environment_id,
            correlation_id=correlation_id,
        )
        if not runs:
            raise RuntimeError("Runtime session did not create an inspectable run.")
        result = client.call_tool(
            "claims.lookup",
            {"claim_id": claim_id},
            correlation_id=correlation_id,
            idempotency_key=f"claims.lookup:{uuid4().hex}",
            runtime_session_id=session.id,
            runtime_run_id=runs[0].id,
        )
        checkpoints = client.list_runtime_checkpoints(
            session.id,
            environment_id=environment_id,
            correlation_id=correlation_id,
        )
        events = client.stream_runtime_events(
            environment_id=environment_id,
            runtime_session_id=session.id,
            runtime_run_id=runs[0].id,
            correlation_id=correlation_id,
        )

    print(
        {
            "session_id": session.id,
            "run_id": runs[0].id,
            "result": result.body,
            "checkpoint_ids": [checkpoint.checkpoint_id for checkpoint in checkpoints],
            "event_ids": [event.id for event in events],
        }
    )


if __name__ == "__main__":
    main()
