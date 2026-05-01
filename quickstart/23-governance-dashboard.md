# Governance Dashboard

The governance dashboard is the visual layer for understanding an agent fleet.
It is not the policy engine itself. It is the operator view: what is running,
which agents are risky, what policies are firing, where lifecycle state is
stale, and how trust is changing.

## Where It Lives

- [Fleet governance dashboard](../demo/governance-dashboard/README.md)
- [Fleet dashboard app](../demo/governance-dashboard/app.py)
- [Fleet demo data](../demo/governance-dashboard/demo_data.py)
- [Agent SRE dashboard](../packages/agent-sre/examples/dashboard/README.md)
- [Agent SRE dashboard app](../packages/agent-sre/examples/dashboard/app.py)
- [Trust score dashboard](../packages/agent-mesh/examples/06-trust-score-dashboard/README.md)
- [Trust dashboard example](../packages/agent-mesh/examples/trust-dashboard/README.md)

## There Are Multiple Dashboards

This repo has several dashboard paths:

| Dashboard | Location | Data source | Best for |
|---|---|---|---|
| Fleet Governance | `demo/governance-dashboard/` | Simulated | Stakeholder demo and platform tour |
| Agent SRE | `packages/agent-sre/examples/dashboard/` | Simulated, with SDK types if installed | Reliability, cost, incidents, chaos |
| Trust Score | `packages/agent-mesh/examples/06-trust-score-dashboard/` | Simulated, pluggable to live | Trust scoring and identity monitoring |
| Trust Dashboard | `packages/agent-mesh/examples/trust-dashboard/` | Example trust data | Trust exploration |

Start with the Fleet Governance dashboard. It gives the broadest view of the
platform concepts.

## Fleet Governance Pages

The demo governance dashboard includes:

- Fleet Overview,
- Shadow Agents,
- Lifecycle Monitor,
- Policy Feed,
- Trust Heatmap.

It uses simulated data out of the box. That is intentional: you can demo the
product without deploying the whole control plane.

## Run The Fleet Dashboard

```bash
cd ophanix-platform/demo/governance-dashboard
pip install -r requirements.txt
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

Docker option:

```bash
cd ophanix-platform/demo/governance-dashboard
docker compose up --build
```

## Run The Agent SRE Dashboard

```bash
cd ophanix-platform/packages/agent-sre
pip install -r examples/dashboard/requirements.txt
streamlit run examples/dashboard/app.py
```

This dashboard has tabs for:

- SLO Health,
- Cost Management,
- Chaos Engineering,
- Incidents,
- Progressive Delivery.

It works standalone with simulated data. If `agent-sre` is installed, it uses
the real SDK types for richer display.

## Run The Trust Score Dashboard

```bash
cd ophanix-platform/packages/agent-mesh/examples/06-trust-score-dashboard
pip install -r requirements.txt
streamlit run trust_dashboard.py
```

This is useful when you want to focus on identity, credentials, trust tier, and
agent-to-agent relationships.

## How To Think About Dashboards In Ophanix

A good governance dashboard should not only show charts. It should answer
operator questions:

- What agents are active right now?
- Which agents are unowned, orphaned, or unregistered?
- Which policies are blocking the most actions?
- Which tools are responsible for denials?
- Which agents have declining trust?
- Which SLOs are close to budget exhaustion?
- Which incidents need human action?
- What changed since the last deployment?

The current dashboards are reference demos. For your startup, the likely next
step is to keep the information architecture but replace simulated data with:

- discovery inventory,
- lifecycle state,
- policy evaluation events,
- audit log events,
- trust-score updates,
- SLO and incident telemetry.

## What To Remember

The dashboard is where governance becomes legible. It should make an executive
feel safe, an operator feel oriented, and an engineer feel able to debug the
next failure.
