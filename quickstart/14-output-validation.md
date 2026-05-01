# Output Validation

Output validation checks whether an agent's answer is good enough, safe enough,
and structured enough to leave the system. Policy enforcement asks "is the
action allowed?" Output validation asks "is the produced content acceptable?"

This matters because an agent can follow policy and still return a bad result:
an incomplete answer, stale information, malformed JSON, hallucinated facts, or
content that fails a business quality gate.

## Where It Lives

- [Content governance](../packages/agent-os/src/agent_os/content_governance.py)
- [Feature deep dive](../features/output-validation/technical-deep-dive.md)
- [PromptDefense evaluator](../packages/agent-compliance/src/agent_compliance/prompt_defense.py)
- [Agent SRE indicators](../packages/agent-sre/src/agent_sre/slo/indicators.py)

## Current Implementation

The implemented core is `ContentQualityEvaluator`. It evaluates precomputed
quality scores against configured rules.

The quality dimensions are:

- `accuracy`,
- `completeness`,
- `freshness`,
- `structure`,
- `relevance`,
- `consistency`.

Each rule has:

- a name,
- a dimension,
- a threshold from 0.0 to 1.0,
- a gate: `pass`, `warn`, or `fail`,
- an optional description.

The evaluator returns a `ContentQualityReport` with:

- all individual evaluations,
- `passed`,
- `overall_score`,
- `warnings`,
- `failures`.

## Important Boundary

The current evaluator does not calculate truthfulness or factuality by itself.
It expects you to provide scores. In practice, those scores can come from:

- deterministic validators,
- schema checks,
- citation coverage checks,
- retrieval freshness checks,
- LLM-as-judge evaluators,
- human review,
- test-set evaluation,
- business-specific scoring functions.

Ophanix should make this explicit in product design. The governance layer is the
decision gate. The scoring source is pluggable.

## Example

```python
from agent_os.content_governance import (
    ContentDimension,
    ContentQualityEvaluator,
    ContentQualityRule,
    QualityGate,
)

evaluator = ContentQualityEvaluator()
evaluator.add_rule(ContentQualityRule(
    name="answer-must-be-complete",
    dimension=ContentDimension.COMPLETENESS,
    threshold=0.85,
    gate=QualityGate.FAIL,
))
evaluator.add_rule(ContentQualityRule(
    name="freshness-warning",
    dimension=ContentDimension.FRESHNESS,
    threshold=0.75,
    gate=QualityGate.WARN,
))

report = evaluator.evaluate(
    agent_id="agent:researcher",
    content_id="response:123",
    scores={
        ContentDimension.COMPLETENESS: 0.70,
        ContentDimension.FRESHNESS: 0.80,
    },
)

print(report.passed)
print(report.overall_score)
print([failure.rule_name for failure in report.failures])
```

In that example, the content fails because completeness is under a fail gate.
Freshness passes.

## Where It Fits In The Request Path

A common governance flow looks like this:

1. User request enters the agent.
2. Prompt injection detector checks the input.
3. Policy engine approves the planned tool calls.
4. Tool calls run through capability and runtime controls.
5. Agent produces an answer.
6. Output validators score the answer.
7. Content governance either releases it, warns, escalates, or blocks.
8. Audit log records the result.

For regulated workflows, output validation often becomes the final release
gate. For example:

- medical assistant answers require citations and confidence,
- loan processing must include required adverse-action fields,
- code agents must pass tests before suggesting a patch,
- customer support agents must not promise refunds outside policy,
- finance agents must include time-sensitive disclaimers.

## Demos To Run

There is no dedicated output-validation script. Run the API directly:

```bash
cd ophanix-platform
pip install -e packages/agent-os
python
```

Then paste the example above.

For adjacent demos, Agent SRE has examples that simulate quality and reliability
metrics:

```bash
cd ophanix-platform
pip install -e "packages/agent-sre[dev]"
python packages/agent-sre/examples/quickstart.py
python packages/agent-sre/examples/slo_alerting.py
```

Those examples are not output validators, but they show how quality signals can
be turned into SLOs, alerts, and budgets.

## What To Remember

Output validation should be policy-aware. A casual internal draft may only need
warnings. A production answer that changes user-visible state may need hard
fail gates, human review, and durable audit evidence.
