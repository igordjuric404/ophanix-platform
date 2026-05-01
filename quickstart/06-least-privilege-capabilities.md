# Least-Privilege Capabilities

Least-privilege capabilities answer a more precise question than "is this agent
trusted?" They ask: "Does this exact agent have this exact capability for this
resource right now?" Trust score controls broad confidence. Capabilities control
scope.

## Where It Lives

- [Capability grants](../packages/agent-mesh/src/agentmesh/trust/capability.py)
- [Constraint graph](../packages/agent-os/src/agent_os/constraint_graph.py)
- [MAF capability guard](../packages/agent-os/src/agent_os/integrations/maf_adapter.py)
- [RBAC manager](../packages/agent-os/src/agent_os/integrations/rbac.py)
- [Delegation chains](../packages/agent-mesh/src/agentmesh/identity/delegation.py)
- [Feature deep dive](../features/least-privilege-capabilities/technical-deep-dive.md)

## Capability Strings

Capabilities are simple strings with a rough shape:

```text
action:resource[:qualifier]
```

Examples:

```text
read:data
write:reports
execute:tools:calculator
admin:*
```

`CapabilityGrant` records who granted the capability, who received it, optional
resource ids, optional expiry, and whether the grant is active. A
`CapabilityScope` collects grants for one agent and checks deny-list entries
before allow grants. `CapabilityRegistry` manages scopes across the mesh.

## Capability Resolution

A capability check usually proceeds like this:

1. Identify the caller agent DID.
2. Identify the requested capability or tool.
3. Check whether the agent has an active matching grant.
4. Apply resource id constraints if present.
5. Deny if the capability is explicitly denied, expired, revoked, or absent.

Wildcard support exists, but be careful. Wildcards are convenient in demos and
dangerous in production. Delegation code also blocks wildcard propagation in
some paths to avoid broad downstream authority.

## Constraint Graph

The constraint graph is an additional resource-access model in Agent OS. It
registers resource nodes and constraint edges:

- resources are `TOOL`, `API`, or `DATA`,
- edges match agent patterns and resource patterns,
- permissions are `ALLOW` or `DENY`,
- conditions can require context values,
- higher-priority edges are evaluated first,
- no match means deny by default.

This gives Ophanix a good internal representation for customer policy like:
"support agents may search tickets, but only billing agents may refund, and
refund over $500 requires approval."

## Framework Guards

In MAF, `CapabilityGuardMiddleware` checks each function invocation against
`allowed_tools` and `denied_tools`. The denied list wins. If a tool is blocked,
the middleware sets an error result, writes an audit entry if configured, and
raises `MiddlewareTermination`.

That is the simplest pattern for any framework: get the tool name, check the
capability model, stop the call before the tool executes.

## Demos To Run

```bash
cd ophanix-platform
python demo/maf_governance_demo.py
```

The demo includes a capability-sandboxing scenario where a tool is allowed and
another is denied. For a smaller read, inspect the `CapabilityGuardMiddleware`
class directly in [maf_adapter.py](../packages/agent-os/src/agent_os/integrations/maf_adapter.py).

## What To Remember

Trust is about confidence. Capabilities are about boundaries. A high-trust agent
still should not have every capability. Ophanix should model capabilities as
explicit, reviewable, revocable grants rather than hidden framework settings.
