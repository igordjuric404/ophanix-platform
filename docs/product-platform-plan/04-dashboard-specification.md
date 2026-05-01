# Dashboard Specification

## Product Navigation

Top-level navigation:

1. Overview
2. Agents
3. Policies
4. Trust
5. MCP Security
6. Mesh
7. Runtime
8. Discovery
9. Marketplace
10. Compliance
11. Observability
12. Integrations
13. Workflows
14. Demo Lab
15. Settings

Global UI requirements:

- Environment selector in the header.
- Time-range selector in the header.
- Search across agents, policies, tools, plugins, audit events, and reports.
- Live event indicator.
- Notification center for approvals, findings, incidents, and expiring credentials.
- Every decision detail drawer should include raw event JSON, matched policy, actor, agent, timestamp, correlation id, and audit hash status.

## 1. Overview

Purpose: give a buyer an immediate understanding of the governed estate.

### Widgets

- Fleet health cards:
  - Total agents.
  - Active agents.
  - Shadow agents.
  - Suspended agents.
  - Orphaned agents.
- Governance cards:
  - Policy evaluations.
  - Denied actions.
  - Escalations pending.
  - MCP blocked calls.
  - Credential rotations due.
- Trust cards:
  - Average trust score.
  - Agents below threshold.
  - Trust score changes in last 24h.
- Compliance cards:
  - Controls passing.
  - Controls with stale evidence.
  - Open violations.
- Operations cards:
  - SLO health.
  - Incidents.
  - Cost budget used.

### Tables And Charts

- Governance activity timeline.
- Policy decision trend by allow/deny/escalate.
- Trust distribution histogram.
- Top risky agents table.
- Recent high-severity audit events.

### Actions

- Run demo scenario.
- Register agent.
- Create policy.
- Scan MCP server.
- Run discovery scan.
- Generate compliance report.

## 2. Agents

Menus:

- Inventory
- Register Agent
- Lifecycle
- Credentials
- Trust Cards
- Ownership
- Capability Requests

### Inventory Page

Table columns:

- Name.
- DID.
- Status.
- Trust score.
- Trust tier.
- Owner.
- Sponsor.
- Framework.
- Runtime.
- Protocols.
- Capabilities.
- Active policies.
- Credential expiry.
- Last heartbeat.
- Risk.

Filters:

- Status.
- Trust tier.
- Owner.
- Sponsor.
- Framework.
- Protocol.
- Capability.
- Policy binding.
- Environment.

Row actions:

- Open detail.
- Suspend.
- Rotate credential.
- Change owner.
- Decommission.
- Run health check.

### Register Agent Page

Wizard steps:

1. Agent details:
   - Name.
   - Description.
   - Business purpose.
   - Environment.
   - Owner.
   - Sponsor.
2. Runtime and framework:
   - Framework: OpenAI Agents, LangChain, CrewAI, smolagents, LlamaIndex, custom.
   - Runtime: local, container, Kubernetes, serverless, external.
   - Endpoint or callback URL.
3. Identity:
   - Generate DID.
   - Upload existing identity.
   - Map to workload identity.
   - Signing key mode.
4. Capabilities:
   - Tools.
   - MCP servers.
   - Data scopes.
   - Runtime actions.
5. Policies:
   - Select policy pack.
   - Bind environment policies.
   - Simulate first action.
6. Bootstrap:
   - Show SDK snippet.
   - Show environment variables.
   - Show generated config.
   - Test heartbeat.

### Agent Detail Page

Tabs:

- Overview:
  - Status, trust, owner, sponsor, last heartbeat, active credential, policy coverage.
- Identity:
  - DID, public keys, trust card, signature verification, identity events.
- Policies:
  - Bound policies, recent decisions, exceptions.
- Credentials:
  - Active credentials, scopes, expiry, rotations, revocations.
- Trust:
  - Score trend, dimensions, recent deltas, handshake history.
- Audit:
  - Agent-specific audit events.
- Runtime:
  - Sessions, ring decisions, sandbox decisions, kill-switch events.
- Integrations:
  - Framework adapter, model provider, webhooks, SDK version.

## 3. Policies

Menus:

- Library
- Editor
- Bindings
- Simulator
- Evaluation Feed
- Exceptions
- Approvals
- Policy Packs

### Library Page

Table columns:

- Policy name.
- Version.
- Status.
- Scope.
- Backend.
- Owner.
- Active bindings.
- Last modified.
- Lint status.
- Deny rate.
- Escalation rate.

Actions:

- Create policy.
- Import YAML.
- Clone.
- Archive.
- Promote.
- Roll back.

### Editor Page

Layout:

- Left: policy metadata and version list.
- Center: YAML/JSON/Rego/Cedar editor.
- Right: lint results, affected agents, recent decisions, simulator preview.

Forms:

