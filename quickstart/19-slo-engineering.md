# SLO Engineering

SLO engineering applies site-reliability ideas to AI agents. Instead of only
asking whether an agent is safe, it asks whether the agent is reliable enough:
does it succeed, stay within cost, avoid hallucination, recover from failures,
and keep its promises over time?

## Where It Lives

- [SLO objectives](../packages/agent-sre/src/agent_sre/slo/objectives.py)
- [SLO indicators](../packages/agent-sre/src/agent_sre/slo/indicators.py)
- [SLO dashboard API](../packages/agent-sre/src/agent_sre/slo/dashboard.py)
- [Agent SRE examples](../packages/agent-sre/examples/README.md)
- [SLO feature deep dive](../features/slo-engineering/technical-deep-dive.md)

## Core Concepts

An SLI is a service-level indicator. It measures something:

- task success rate,
- hallucination rate,
- latency,
- cost per task,
- tool error rate,
- escalation rate.

An SLO is the target for that measurement:

- success rate must be at least 95%,
- hallucination rate must be under 5%,
- p95 latency must be under 4 seconds,
- cost per task must stay under a budget.

An error budget is how much failure you can tolerate before changing behavior.
For a 95% success target, the allowed error budget is 5%.

## Current Implementation

The implemented SLO layer provides:

- `SLO`,
- `ErrorBudget`,
- `BurnRateAlert`,
- `SLOStatus`,
- alert hooks,
- event recording,
- budget remaining percentage,
- burn-rate calculation,
- exhaustion actions.

SLO statuses are:

- `healthy`,
- `warning`,
- `critical`,
- `exhausted`,
- `unknown`.

Exhaustion actions are:

- alert,
- freeze deployments,
- circuit break,
- throttle.

The SLO object can send alerts when status worsens or recovers if an
`AlertManager` is attached.

## Error Budget Intuition

Burn rate tells you how quickly the budget is being consumed. A burn rate of
1.0 means you are consuming budget at the expected pace. Above 1.0 means you
are burning faster than planned.

This matters because waiting for the budget to hit zero is too late. High burn
rate is an early warning signal.

## Demos To Run

Install Agent SRE:

```bash
cd ophanix-platform
pip install -e "packages/agent-sre[dev]"
```

Run the quickstart:

```bash
python packages/agent-sre/examples/quickstart.py
```

That script simulates 100 agent tasks with a success rate below target and a
hallucination rate above target, then prints SLO status, budget consumption,
cost tracking, and alerts.

Run burn-rate alerting:

```bash
python packages/agent-sre/examples/slo_alerting.py
```

Run the dashboard:

```bash
cd ophanix-platform/packages/agent-sre
pip install -r examples/dashboard/requirements.txt
streamlit run examples/dashboard/app.py
```

Open `http://localhost:8501`.

## Minimal API Shape

The exact SLI classes live in
[indicators.py](../packages/agent-sre/src/agent_sre/slo/indicators.py). The
common runtime shape is:

```python
slo.record_event(good=True)
slo.record_event(good=False)

status = slo.evaluate()
print(status.value)
print(slo.error_budget.remaining_percent)
print(slo.error_budget.burn_rate())
```

## Ophanix Product Framing

For an agent governance startup, SLOs are more than observability. They let you
turn reliability into policy:

- if budget is healthy, allow normal autonomy,
- if burn rate is high, require approval for risky tools,
- if budget is exhausted, freeze model rollout,
- if hallucination SLO is breached, route to human review,
- if cost SLO is breached, throttle expensive tools.

## What To Remember

Agents need operational contracts. SLOs make those contracts measurable. Error
budgets make them actionable.
