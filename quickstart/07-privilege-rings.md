# Privilege Rings

Privilege rings are the runtime's coarse-grained privilege model. They are
inspired by operating-system CPU rings: lower ring numbers are more privileged,
higher ring numbers are safer and more restricted. The point is to avoid a
binary "trusted or not trusted" model for agents.

## Where It Lives

- [Runtime models](../packages/agent-hypervisor/src/hypervisor/models.py)
- [Action classifier](../packages/agent-hypervisor/src/hypervisor/rings/classifier.py)
- [Ring enforcer](../packages/agent-hypervisor/src/hypervisor/rings/enforcer.py)
- [Ring elevation](../packages/agent-hypervisor/src/hypervisor/rings/elevation.py)
- [Breach detector](../packages/agent-hypervisor/src/hypervisor/rings/breach_detector.py)
- [Runtime package shim](../packages/agent-runtime/src/agent_runtime/__init__.py)
- [Feature deep dive](../features/privilege-rings/technical-deep-dive.md)

## The Ring Model

The current model is:

- Ring 0, root: runtime configuration and penalty operations. Public Preview
  denies these operations; they are reserved for kernel-level controls.
- Ring 1, privileged: non-reversible operations such as deploy, delete, or
  write operations with no undo path.
- Ring 2, standard: reversible operations and normal write paths.
- Ring 3, sandbox: read-only or research operations; default for unknown or
  low-trust agents.

The `ExecutionRing.from_eff_score()` helper assigns rings from effective trust:

- score above the Ring 1 threshold plus consensus -> Ring 1,
- score above the Ring 2 threshold -> Ring 2,
- otherwise -> Ring 3.

Ring 0 is not assigned by score.

## Action Classification

Actions are represented by `ActionDescriptor`. The required ring is derived from
action metadata:

- `is_admin` -> Ring 0,
- non-reversible and not read-only -> Ring 1,
- read-only -> Ring 3,
- otherwise -> Ring 2.

The classifier caches classification results and supports overrides. In a real
Ophanix deployment, your product layer would probably maintain these
classifications centrally so customers can review why a tool is Ring 1 instead
of Ring 2.

## Enforcement

`RingEnforcer.check()` compares the agent ring with the action's required ring.
Because lower ring numbers are more privileged, an agent is allowed only if its
ring value is less than or equal to the required ring value.

Examples:

- Ring 2 agent can perform Ring 3 read-only action.
- Ring 2 agent cannot perform Ring 1 deployment action.
- Ring 0 action is always denied in Public Preview.

## Elevation And Breach Detection

The runtime includes concepts for time-limited ring elevation and breach
detection. The feature docs describe a fuller production model; the current
public-preview implementation keeps some dynamic elevation surfaces restricted.
That is still useful as product direction: Ophanix can treat "temporary higher
privilege" as an approval workflow with a TTL, reason, and audit entry.

## Demos To Run

The runtime README has the clearest interactive code sample:

```bash
cd ophanix-platform
cat packages/agent-hypervisor/README.md
```

If installed locally, you can explore the classes in a Python shell:

```python
from hypervisor.models import ActionDescriptor, ExecutionRing, ReversibilityLevel
from hypervisor.rings.enforcer import RingEnforcer

action = ActionDescriptor(
    action_id="deploy",
    name="Deploy",
    execute_api="/deploy",
    reversibility=ReversibilityLevel.NONE,
)
enforcer = RingEnforcer()
agent_ring = ExecutionRing.from_eff_score(0.7)
print(enforcer.check(agent_ring, action, eff_score=0.7).allowed)
```

## What To Remember

Rings are not a replacement for policies or capabilities. They are a blast
radius control. A policy can say "billing agents may refund." A capability can
say "this agent can refund invoice 123." A ring can say "this action is too
risky for a sandboxed or merely standard agent."
