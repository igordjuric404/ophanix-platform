# Policy Engine

The policy engine is the first feature to understand because almost every other
capability feeds context into it or acts on its decision. It is the deterministic
layer that evaluates an action before the action runs. The important distinction
is that this is not "prompting the model to behave." It is normal software
control flow: construct a context dict, evaluate configured rules, return
allow, deny, audit, or block, then log the decision.

## Where It Lives

- [Policy schema](../packages/agent-os/src/agent_os/policies/schema.py)
- [Policy evaluator](../packages/agent-os/src/agent_os/policies/evaluator.py)
- [External policy backends](../packages/agent-os/src/agent_os/policies/backends.py)
- [Conflict resolution](../packages/agent-os/src/agent_os/policies/conflict_resolution.py)
- [Tutorial](../docs/tutorials/01-policy-engine.md)
- [Feature deep dive](../features/policy-engine/technical-deep-dive.md)

## How It Works

The native policy model is small on purpose:

- `PolicyDocument` holds metadata, defaults, and a list of rules.
- `PolicyRule` has a name, condition, action, priority, and message.
- `PolicyCondition` compares one runtime context field against a value.
- `PolicyEvaluator.evaluate(context)` sorts rules by descending priority and
  returns the first match.
- If no YAML or JSON rule matches, registered external backends are consulted.
- If evaluation throws, the evaluator denies access. This is a fail-closed
  safety behavior.

The runtime context is just a dictionary. For example, the MAF middleware builds
context fields such as `agent`, `message`, `timestamp`, `stream`, and
`message_count`. A tool-call adapter might use `agent_id`, `tool_name`,
`resource`, `token_count`, `trust_score`, or `tenant`.

## Rule Evaluation Flow

1. Load policies from Python objects or a policy directory.
2. Flatten all rules from all loaded documents.
3. Sort by `priority`, highest first.
4. For each rule, read `context[condition.field]`.
5. Apply the operator: `eq`, `ne`, `gt`, `lt`, `gte`, `lte`, `in`, `matches`,
   or `contains`.
6. Return a `PolicyDecision` with `allowed`, `matched_rule`, `action`,
   `reason`, and an `audit_entry`.
7. If nothing matches, apply the first policy document's default action.

That last point matters. The sample quickstart policies default to allow. For
production, default-deny is usually better unless you have complete coverage and
strong observability.

## External Policy Languages

The evaluator can attach OPA/Rego and Cedar backends:

- `OPABackend` can call a remote OPA server, call the local `opa eval` CLI, or
  fall back to simple built-in pattern handling when the CLI is not available.
- `CedarBackend` normalizes Cedar authorization decisions into the same
  `BackendDecision` shape.

Native YAML rules run first. External backends are used only if no native rule
matched.

## Conflict Handling

The standalone evaluator uses priority-first matching. The conflict resolver
module also defines strategies you can use in richer deployments:

- `DENY_OVERRIDES`: any deny wins.
- `ALLOW_OVERRIDES`: any allow wins.
- `PRIORITY_FIRST_MATCH`: highest-priority matching rule wins.
- `MOST_SPECIFIC_WINS`: agent-scoped rules override organization, tenant, and
  global rules.

For Ophanix, `DENY_OVERRIDES` is the safer enterprise default when merging
customer policies, Ophanix base policy, and temporary exceptions.

## Demos To Run

```bash
cd ophanix-platform
python3 -m pip install -e packages/agent-os
python3 examples/quickstart/govern_in_60_seconds.py
python3 examples/quickstart/retrofit_governed.py
```

For the live middleware path:

```bash
cd ophanix-platform
export OPENAI_API_KEY="..."
python demo/maf_governance_demo.py
```

The live demo loads [demo/policies/research_policy.yaml](../demo/policies/research_policy.yaml),
blocks messages containing `internal` or `secrets`, allows research-like
messages containing `search`, and audits every action.

## What To Remember

The policy engine is intentionally boring in the best way. It should be fast,
predictable, inspectable, and testable. The hard work is not the evaluator; it
is deciding what context you pass into it and making sure every real action path
goes through it.
