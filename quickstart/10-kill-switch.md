# Kill Switch

The kill switch is the emergency stop for agents. It lets the runtime terminate
an agent, hand off in-flight saga steps when possible, and record why the stop
happened.

## Where It Lives

- [Kill switch implementation](../packages/agent-hypervisor/src/hypervisor/security/kill_switch.py)
- [Rate limiter](../packages/agent-hypervisor/src/hypervisor/security/rate_limiter.py)
- [Runtime exports](../packages/agent-runtime/src/agent_runtime/__init__.py)
- [Tutorial](../docs/tutorials/14-kill-switch-and-rate-limiting.md)
- [Feature deep dive](../features/kill-switch/technical-deep-dive.md)

## What It Tracks

`KillResult` records:

- kill id,
- agent DID,
- session id,
- reason,
- timestamp,
- step handoffs,
- handoff success count,
- whether compensation was triggered,
- whether termination callback ran,
- free-form details.

Kill reasons include:

- behavioral drift,
- rate limit,
- ring breach,
- manual,
- quarantine timeout,
- session timeout.

## How It Works

1. Agents register a termination callback with `register_agent()`.
2. Substitute agents can be registered per session.
3. When `kill()` is called, the switch looks for a substitute.
4. In-flight saga steps are either handed off to the substitute or marked for
   compensation.
5. The registered termination callback runs.
6. The result is appended to kill history.
7. The killed agent is removed from the process and substitute registries.

The current implementation is callback-based. In production, those callbacks
could stop a process, revoke a token, isolate a container, scale down a pod, or
mark the lifecycle state as suspended/decommissioning.

## Relationship To Other Features

The kill switch is usually triggered by something else:

- rogue-agent detector recommends quarantine,
- circuit breaker sees cascading failure,
- rate limiter detects runaway calls,
- ring breach detector sees privilege escalation attempts,
- lifecycle manager decommissions an orphaned agent,
- human operator pushes the button.

Ophanix should expose both manual and automated kill paths, and every kill
should be auditable.

## Demos To Run

Read the tutorial:

```bash
cd ophanix-platform
cat docs/tutorials/14-kill-switch-and-rate-limiting.md
```

Explore the implementation:

```python
from hypervisor.security.kill_switch import KillReason, KillSwitch

kills = KillSwitch()
kills.register_agent("did:mesh:agent-1", lambda: print("terminated"))
result = kills.kill(
    agent_did="did:mesh:agent-1",
    session_id="session-1",
    reason=KillReason.MANUAL,
    in_flight_steps=[{"step_id": "step-1", "saga_id": "saga-1"}],
)
print(result.terminated)
print(result.compensation_triggered)
```

## What To Remember

A kill switch is only useful if it is wired into real control points. For
Ophanix, avoid making it just a dashboard button. It should revoke credentials,
stop runtime execution, update lifecycle state, and leave a forensic record.
