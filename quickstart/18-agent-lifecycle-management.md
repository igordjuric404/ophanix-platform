# Agent Lifecycle Management

Agent lifecycle management tracks an agent from request to retirement. It
answers the operational questions that policy alone cannot:

- who owns this agent?
- why does it exist?
- was it approved?
- is it active?
- are its credentials fresh?
- did it stop heartbeating?
- has it been decommissioned?

## Where It Lives

- [Lifecycle manager](../packages/agent-mesh/src/agentmesh/lifecycle/manager.py)
- [Lifecycle models](../packages/agent-mesh/src/agentmesh/lifecycle/models.py)
- [Orphan detector](../packages/agent-mesh/src/agentmesh/lifecycle/orphan_detector.py)
- [Lifecycle credentials](../packages/agent-mesh/src/agentmesh/lifecycle/credentials.py)
- [Lifecycle tutorial](../docs/tutorials/30-agent-lifecycle.md)
- [Feature deep dive](../features/agent-lifecycle-management/technical-deep-dive.md)

## Lifecycle States

The implemented state machine uses:

- `pending_approval`,
- `provisioned`,
- `active`,
- `suspended`,
- `rotating_credentials`,
- `decommissioning`,
- `decommissioned`,
- `orphaned`.

The manager rejects invalid transitions. For example, a decommissioned agent is
terminal. An active agent can be suspended, decommissioned, marked orphaned, or
enter credential rotation. A suspended agent can resume or decommission.

## Lifecycle Policy

`LifecyclePolicy` controls:

- whether approval is required,
- whether an owner is required,
- heartbeat interval,
- orphan threshold,
- max inactive days,
- credential policy.

`CredentialPolicy` controls:

- max credential TTL,
- rotation overlap,
- whether auto-rotation is enabled,
- whether credentials are revoked on decommission.

The default policy requires an owner and human approval.

## Main Flow

```python
from agentmesh.lifecycle.manager import LifecycleManager

manager = LifecycleManager(storage_path=".agentmesh/lifecycle.json")

agent = manager.request_provisioning(
    name="research-assistant",
    owner="founders@ophanix.ai",
    purpose="Summarize customer discovery notes",
    agent_type="langchain",
    actor="igor",
)

manager.approve(agent.agent_id, actor="igor")
manager.activate(agent.agent_id)
manager.heartbeat(agent.agent_id)

print(manager.summary())
print(manager.get_audit_trail(agent.agent_id))
```

Activation issues a short-lived credential id and expiry timestamp. Heartbeats
update liveness. Every state change records a lifecycle event.

## Suspension And Decommissioning

Suspension is temporary:

```python
manager.suspend(agent.agent_id, reason="reviewing abnormal tool calls")
manager.resume(agent.agent_id)
```

Decommissioning is final:

```python
manager.decommission(agent.agent_id, reason="startup experiment retired")
```

If the credential policy says to revoke on decommission, the current credential
is removed before the agent reaches `decommissioned`.

## Orphaned Agents

An orphaned agent is one that appears to be running but no longer has a valid
owner or heartbeat relationship. The orphan detector helps find agents that:

- missed heartbeats,
- have no owner,
- have been inactive too long.

In Ophanix, orphan detection should connect directly to discovery:

- discovery finds unknown running agents,
- lifecycle checks whether they are registered,
- missing or stale lifecycle state becomes an incident or remediation task.

## Demos To Run

Read the lifecycle tutorial:

```bash
cd ophanix-platform
cat docs/tutorials/30-agent-lifecycle.md
```

Run the manager directly:

```bash
cd ophanix-platform
pip install -e packages/agent-mesh
python
```

Then paste the main-flow snippet above.

The governance dashboard also has a lifecycle-monitor page with simulated data:

```bash
cd ophanix-platform/demo/governance-dashboard
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`.

## What To Remember

Lifecycle is the difference between "we have code that can call tools" and "we
operate a fleet of accountable agents." For Ophanix, this is one of the core
startup features to make visible and understandable to customers.
