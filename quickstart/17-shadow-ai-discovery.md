# Shadow AI Discovery

Shadow AI discovery finds agents that exist outside your governance boundary.
These can be local processes, config files, GitHub repositories, MCP servers,
or framework-specific projects that were never registered with AgentMesh.

The blunt truth: you cannot govern agents you cannot see. Discovery is the
inventory layer that tells you what exists before policy enforcement starts.

## Where It Lives

- [Agent Discovery package](../packages/agent-discovery/README.md)
- [Discovery CLI](../packages/agent-discovery/src/agent_discovery/cli/main.py)
- [Discovery models](../packages/agent-discovery/src/agent_discovery/models.py)
- [Process scanner](../packages/agent-discovery/src/agent_discovery/scanners/process.py)
- [Config scanner](../packages/agent-discovery/src/agent_discovery/scanners/config.py)
- [GitHub scanner](../packages/agent-discovery/src/agent_discovery/scanners/github.py)
- [Inventory store](../packages/agent-discovery/src/agent_discovery/inventory.py)
- [Risk scorer](../packages/agent-discovery/src/agent_discovery/risk.py)
- [Feature deep dive](../features/shadow-ai-discovery/technical-deep-dive.md)

## What It Finds

The scanners look for evidence of agent frameworks and agent-serving patterns.
The process scanner recognizes signatures for:

- LangChain and LangGraph,
- CrewAI,
- AutoGen,
- OpenAI Agents SDK,
- Semantic Kernel,
- Agent Governance Toolkit components,
- MCP servers,
- LlamaIndex,
- Haystack,
- PydanticAI,
- Google ADK.

The config scanner walks directories looking for agent artifacts, such as:

- `agentmesh.yaml`,
- `crewai.yaml`,
- `mcp.json`,
- Docker or Compose references,
- known framework dependency files.

The GitHub scanner searches repositories for config files and dependency
signals. It requires the optional GitHub dependency set.

## Evidence-Based Discovery

Every finding is a `DiscoveredAgent`. It has:

- a stable fingerprint for deduplication,
- best-guess name,
- framework or agent type,
- optional DID or SPIFFE identity,
- optional owner,
- governance status,
- confidence score,
- evidence records,
- first-seen and last-seen timestamps.

Every evidence record includes:

- which scanner found it,
- how it was detected,
- source path, PID, URL, or similar,
- human-readable detail,
- raw redacted data,
- confidence.

This is important because discovery can produce noisy results. You want a
reviewable evidence chain, not a black-box list.

## Risk Scoring

`RiskScorer` scores discovered agents from 0 to 100. It adds risk for:

- no DID or SPIFFE identity,
- no owner,
- shadow or unregistered status,
- high-risk framework types,
- long time ungoverned,
- medium-risk MCP or Semantic Kernel style agents.

It subtracts some risk for very low-confidence detections because those may be
false positives.

Risk levels are:

- `critical`,
- `high`,
- `medium`,
- `low`,
- `info`.

## CLI Commands

Install:

```bash
cd ophanix-platform
pip install -e "packages/agent-discovery[all]"
```

Scan the current repo with process and config scanners:

```bash
agent-discovery scan
```

Scan specific paths:

```bash
agent-discovery scan -s config -p /path/to/projects -p /path/to/deployments
```

Scan a GitHub organization:

```bash
agent-discovery scan -s github --github-org my-org
```

Export JSON for CI or ingestion:

```bash
agent-discovery scan -o json
```

View inventory:

```bash
agent-discovery inventory
agent-discovery inventory -o summary
agent-discovery inventory -o json
```

Reconcile against a registry:

```bash
agent-discovery reconcile --registry-file registered-agents.json
```

The inventory defaults to:

```text
~/.agent-discovery/inventory.json
```

## What Reconciliation Means

Discovery only says "this looks like an agent." Reconciliation compares that
agent against your approved registry. Anything found in discovery but missing
from the registry becomes a shadow-agent candidate.

The remediation flow for Ophanix should usually be:

1. confirm the evidence is real,
2. identify the owner,
3. register the agent or decommission it,
4. assign capabilities and policy,
5. begin lifecycle heartbeats,
6. monitor with Agent SRE.

## Demos To Run

The package itself is the demo. From this repo:

```bash
cd ophanix-platform
pip install -e "packages/agent-discovery[all]"
agent-discovery scan -s config -p . -o table
agent-discovery inventory -o summary
```

For JSON:

```bash
agent-discovery scan -s config -p . -o json
```

## What To Remember

Discovery should be read-only and evidence-driven. It should not try to fix
everything automatically. Its job is to surface unknown agents with enough
context that a human or workflow can bring them under governance.