- Name.
- Description.
- Scope.
- Priority.
- Backend.
- Owner.
- Tags.
- Effective date.
- Expiration date.

### Bindings Page

Matrix columns:

- Policy.
- Agent.
- MCP server.
- Tool.
- Runtime action.
- Environment.
- Status.
- Rollout percentage.
- Last evaluation.

Actions:

- Bind policy.
- Unbind.
- Dry run.
- Promote from shadow to enforce.
- Create exception.

### Simulator Page

Inputs:

- Agent.
- Action.
- Resource.
- Tool.
- Context JSON.
- Policy version.
- Backend.

Outputs:

- Decision.
- Matched rule.
- Reason.
- Evaluation latency.
- Audit event preview.
- Trust impact preview.

## 4. Trust

Menus:

- Leaderboard
- Heatmap
- Score Events
- Trust Cards
- Handshakes
- Thresholds
- Explainability

### Leaderboard

Table columns:

- Agent.
- Score.
- Tier.
- 24h delta.
- Security.
- Compliance.
- Quality.
- Efficiency.
- Collaboration.
- Last trust event.

Charts:

- Trust score trend.
- Distribution by tier.
- Top positive/negative deltas.

### Heatmap

Features:

- Agent-to-agent trust matrix.
- Cell hover shows score, last handshake, allowed protocols.
- Cell click opens handshake history and policy requirements.

### Thresholds

Forms:

- Minimum trust for handoff.
- Minimum trust for MCP tool use.
- Minimum trust for privileged runtime action.
- Minimum trust for marketplace plugin install.
- Trust decay settings.
- Dimension weights.

## 5. MCP Security

Menus:

- Servers
- Tools
- Security Scans
- Proxy Traffic
- Approvals
- Tool Policies
- Response Scanner
- Rate Limits

### Servers Page

Table columns:

- Name.
- Endpoint.
- Owner.
- Auth type.
- Status.
- Tools.
- Last scan.
- Critical findings.
- Traffic.
- Policy pack.

Actions:

- Register server.
- Run scan.
- Disable server.
- Rotate server credential.

### Tools Page

Table columns:

- Tool name.
- Server.
- Schema hash.
- Risk.
- Allowed agents.
- Approval required.
- Last call.
- Deny rate.
- Sanitizer status.

### Security Scans

Scan detail sections:

- Prompt injection findings.
- Hidden Unicode.
- Encoded payload.
- Schema abuse.
- Rug pull or changed definition.
- Cross-server exfiltration risk.
- Typosquatting.
- Recommended policy.

### Proxy Traffic

Table columns:

- Timestamp.
- Source agent.
- Server.
- Tool.
- Decision.
- Matched policy.
- Approval status.
- Sanitizer action.
- Latency.
- Correlation id.

## 6. Mesh

Menus:

- Topology
- Messages
- Handshakes
- Handoffs
- Protocol Bridges
- Mesh Policies

### Topology

Graph:

- Nodes are agents.
- Edges are protocol connections.
- Node color is trust tier.
- Edge thickness is traffic.
- Edge color is allow/deny ratio.

Filters:

- Protocol.
- Environment.
- Framework.
- Trust tier.
- Time range.

### Messages

Table columns:

- Timestamp.
- Source.
- Target.
- Protocol.
- Action.
- Decision.
- Trust threshold.
- Latency.
- Correlation id.

## 7. Runtime

Menus:

- Sessions
- Rings
- Sandbox
- Sagas
- Kill Switch
- Liability
- Runtime Policies

### Sessions

Table columns:

- Session id.
- Agent.
- State.
- Ring.
- Started.
- Last action.
- Sponsor.
- Policy status.
- Cost.
- Trust delta.

### Rings

Charts and tables:

- Actions by required ring.
- Denials by ring.
- Agents by current ring.
- Ring threshold configuration.

### Sandbox

Forms:

- Sandbox profile name.
- Provider: subprocess, Docker, Kubernetes, external.
- Allowed imports.
- Blocked imports.
- Allowed paths.
- Network access.
- Resource limits.

### Sagas

Saga builder:

- Add step.
- Set required capability.
- Set timeout.
- Set retry policy.
- Set compensation step.
- Bind policy.

Execution monitor:

- Step status timeline.
- Failure reason.
- Compensation status.
- Audit links.

### Kill Switch

Controls:

- Target type: agent, session, tool, plugin, MCP server.
- Scope: current session, environment, organization.
- Reason.
- Sponsor approval.
- Typed confirmation.

## 8. Discovery

Menus:

- Scan Runs
- Findings
- Risk Triage
- Reconciliation
- Scanner Settings
- Suppressions

### Scan Runs

Table columns:

- Scanner.
- Target.
- Status.
- Started.
- Duration.
- Findings.
- High risk.
- Errors.

### Findings

Table columns:

