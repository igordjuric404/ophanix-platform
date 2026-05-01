# Unified CLI And Compliance Verification

The CLI and compliance package are the fastest way to turn the toolkit from
libraries into repeatable checks. This is where you get policy linting,
governance attestation, integrity manifests, MCP scanning, Agent OS project
setup, discovery commands, and SRE status commands.

## Where It Lives

- [Unified AGT CLI](../packages/agent-compliance/src/agent_compliance/cli/agt.py)
- [Compliance CLI](../packages/agent-compliance/src/agent_compliance/cli/main.py)
- [Governance verifier](../packages/agent-compliance/src/agent_compliance/verify.py)
- [Integrity verifier](../packages/agent-compliance/src/agent_compliance/integrity.py)
- [Policy linter](../packages/agent-compliance/src/agent_compliance/lint_policy.py)
- [Agent OS CLI](../packages/agent-os/src/agent_os/cli/__init__.py)
- [MCP scan CLI](../packages/agent-os/src/agent_os/cli/mcp_scan.py)
- [Agent Discovery CLI](../packages/agent-discovery/src/agent_discovery/cli/main.py)
- [Agent SRE CLI](../packages/agent-sre/src/agent_sre/cli/main.py)
- [Compliance tutorial](../docs/tutorials/18-compliance-verification.md)

## Console Scripts

The packages define these entry points:

| Command | Package | Purpose |
|---|---|---|
| `agt` | `agent-compliance` | Unified governance CLI |
| `agent-compliance` | `agent-compliance` | Compliance CLI |
| `agent-governance` | `agent-compliance` | Alias for compliance CLI |
| `agent-governance-toolkit` | `agent-compliance` | Alias for compliance CLI |
| `agent-os` | `agent-os` | Agent OS project and policy commands |
| `agentmesh` | `agent-mesh` | AgentMesh commands |
| `hypervisor` | `agent-hypervisor` | Hypervisor session commands |
| `agent-sre` | `agent-sre` | SRE status/info commands |
| `agent-discovery` | `agent-discovery` | Shadow agent discovery |

## Install Locally

```bash
cd ophanix-platform
pip install -e packages/agent-os
pip install -e packages/agent-mesh
pip install -e packages/agent-hypervisor
pip install -e packages/agent-sre
pip install -e packages/agent-compliance
pip install -e packages/agent-discovery
```

## Unified `agt` CLI

`agt` is meant to be the primary CLI face:

```bash
agt --help
agt doctor
agt verify
agt verify --badge
agt --json verify
agt integrity
agt integrity --generate integrity.json
agt integrity --manifest integrity.json
agt lint-policy examples/policies
agt lint-policy examples/policies --strict
```

`agt doctor` checks installed AGT packages, Python version, plugin discovery,
and common config files.

`agt verify` runs OWASP Agentic Security Initiative control checks and produces
a governance attestation.

`agt integrity` generates or verifies a manifest of file and function hashes.

`agt lint-policy` checks YAML policy files for common mistakes.

## Compliance CLI Aliases

The older compliance CLI exposes the same core ideas:

```bash
agent-compliance verify
agent-compliance verify --json
agent-compliance verify --badge
agent-compliance integrity --generate integrity.json
agent-compliance integrity --manifest integrity.json
agent-compliance lint-policy examples/policies --strict
```

The aliases `agent-governance` and `agent-governance-toolkit` point to the same
entry point.

## What Governance Verification Checks

The verifier checks whether expected governance components are importable for
OWASP ASI-style controls. Examples include:

- prompt injection,
- insecure tool use,
- excessive agency,
- unauthorized escalation,
- trust boundary violation,
- logging,
- identity,
- policy bypass,
- supply-chain integrity,
- behavioral anomaly.

It returns:

- pass/fail,
- controls passed and total,
- coverage percentage,
- compliance grade,
- toolkit version,
- Python and platform info,
- attestation hash.

This is presence verification, not a full live red-team assessment. It proves
the components are available and attestable; you still need runtime telemetry
and tests for production assurance.

## Agent OS CLI

`agent-os` handles local project governance setup and policy checking:

```bash
agent-os --help
agent-os init
agent-os secure
agent-os status
agent-os audit
agent-os check path/to/file.py
agent-os validate examples/policies
agent-os install-hooks
agent-os metrics
agent-os health
```

It also has an MCP scanner implementation in source with commands:

```bash
python -m agent_os.cli.mcp_scan scan path/to/mcp-config.json
python -m agent_os.cli.mcp_scan fingerprint path/to/mcp-config.json
python -m agent_os.cli.mcp_scan report path/to/mcp-config.json --format markdown
```

Depending on packaging, there may not be a separate `mcp-scan` console script
in this checkout, so `python -m agent_os.cli.mcp_scan ...` is the reliable
local form.

## Discovery And SRE CLIs

Discovery:

```bash
agent-discovery scan
agent-discovery inventory -o summary
agent-discovery reconcile --registry-file registered-agents.json
```

SRE:

```bash
agent-sre version
agent-sre info
agent-sre slo status
agent-sre cost summary
```

The SRE CLI is intentionally light right now. Most Agent SRE behavior is in the
Python APIs and examples.

## Demos To Run

Start with:

```bash
cd ophanix-platform
pip install -e packages/agent-compliance
agt doctor
agt verify
agt verify --badge
```

Then:

```bash
pip install -e packages/agent-os
agent-os status
agent-os validate examples/policies
```

And:

```bash
pip install -e "packages/agent-discovery[all]"
agent-discovery scan -s config -p . -o table
```

## What To Remember

The CLI is how governance becomes repeatable in CI, local development, and
customer environments. For Ophanix, the strongest path is to make the CLI emit
clear evidence artifacts: attestations, integrity reports, policy lint results,
MCP scan reports, discovery inventory, and SLO status.
