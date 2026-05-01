# Trust Scoring

Trust scoring turns agent behavior into an access-control signal. Instead of
granting a fixed permission forever, the platform keeps a score that can go up
with good behavior and down after violations, failures, drift, or risky peer
interactions.

## Where It Lives

- [Reward scoring](../packages/agent-mesh/src/agentmesh/reward/scoring.py)
- [Network trust decay](../packages/agent-mesh/src/agentmesh/reward/trust_decay.py)
- [Shared trust types](../packages/agent-mesh/src/agentmesh/trust_types.py)
- [Trust policy DSL](../packages/agent-mesh/src/agentmesh/governance/trust_policy.py)
- [Trust handshake](../packages/agent-mesh/src/agentmesh/trust/handshake.py)
- [Trust dashboard example](../packages/agent-mesh/examples/06-trust-score-dashboard/README.md)
- [Feature deep dive](../features/trust-scoring/technical-deep-dive.md)

## Score Model

The richer AgentMesh scoring model uses a `TrustScore` in the range 0 to 1000.
It aggregates reward dimensions:

- `policy_compliance`
- `resource_efficiency`
- `output_quality`
- `security_posture`
- `collaboration_health`

Each dimension receives `RewardSignal` events with a value from 0.0 to 1.0 and
an optional weight. Dimension scores update with an exponential moving average.
The total score maps to tiers:

- `verified_partner`
- `trusted`
- `standard`
- `probationary`
- `untrusted`

There is also a lightweight shared `TrustTracker` that uses 0.0 to 1.0 scores.
That is useful for integrations that need a simple canonical type.

## Trust Decay And Network Effects

`NetworkTrustEngine` adds three ideas:

- Temporal decay: score can slowly fall if no positive signals arrive.
- Trust contagion: if agent A frequently interacts with agent B, B's severe
  trust event can partially affect A.
- Regime detection: sudden action-distribution changes can raise a
  `RegimeChangeAlert`.

This is useful for multi-agent systems where trust is not isolated. A highly
trusted orchestrator repeatedly delegating to unsafe workers should not look
perfect forever.

## Policy Integration

Trust scores become policy context. You can require:

- minimum trust score for peer communication,
- higher score for write or deployment actions,
- lower rate limits for probationary agents,
- human approval below a threshold,
- credential revocation below a revocation threshold.

The trust policy DSL in [trust_policy.py](../packages/agent-mesh/src/agentmesh/governance/trust_policy.py)
supports dot-notated fields, comparison operators, priorities, and actions like
`allow`, `deny`, `warn`, and `require_approval`.

## Demos To Run

```bash
cd ophanix-platform/packages/agent-mesh/examples/06-trust-score-dashboard
pip install -r requirements.txt
streamlit run trust_dashboard.py
```

The general dashboard also has a trust heatmap:

```bash
cd ophanix-platform/demo/governance-dashboard
pip install -r requirements.txt
streamlit run app.py
```

For protocol and trust interaction:

```bash
cd ophanix-platform/packages/agent-mesh/examples/07-multi-vendor-collaboration
python demo.py
```

## What To Remember

Trust scoring should not be ornamental. If the score does not change access,
rate limits, review requirements, or lifecycle state, it is just analytics.
The strong Ophanix product angle is to make trust an operational control.
