# Rogue Agent Detection

Rogue agent detection looks for agents whose behavior no longer matches their
expected profile. It is the runtime counterpart to static policy. Policy says
what should happen. Rogue detection asks whether observed behavior suggests the
agent has drifted, looped, been compromised, or is abusing tools.

## Where It Lives

- [Rogue detector](../packages/agent-sre/src/agent_sre/anomaly/rogue_detector.py)
- [General anomaly detector](../packages/agent-sre/src/agent_sre/anomaly/detector.py)
- [Feature deep dive](../features/rogue-agent-detection/technical-deep-dive.md)
- [Agent SRE examples](../packages/agent-sre/examples/README.md)

## Signals Used

The implemented `RogueAgentDetector` combines three analyzers:

1. Tool-call frequency.
   - Tracks calls per time window.
   - Uses z-score against previous windows.
   - Flags sudden spikes.
2. Action entropy.
   - Uses Shannon entropy over action names.
   - Very low entropy can mean a loop.
   - Very high entropy can mean erratic behavior.
3. Capability profile deviation.
   - Registers an expected allowed-tool set per agent.
   - Counts calls outside that profile.
   - Produces a violation ratio.

The final risk is a composite score:

```text
composite = frequency_score + entropy_score + capability_score
```

Risk levels are:

- under 1.0: low,
- 1.0 to under 2.0: medium,
- 2.0 to under 3.0: high,
- 3.0 or above: critical.

By default, quarantine is recommended at `high` and above.

## Tamper-Evident Assessments

Every `RogueAssessment` is linked into a hash chain:

- `previous_hash`,
- `entry_hash`,
- canonical assessment payload.

`verify_assessment_chain()` walks the history and confirms the chain still
matches. This is useful when you need to prove that detection results were not
edited after the fact.

## Example

```python
from agent_sre.anomaly.rogue_detector import RogueAgentDetector

detector = RogueAgentDetector()
detector.register_capability_profile(
    "agent:researcher",
    allowed_tools=["web_search", "summarize"],
)

for _ in range(20):
    detector.record_action(
        agent_id="agent:researcher",
        action="delete_records",
        tool_name="database_delete",
    )

assessment = detector.assess("agent:researcher")
print(assessment.risk_level.value)
print(assessment.quarantine_recommended)
print(assessment.to_dict())

print(detector.verify_assessment_chain())
```

## How To Use It In Ophanix

The detector should sit beside your telemetry pipeline. Every time an agent
takes an action, feed the detector:

- agent id,
- action name,
- tool name,
- timestamp if you have one.

Then periodically assess active agents and feed results into policy:

- medium risk: increase logging and reduce concurrency,
- high risk: require human approval,
- critical risk: suspend credentials or trigger kill switch,
- repeated capability deviation: update lifecycle state or open an incident.

## Demos To Run

Install Agent SRE and run the quickstart:

```bash
cd ophanix-platform
pip install -e "packages/agent-sre[dev]"
python packages/agent-sre/examples/quickstart.py
```

Run the broader examples:

```bash
python packages/agent-sre/examples/slo_alerting.py
python packages/agent-sre/examples/cost_guard.py
python packages/agent-sre/examples/chaos_test.py
```

There is not a dedicated rogue-detector demo script, but the Python snippet
above uses the implemented detector directly.

## What To Remember

Rogue detection is not a single "bad agent" label. It is a set of behavioral
signals. The power comes from connecting those signals to concrete responses:
throttle, isolate, require approval, rotate credentials, or stop the agent.
