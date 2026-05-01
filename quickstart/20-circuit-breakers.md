# Circuit Breakers

Circuit breakers stop repeated failures from cascading through a multi-agent
system. If one agent, tool, model provider, or downstream service keeps failing,
the breaker opens and blocks more calls until a recovery window passes.

This is especially important for agent systems because agents often retry,
delegate, or call compensating tools. Without a breaker, one failing dependency
can create a large blast radius.

## Where It Lives

- [SRE circuit breaker](../packages/agent-sre/src/agent_sre/cascade/circuit_breaker.py)
- [Incident circuit breaker compatibility layer](../packages/agent-sre/src/agent_sre/incidents/circuit_breaker.py)
- [Circuit breaker feature deep dive](../features/circuit-breakers/technical-deep-dive.md)
- [Agent SRE examples](../packages/agent-sre/examples/README.md)

## States

The implemented circuit breaker has three states:

- `CLOSED`: calls are allowed.
- `OPEN`: calls are blocked.
- `HALF_OPEN`: a limited number of trial calls are allowed to check recovery.

The default config:

- opens after 5 failures,
- waits 30 seconds before recovery trial,
- allows 1 half-open test call.

## Basic Usage

```python
from agent_sre.cascade.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitOpenError,
)

breaker = CircuitBreaker(
    "agent:researcher",
    CircuitBreakerConfig(failure_threshold=2, recovery_timeout_seconds=10),
)

def flaky_tool():
    raise RuntimeError("provider unavailable")

for _ in range(2):
    try:
        breaker.call(flaky_tool)
    except RuntimeError:
        pass

try:
    breaker.call(flaky_tool)
except CircuitOpenError as exc:
    print(exc.agent_id, exc.retry_after)
```

You can also provide a fallback:

```python
result = breaker.call(expensive_or_fragile_tool, fallback={"status": "degraded"})
```

If the circuit is open, the fallback is returned instead of raising.

## Cascade Detection

`CascadeDetector` manages breakers for multiple agents and reports when enough
agents are affected to count as a cascade:

```python
from agent_sre.cascade.circuit_breaker import CascadeDetector

detector = CascadeDetector(
    agents=["agent:a", "agent:b", "agent:c"],
    cascade_threshold=2,
)

breaker = detector.get_breaker("agent:a")
breaker.record_failure()
breaker.record_failure()
breaker.record_failure()
breaker.record_failure()
breaker.record_failure()

print(detector.get_affected_agents())
print(detector.check_cascade())
```

## How It Connects To Policy

Circuit breakers should feed policy decisions:

- open breaker for a tool: deny more calls to that tool,
- open breaker for an agent: route to fallback agent,
- cascade detected: pause the workflow or kill the session,
- half-open state: allow only low-risk test calls,
- recovery: restore normal autonomy gradually.

For Ophanix, this is a strong product story: governance is not just blocking bad
behavior. It also keeps production systems stable when normal dependencies
misbehave.

## Demos To Run

Install Agent SRE:

```bash
cd ophanix-platform
pip install -e "packages/agent-sre[dev]"
```

Run the quickstart and chaos examples:

```bash
python packages/agent-sre/examples/quickstart.py
python packages/agent-sre/examples/chaos_test.py
```

The unit tests are also a compact executable specification:

```bash
pytest packages/agent-sre/tests/unit/test_circuit_breaker.py
```

## What To Remember

Circuit breakers are reliability guardrails. They do not decide whether an
action is morally or legally allowed; they decide whether the system is healthy
enough to keep trying.
