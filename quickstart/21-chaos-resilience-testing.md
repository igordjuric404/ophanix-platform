# Chaos Resilience Testing

Chaos resilience testing intentionally injects failures into an agent system to
see whether the system degrades safely. It turns "we think this is resilient"
into evidence.

For agent governance, chaos is not only latency and errors. The package also
models adversarial faults such as prompt injection, policy bypass, privilege
escalation, data exfiltration, tool abuse, identity spoofing, contradictory
instructions, and trust perturbation.

## Where It Lives

- [Chaos engine](../packages/agent-sre/src/agent_sre/chaos/engine.py)
- [Chaos library](../packages/agent-sre/src/agent_sre/chaos/library.py)
- [Chaos scheduler](../packages/agent-sre/src/agent_sre/chaos/scheduler.py)
- [Adversarial chaos](../packages/agent-sre/src/agent_sre/chaos/adversarial.py)
- [Chaos example](../packages/agent-sre/examples/chaos_test.py)
- [Chaos chatbot example](../packages/agent-sre/examples/chaos-chatbot/README.md)
- [Feature deep dive](../features/chaos-resilience-testing/technical-deep-dive.md)

## Fault Types

The current `FaultType` enum includes:

- latency injection,
- error injection,
- timeout injection,
- prompt injection,
- policy bypass,
- privilege escalation,
- data exfiltration,
- tool abuse,
- identity spoofing,
- deadlock injection,
- contradictory instruction,
- trust perturbation.

Convenience constructors include:

- `Fault.latency_injection(...)`,
- `Fault.error_injection(...)`,
- `Fault.timeout_injection(...)`,
- `Fault.prompt_injection(...)`,
- `Fault.policy_bypass(...)`,
- `Fault.privilege_escalation(...)`,
- `Fault.data_exfiltration(...)`,
- `Fault.tool_abuse(...)`,
- `Fault.identity_spoofing(...)`,
- `Fault.deadlock_injection(...)`,
- `Fault.contradictory_instruction(...)`,
- `Fault.trust_perturbation(...)`.

There are also legacy aliases like `tool_timeout`, `tool_error`,
`llm_latency`, `credential_expire`, `network_partition`, and `cost_spike`.

## Experiment Model

`ChaosExperiment` tracks:

- experiment id,
- name,
- target agent,
- faults,
- duration,
- abort conditions,
- blast radius,
- state,
- injection events,
- start/end times,
- abort reason,
- resilience score.

Experiment states are:

- `pending`,
- `running`,
- `completed`,
- `aborted`,
- `failed`.

Abort conditions are safety rails. For example, abort if success rate drops
below a threshold or cost rises above a threshold.

## Minimal Example

```python
from agent_sre.chaos.engine import AbortCondition, ChaosExperiment, Fault

experiment = ChaosExperiment(
    name="search-tool-timeout",
    target_agent="agent:researcher",
    faults=[
        Fault.timeout_injection("web_search", delay_ms=30000, rate=0.25),
        Fault.prompt_injection("agent:researcher", technique="direct_override"),
    ],
    duration_seconds=60,
    blast_radius=0.10,
    abort_conditions=[
        AbortCondition(metric="success_rate", threshold=0.80, comparator="lte"),
    ],
)

experiment.start()
for fault in experiment.faults:
    experiment.inject_fault(fault)

if experiment.check_abort({"success_rate": 0.75}):
    print(experiment.abort_reason)
else:
    score = experiment.calculate_resilience(
        baseline_success_rate=0.98,
        experiment_success_rate=0.94,
    )
    experiment.complete(score)

print(experiment.to_dict())
```

## What Good Chaos Looks Like

A useful chaos test is small, measured, and reversible:

- choose one hypothesis,
- keep blast radius low,
- define abort conditions,
- measure baseline behavior first,
- inject one or two faults,
- measure recovery,
- record the result,
- convert failures into backlog work.

For Ophanix, chaos tests can become compliance evidence:

- "we tested prompt-injection resilience weekly",
- "credential-expiry chaos does not break recovery",
- "fallback agents activate when trust drops",
- "kill switch stops in-flight workflows."

## Demos To Run

Install Agent SRE:

```bash
cd ophanix-platform
pip install -e "packages/agent-sre[dev]"
```

Run the base chaos example:

```bash
python packages/agent-sre/examples/chaos_test.py
```

Run the chatbot-specific chaos demo:

```bash
cd ophanix-platform/packages/agent-sre/examples/chaos-chatbot
python demo.py
```

Review the scenario schedule:

```bash
cd ophanix-platform
cat packages/agent-sre/examples/chaos/schedules.yaml
```

## What To Remember

Chaos testing should not be theater. The useful question is not "can we break
it?" The useful question is "when it breaks, does governance contain the
damage, record the evidence, and recover cleanly?"