- Detected name.
- Type.
- Source.
- Owner.
- Identity status.
- Registry match.
- Risk score.
- Evidence count.
- First seen.
- Last seen.
- Status.

Actions:

- Assign owner.
- Register as agent.
- Suppress.
- Create policy.
- Mark decommissioned.

## 9. Marketplace

Menus:

- Catalog
- Installed
- Plugin Detail
- Publish
- Review Queue
- Signing Keys
- Policies
- Usage Trust

### Catalog

Table columns:

- Name.
- Version.
- Type.
- Publisher.
- Signature.
- Trust tier.
- Quality score.
- Installs.
- Required capabilities.
- Policy status.

### Install Flow

Steps:

1. Select plugin version.
2. Select environment and target agents.
3. Review manifest.
4. Review required capabilities.
5. Run policy compatibility check.
6. Approve and install.
7. Show audit event and trust impact.

## 10. Compliance

Menus:

- Control Map
- Audit Explorer
- Evidence Library
- Reports
- Attestations
- Violations
- Exports

### Audit Explorer

Table columns:

- Timestamp.
- Event type.
- Actor.
- Agent.
- Resource.
- Decision.
- Severity.
- Policy.
- Trust delta.
- Correlation id.
- Hash status.

### Control Map

Framework tabs:

- SOC 2.
- GDPR.
- EU AI Act.
- HIPAA.
- Internal policy.

Control row fields:

- Control id.
- Description.
- Status.
- Evidence count.
- Freshness.
- Owner.
- Open violations.

### Report Builder

Inputs:

- Framework.
- Date range.
- Environment.
- Agents.
- Include raw evidence.
- Export format.

Outputs:

- Report preview.
- Evidence appendix.
- Exceptions.
- Signature/attestation.

## 11. Observability

Menus:

- Overview
- SLOs
- Incidents
- Costs
- Chaos
- Rollouts
- Metrics
- Logs
- Traces
- Alerts

### SLOs

Table columns:

- Name.
- SLI.
- Target.
- Current.
- Window.
- Error budget remaining.
- Burn rate.
- Status.

Create form:

- Name.
- Agent or fleet.
- SLI.
- Target.
- Window.
- Alert threshold.
- Enforcement action.

### Incidents

Table columns:

- Incident id.
- Severity.
- Status.
- Affected agents.
- Trigger.
- Related policy.
- Related MCP tool.
- Started.
- Owner.

### Costs

Charts:

- Cost by model provider.
- Cost by agent.
- Cost by workflow.
- Cost by tool.
- Budget burn-down.

## 12. Integrations

Menus:

- Frameworks
- Model Providers
- Identity Providers
- Observability Providers
- Secret Stores
- Webhooks
- API Keys

### Frameworks

Table columns:

- Framework.
- Status.
- Version.
- Connected agents.
- Last event.
- Policy coverage.
- Trust coverage.
- Telemetry status.

Setup wizard:

1. Select framework.
2. Add provider credentials.
3. Choose sample agent or existing agent.
4. Bind policies.
5. Run health check.
6. Show bootstrap command.

## 13. Workflows

Menus:

- Catalog
- Runs
- Schedules
- Artifacts
- Attestations
- CLI Export

### Catalog

Rows:

- Policy lint.
- Governance verify.
- Integrity check.
- Security scan.
- SBOM generation.
- Dependency confusion check.
- Marketplace plugin evaluate.
- Discovery scan.

Run detail:

- Inputs.
- Logs.
- Exit status.
- Duration.
- Artifacts.
- Linked evidence.

## 14. Demo Lab

Menus:

- Scenario Catalog
- Scenario Runner
- Prerequisites
- Live Evidence
- Reset Environment
- Export Script

### Scenario Catalog

Table columns:

- Scenario.
- Value proof.
- Required services.
- Duration.
- Last run.
- Status.
- Proof checklist.

### Scenario Runner

Layout:

- Left: steps, expected result, current status.
- Center: live timeline.
- Right: proof checklist and links to relevant dashboard pages.

Controls:

- Start.
- Pause.
- Continue.
- Reset.
- Export report.

### Prerequisites

Checks:

- PostgreSQL connected.
- Redis connected.
- Model provider configured.
- Sample MCP server running.
- Demo agents registered.
- Policies active.
- OPA optional.
- GitHub token optional.

## 15. Settings

Menus:

- Users
- Roles
- Organizations
- Environments
- Retention
- Audit Integrity
- Feature Flags
- System Health

Required settings:

- RBAC roles:
  - Viewer.
  - Operator.
  - Policy Admin.
  - Security Admin.
  - Compliance Admin.
  - Platform Admin.
- Retention:
  - Audit retention.
  - Metrics retention.
  - Report retention.
  - Discovery finding retention.
- Audit:
  - Hash verification status.
  - Export destinations.
  - Legal hold.
