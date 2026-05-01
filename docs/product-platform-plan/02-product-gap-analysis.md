# Product Gap Analysis

## Gap Summary

The missing layer is not the governance logic. The missing layer is productization: a persistent control plane, a single dashboard, real event ingestion, workflow APIs, seeded but live demo infrastructure, and clear buyer-facing proof flows.

The following sections use the same structure for each feature:

- What exists in the repo
- What is mocked, simulated, hardcoded, or demo-only
- What is missing for product readiness
- What needs to be built
- How it should be visualized in the dashboard
- Demo, MVP, and enterprise scope

## 1. Policy Engine And Policy Configuration

For the policy engine feature, create a Policy Management dashboard that visualizes policy coverage, active bindings, evaluation volume, deny/escalate trends, and policy test results. It must include Policy Library, Policy Editor, Bindings, Simulation, Approval Queue, and Evaluation Feed menus to configure rules, scopes, conditions, priorities, backends, exceptions, and rollout state.

### What Exists

- YAML/JSON policy schema in `packages/agent-os/src/agent_os/policies/schema.py`.
- Policy evaluator in `packages/agent-os/src/agent_os/policies/evaluator.py`.
- OPA/Rego and Cedar backend support in `packages/agent-os/src/agent_os/policies/backends.py`.
- Shared cross-project policy schema in `packages/agent-os/src/agent_os/policies/shared.py`.
- Policy linter in `packages/agent-compliance/src/agent_compliance/cli/lint_policy.py`.
- Example policies under `packages/agent-os/examples/policies`, `packages/agent-mesh/examples/policies`, and framework examples.

### Mocked Or Demo-Only

- Policy files are manually edited in the repo.
- No central policy inventory or runtime binding state.
- Current API surfaces do not expose full policy CRUD, versioning, binding, approval, or rollback.
- OPA and Cedar support require external runtimes or CLIs for full fidelity.

### Missing

- Canonical policy database and version history.
- UI policy editor with YAML/JSON validation and lint feedback.
- Policy binding model for agents, tool groups, MCP servers, runtime rings, framework adapters, and environments.
- Policy simulation API that runs real evaluator logic against sample and live captured events.
- Approval and promotion workflow from draft to active.
- Rollback, diff, ownership, tags, and audit trail.
- Policy pack concept for demo, SOC 2, GDPR, EU AI Act, PCI, HIPAA, internal security.

### Build Required

- Backend:
  - `policies`, `policy_versions`, `policy_bindings`, `policy_tests`, `policy_rollouts`, `policy_exceptions`.
  - CRUD API for policy docs, versions, tags, owners, and active status.
  - Evaluation API that wraps the existing evaluator and records every decision.
  - Backend selector per policy: local evaluator, OPA, Cedar.
  - Policy import/export from existing YAML examples.
  - Policy linter service using existing compliance linter.
- UI:
  - Policy Library table.
  - Monaco-style YAML/JSON editor.
  - Binding wizard.
  - Simulation console.
  - Approval queue.
  - Evaluation feed.
- Jobs:
  - Scheduled policy lint.
  - Drift detection between DB policy and deployed file/agent config.
  - Rollout health monitor.
- Persistence:
  - PostgreSQL for policies and decisions.
  - Object storage or DB text column for rendered reports and exported bundles.

### Dashboard Visualization

- Policy Library table columns: name, version, status, scope, backend, owner, last changed, active bindings, deny rate, test status.
- Policy Editor:
  - Left tree: sections and rules.
  - Center editor: YAML/JSON/Rego/Cedar body.
  - Right panel: lint errors, referenced capabilities, affected agents, recent decisions.
- Bindings page:
  - Matrix of policy to agent/tool/MCP server/environment.
  - Filters: environment, owner, framework, risk tier, status.
  - Actions: bind, unbind, clone binding, dry run, promote.
- Simulation page:
  - Inputs: agent, action, resource, context JSON, policy version, backend.
  - Output: allow/deny/escalate/audit, matched rule, reasoning, latency, audit preview.
- Evaluation Feed:
  - Timeline of real policy decisions.
  - Facets: decision, action, agent, rule, policy version, MCP server, risk level.

### Scope

- Must have for demo:
  - Import example YAML policies into DB.
  - UI editor with lint and save.
  - Bind policy to demo agents and MCP tools.
  - Real simulation and live evaluation feed.
- Must have for sellable MVP:
  - Versioning, approval, rollback, exceptions, RBAC, API keys, policy packs.
  - OPA/Rego optional runtime and local evaluator fallback.
  - Audit every change.
- Later enterprise feature:
  - Multi-tenant policy promotion pipelines.
  - GitOps sync.
  - Cedar/OPA clusters.
  - Formal policy impact analysis.
  - Delegated policy ownership by business unit.

## 2. Agent Identity And Registration

For the agent identity feature, create an Agent Registry dashboard that visualizes registered agents, DIDs, sponsors, owners, capabilities, lifecycle state, trust tier, framework, runtime location, credential status, and last heartbeat. It must include Inventory, Register Agent, Identity Details, Capability Approval, Lifecycle, and Ownership menus to configure agent metadata, sponsors, capabilities, protocols, environments, and identity provider mappings.

### What Exists

- DID-style identity creation in `packages/agent-mesh/src/agentmesh/identity/agent_id.py`.
- Agent registry in `packages/agent-mesh/src/agentmesh/services/registry/agent_registry.py`.
- Lifecycle manager in `packages/agent-mesh/src/agentmesh/lifecycle/manager.py`.
- Orphan detector in `packages/agent-mesh/src/agentmesh/lifecycle/orphan_detector.py`.
- Trust card and handshake components under `packages/agent-mesh/src/agentmesh/trust`.
- Entra and managed identity related tests and identity components exist, but real cloud calls are not the default demo path.

### Mocked Or Demo-Only

- Default registry is in-memory.
- Lifecycle can use JSON file persistence but is not a product database.
- Registration examples are local scripts.
- Demo dashboards generate fake fleets.
- No single UI to approve, reject, suspend, decommission, or transfer ownership.

### Missing

- Persistent agent inventory.
- Agent onboarding wizard.
- Sponsor/owner approval workflow.
- Capability request and approval model.
- Agent heartbeat ingestion.
- Identity verification status.
- Framework/runtime metadata.
- Agent to policy, credential, trust, audit, and runtime joins.

### Build Required

- Backend:
  - `agents`, `agent_identities`, `agent_capabilities`, `agent_protocols`, `agent_owners`, `agent_heartbeats`, `agent_lifecycle_events`.
  - APIs for register, approve, activate, suspend, resume, decommission, change owner, update capability, heartbeat.
  - Adapter over existing `AgentIdentity`, `AgentRegistry`, `LifecycleManager`, and `OrphanDetector`.
  - Registration token flow for agents to self-register.
- UI:
  - Agent Inventory.
  - Register Agent wizard.
  - Agent detail page with tabs: Overview, Identity, Policies, Credentials, Trust, Audit, Runtime, Integrations.
  - Approval queue for pending registration and capability changes.
- Jobs:
  - Heartbeat monitor.
  - Orphan detection.
  - Capability drift detector.
- Persistence:
  - PostgreSQL for agent state.
  - Redis for recent heartbeat cache and online/offline presence.

### Dashboard Visualization

- Agent Inventory table columns: agent name, DID, status, trust score, trust tier, owner, sponsor, framework, protocols, capabilities, active policies, credential expiry, last heartbeat.
- Register Agent wizard:
  - Step 1: name, description, owner, sponsor.
  - Step 2: framework type and runtime environment.
  - Step 3: requested capabilities and tools.
  - Step 4: policy pack and environment bindings.
  - Step 5: generated bootstrap command or config.
- Agent Detail:
  - Header with trust score, status, owner, active credential, last action.
  - Identity tab with DID, public keys, certificate chain, trust card.
  - Lifecycle tab with state machine and event timeline.
  - Actions menu: suspend, rotate credential, change owner, decommission, open live session.

### Scope

- Must have for demo:
  - Register three sample agents from UI.
  - Generate DIDs and credentials using existing primitives.
  - Show heartbeat and owner metadata.
  - Lifecycle approve, activate, suspend, resume.
- Must have for sellable MVP:
  - Persistent registry.
  - API registration tokens.
  - Owner/sponsor approval.
  - Agent bootstrap SDK snippets.
  - Orphan detection and audit.
- Later enterprise feature:
  - SCIM ownership sync.
  - Entra/Okta workload identity mapping.
  - SPIFFE/SPIRE integration.
  - Hardware-backed keys and HSM/KMS.

## 3. Trust Scoring And Trust Cards

For the trust feature, create a Trust Center dashboard that visualizes agent trust scores, trust dimensions, trend lines, trust card signatures, peer handshakes, score deltas, and trust-based enforcement decisions. It must include Leaderboard, Heatmap, Trust Cards, Score Events, Rules, and Handshake Logs menus to configure thresholds, decay rules, trust dimensions, revocations, and peer eligibility.

### What Exists

- Trust cards in `packages/agent-mesh/src/agentmesh/trust/cards.py`.
- Trust handshake in `packages/agent-mesh/src/agentmesh/trust/handshake.py`.
- Reward scoring in `packages/agent-mesh/src/agentmesh/reward/scoring.py` and `engine.py`.
- Trust score dashboards and examples.
- Protocol bridge and trust bridge components.

### Mocked Or Demo-Only

- Streamlit trust dashboards use hardcoded/simulated agents, scores, credentials, traffic, and audit logs.
- Trust scores are not centrally persisted across product components.
- Some protocol bridge methods return placeholder success or discovered-agent values.
- Trust dimensions are not wired to all real policy/audit/runtime/MCP events by default.

### Missing

- Canonical trust score history.
- Trust signal ingestion from policy decisions, MCP calls, credential health, runtime incidents, SLOs, and discovery findings.
- Trust card issuance and revocation UI.
- Threshold management per action/tool/environment.
- Peer handshake visualization and failure reasons.
- Trust score explainability.

### Build Required

- Backend:
  - `trust_scores`, `trust_dimensions`, `trust_events`, `trust_cards`, `trust_card_revocations`, `trust_thresholds`, `handshake_events`.
  - Event consumer that turns audit/policy/runtime/discovery/SRE events into trust signals.
  - API over existing scoring engine and trust card registry.
  - Score recalculation job and explainability endpoint.
- UI:
  - Trust Leaderboard.
  - Trust Heatmap.
  - Trust Card detail.
  - Score timeline.
  - Trust rules and thresholds.
  - Handshake logs.
- Jobs:
  - Periodic trust recomputation.
  - Trust decay.
  - Revocation propagation.

### Dashboard Visualization

- Leaderboard table columns: agent, score, tier, 24h delta, compliance, security, quality, efficiency, collaboration, last event.
- Heatmap:
  - Agent-to-agent trust relationship matrix.
  - Click cell to open handshake history.
- Trust Card page:
  - Signed card metadata, issuer, subject DID, capabilities, score, valid from/to, signature verification, revocation status.
- Score Events:
  - Timeline with positive/negative deltas, source event, rule, affected dimension, before/after.
- Thresholds:
  - Form fields: minimum trust for handoff, MCP tool use, privileged runtime action, plugin install, credential renewal.

### Scope

- Must have for demo:
  - Persist trust score for demo agents.
  - Update trust on allowed/denied policy evaluations and MCP tool calls.
  - Show signed trust cards and score deltas.
- Must have for sellable MVP:
  - Explainable trust scoring with configurable weights.
  - Revocation list and handshake logs.
  - Integration with policy bindings and runtime controls.
- Later enterprise feature:
  - Federated trust exchange.
  - External trust providers.
  - Cross-organization trust cards.
  - Customer-tuned scoring models.

## 4. Credential Lifecycle And Rotation

For the credential lifecycle feature, create a Credentials dashboard that visualizes active credentials, expiry windows, rotation events, revoked tokens, credential scopes, agent bindings, and policy failures. It must include Active Credentials, Rotation Queue, Revocations, Scope Review, Expiry Calendar, and Settings menus to configure TTLs, scopes, rotation policies, issuers, and emergency revocation rules.

### What Exists

- Credential model and manager in `packages/agent-mesh/src/agentmesh/identity/credentials.py`.
- Lifecycle state support for credential rotation in `LifecycleManager`.
- Credential status visualization in the simulated trust dashboard.
- MCP message signer and session auth in `packages/agent-os`.

### Mocked Or Demo-Only

- Credential manager state is in-memory.
- Dashboards synthesize credential status.
- No central issuer, persistent revocation list, rotation job, or UI.
- No production key management integration by default.

### Missing

- Persistent credentials table storing hashes and metadata only.
- Rotation scheduling and execution.
- Revocation propagation.
- Credential scope review.
- Credential issuance audit and sponsor approval.
- Expiry alerting.

### Build Required

- Backend:
  - `agent_credentials`, `credential_scopes`, `credential_rotations`, `credential_revocations`, `credential_issuers`.
  - APIs for issue, rotate, revoke, verify, list, and scope change request.
  - Adapter over existing `CredentialManager`.
  - Secret material handling via external secret store; DB stores metadata and hashes only.
- UI:
  - Active credential inventory.
  - Rotation queue.
  - Revocation page.
  - Agent credential detail.
  - Emergency revoke button with confirmation and audit reason.
- Jobs:
  - Expiry monitor.
  - Auto-rotation.
  - Revocation cleanup.
- Deployment:
  - Demo can use local generated keys.
  - MVP should use a secret manager or KMS-backed signer.

### Dashboard Visualization

- Active Credentials table columns: agent, credential id, type, scopes, issuer, issued at, expires at, status, rotation policy, last used, last verified.
- Expiry Calendar:
  - Week/month view of expiring credentials.
- Rotation Queue:
  - Pending rotations with reason, impact, target agents, approval status.
- Scope Review:
  - Diff between requested scopes, granted scopes, and policy-allowed scopes.

### Scope

- Must have for demo:
  - Issue short-lived credentials to sample agents.
  - Rotate one credential from UI.
  - Show expiry and audit event.
- Must have for sellable MVP:
  - Persistent metadata.
  - Auto-rotation.
  - Emergency revoke.
  - Scope approval.
  - Secret store integration.
- Later enterprise feature:
  - SPIFFE/SVID.
  - HSM/KMS.
  - Customer CA integration.
  - Certificate transparency or revocation distribution.

## 5. Agent Mesh And Inter-Agent Communication

For the agent mesh feature, create a Mesh Topology dashboard that visualizes live agent-to-agent communication, protocols, trust handshakes, message flows, blocked handoffs, latency, and capability mismatches. It must include Topology, Messages, Handshakes, Protocol Bridges, Handoffs, and Mesh Policies menus to configure allowed peers, protocol adapters, trust thresholds, capabilities, and routing rules.

### What Exists

- Event bus in `packages/agent-mesh/src/agentmesh/events`.
- Trust handshake in `packages/agent-mesh/src/agentmesh/trust/handshake.py`.
- Protocol bridge classes in `packages/agent-mesh/src/agentmesh/trust/bridge.py`.
- Mesh examples, policies, proxy demo, Kubernetes samples.
- Observability metrics and Grafana dashboards.

### Mocked Or Demo-Only

- Some protocol bridge operations return placeholder success.
- Demo traffic is simulated in Streamlit dashboards.
- No central mesh traffic store.
- No deployed mesh control plane API.

### Missing

- Live message ingestion from agents/framework adapters.
- Mesh topology model and connection history.
- Trust-based handoff enforcement UI.
- Protocol bridge configuration.
- Failure reason capture for rejected handshakes.
- Live replay of communication flows.

### Build Required

- Backend:
  - `mesh_connections`, `mesh_messages`, `mesh_handoffs`, `mesh_handshakes`, `protocol_adapters`, `mesh_routes`.
  - APIs for topology, message search, bridge config, handoff approval, handshake logs.
  - SDK hooks for framework integrations to emit mesh messages.
- UI:
  - Topology graph.
  - Message feed.
  - Handoff detail drawer.
  - Protocol bridge config.
  - Trust failure explorer.
- Jobs:
  - Message retention compaction.
  - Topology snapshot calculation.
  - Dead-peer detection.

### Dashboard Visualization

- Topology:
  - Nodes: agents sized by traffic and colored by trust tier/status.
  - Edges: protocol, message volume, latency, deny rate.
  - Filters: environment, protocol, trust tier, framework, time range.
- Messages table columns: timestamp, source, target, protocol, action, decision, latency, trust threshold, correlation id.
- Handoff flow:
  - Select source agent, target agent, task type.
  - Show required capabilities, trust threshold, policy decision, result.

### Scope

- Must have for demo:
  - Use real local agents and governed handoff events.
  - Show allowed and blocked handoff based on trust/capability.
  - Persist message events.
- Must have for sellable MVP:
  - SDK/event hooks for OpenAI Agents, CrewAI, smolagents, LangChain.
  - Mesh route and peer policy management.
  - Topology and search.
- Later enterprise feature:
  - Cross-cluster mesh federation.
  - Protocol bridge marketplace.
  - Multi-tenant routing policies.

## 6. MCP Governance And Security Proxy

For the MCP governance feature, create an MCP Security dashboard that visualizes MCP servers, tools, schemas, scan findings, tool calls, proxy decisions, approval requests, sanitized responses, and rate limits. It must include Servers, Tools, Security Scans, Proxy Traffic, Approvals, Tool Policies, and Response Scanner menus to configure server registration, allowed tools, denied tools, parameter rules, scan baselines, human approval rules, and rate limits.

### What Exists

- MCP gateway in `packages/agent-os/src/agent_os/mcp_gateway.py`.
- MCP security scanner in `packages/agent-os/src/agent_os/mcp_security.py`.
- MCP response scanner in `packages/agent-os/src/agent_os/mcp_response_scanner.py`.
- MCP session auth and message signing in `packages/agent-os`.
- MCP server examples in `packages/agent-mesh/examples` and `examples/mcp-trust-verified-server`.
- MCP policy primitives and Rust/TypeScript SDK references.

### Mocked Or Demo-Only

- Default stores and sinks are in-memory.
- Some demo MCP calls are local examples.
- Scanner has built-in sample rules that need explicit production config.
- No product registry for MCP servers/tools or scan history.

### Missing

- MCP server registry and tool inventory.
- Scan scheduling and diffing between tool versions.
- Proxy traffic store.
- Human approval queue.
- Tool-level policy binding.
- Response sanitizer configuration.
- Rate-limit management and observability.

### Build Required

- Backend:
  - `mcp_servers`, `mcp_tools`, `mcp_tool_versions`, `mcp_scan_runs`, `mcp_findings`, `mcp_tool_calls`, `mcp_approvals`, `mcp_rate_limits`.
  - Gateway adapter that records every call and decision.
  - Scanner API using existing scanner classes.
  - Approval callbacks backed by DB state and UI.
- UI:
  - Server registry.
  - Tool catalog.
  - Scan findings.
  - Proxy live traffic.
  - Approval queue.
  - Tool policy editor.
- Jobs:
  - Scheduled scans.
  - Schema diff detection.
  - Finding severity recalculation.
  - Tool usage summarization.

### Dashboard Visualization

- Servers table columns: name, endpoint, owner, auth type, status, tools, last scan, critical findings, policy pack, traffic.
- Tools table columns: server, tool name, schema hash, risk level, allowed agents, denied agents, approval required, last call, deny rate.
- Security Scan detail:
  - Findings grouped by prompt injection, schema abuse, hidden Unicode, encoded payload, rug pull, cross-server risk, typosquatting.
  - Show tool definition diff and recommended policy.
- Proxy Traffic:
  - Timeline of calls with source agent, tool, params classification, decision, sanitizer action, latency, correlation id.
- Approval Queue:
  - Approve/deny with reason.
  - Show matched policy, tool risk, agent trust, requested params.

### Scope

- Must have for demo:
  - Register one real local MCP server with several tools.
  - Scan tool definitions.
  - Route agent tool calls through MCP gateway.
  - Show one allowed call, one denied call, one approval-required call, and one sanitized response.
- Must have for sellable MVP:
  - Persistent server/tool registry.
  - Scheduled scan and diff.
  - Approval workflow.
  - Rate limits and per-agent policies.
  - Audit export.
- Later enterprise feature:
  - MCP server federation.
  - Customer allowlist catalog.
  - SIEM export.
  - Third-party MCP marketplace risk feeds.

## 7. Audit Logging And Compliance Reporting

For the audit and compliance feature, create a Compliance Evidence dashboard that visualizes policy decisions, identity events, credential changes, MCP calls, trust score changes, runtime controls, discovery findings, plugin actions, and SRE incidents as immutable evidence. It must include Audit Explorer, Evidence Library, Control Map, Reports, Attestations, Violations, and Export menus to configure control frameworks, evidence mappings, report periods, retention, and export destinations.

### What Exists

- Agent OS audit logger with JSONL, in-memory, and logging backends.
- Hypervisor audit commitments and event APIs.
- AgentMesh dashboard API can return audit logs from memory.
- Compliance CLI verifies modules and creates attestations.
- Example audit trails in use-case demos.
- Annex IV and compliance-related files exist in AgentMesh governance tests/examples.

### Mocked Or Demo-Only

- Many audit logs are local files or generated demo events.
- No centralized audit/event store.
- Compliance verifier is capability/install evidence, not full runtime evidence.
- No product report lifecycle or control evidence mapping UI.

### Missing

- Unified audit event schema.
- Append-only event store with tamper-evident hashes.
- Evidence mapping from events to controls.
- Compliance report generation and approval workflow.
- Retention and legal hold.
- Export to PDF/JSON/CSV/SIEM.

### Build Required

- Backend:
  - `audit_events`, `audit_event_hashes`, `evidence_items`, `control_frameworks`, `controls`, `control_mappings`, `compliance_reports`, `attestations`, `violations`.
  - Ingestion API for all packages.
  - Hash-chain or commitment logic integrated with hypervisor commitments.
  - Report renderer.
- UI:
  - Audit Explorer.
  - Evidence Library.
  - Control Map.
  - Report Builder.
  - Violations inbox.
- Jobs:
  - Evidence classification.
  - Report generation.
  - Retention enforcement.
  - Daily integrity verification.

### Dashboard Visualization

- Audit Explorer table columns: timestamp, event type, actor, agent, resource, decision, severity, correlation id, policy id, trust delta, hash status.
- Detail drawer:
  - Raw event JSON.
  - Related events.
  - Matched policy.
  - Evidence mappings.
  - Hash verification.
- Control Map:
  - Framework tabs: SOC 2, GDPR, EU AI Act, HIPAA, internal policy.
  - Control status: pass, warning, failed, insufficient evidence.
  - Evidence count and freshness.
- Report Builder:
  - Select framework, date range, business unit, agents, include raw evidence, export format.

### Scope

- Must have for demo:
  - Store all demo events in one audit table.
  - Show policy, identity, MCP, trust, credential, discovery, and runtime events.
  - Generate a simple compliance report from real demo evidence.
- Must have for sellable MVP:
  - Tamper-evident event chain.
  - Control mapping.
  - Report history.
  - Retention settings.
  - Export API.
- Later enterprise feature:
  - External ledger/notary.
  - SIEM integrations.
  - Legal hold.
  - Custom framework builder.

## 8. Runtime Sandboxing And Execution Controls

For the runtime controls feature, create a Runtime Control dashboard that visualizes sessions, rings, sandbox decisions, sagas, kill-switch events, liability owners, runtime denials, and compensation actions. It must include Sessions, Rings, Sandbox, Sagas, Kill Switch, Liability, and Runtime Policies menus to configure allowed actions, ring thresholds, sandbox providers, session limits, saga steps, and emergency controls.

### What Exists

- Execution sandbox in `packages/agent-os/src/agent_os/sandbox.py`.
- Sandbox provider abstractions in `packages/agent-os/src/agent_os/sandbox_provider.py`.
- Hypervisor sessions, rings, sagas, kill switch, liability, audit, and FastAPI API.
- Runtime package wrapper.
- Docker/Kubernetes examples.

### Mocked Or Demo-Only

- Subprocess sandbox provider is not production isolation.
- Hypervisor state is in-memory.
- Saga execution can use a no-op executor.
- Ring elevation is a public-preview stub and always denied.
- Some session isolation/locks/vector clock modules are public-preview or tracking-only.

### Missing

- Real runtime executor integration.
- Persistent session and saga state.
- Sandbox provider selection and health.
- UI kill-switch workflow.
- Ring policy editor tied to trust and action risk.
- Runtime event ingestion into audit/trust/SRE.

### Build Required

- Backend:
  - `runtime_sessions`, `runtime_actions`, `runtime_ring_decisions`, `sandbox_profiles`, `sagas`, `saga_steps`, `kill_switch_events`, `liability_records`.
  - Adapter over hypervisor API/classes.
  - Real demo executor for sample actions.
  - Runtime policy binding to agent/action/tool.
- UI:
  - Session list.
  - Session detail timeline.
  - Ring decision explorer.
  - Saga builder and execution monitor.
  - Kill switch panel.
  - Sandbox profile settings.
- Jobs:
  - Session timeout monitor.
  - Saga retry/compensation.
  - Sandbox health check.

### Dashboard Visualization

- Sessions table columns: session id, agent, state, ring, started, last action, policy status, sponsor, cost, trust delta.
- Ring Decision chart:
  - Actions by required ring, allowed/denied, reason.
- Saga Builder:
  - Ordered steps, required capabilities, compensation step, timeout, retry count.
- Kill Switch:
  - Emergency action with target agent/session/tool.
  - Requires typed confirmation, reason, sponsor, scope.

### Scope

- Must have for demo:
  - Run a real sample saga with three steps and one compensation.
  - Show ring denial for a privileged action.
  - Trigger kill switch on a demo agent/session.
- Must have for sellable MVP:
  - Persistent runtime state.
  - Real executor interface.
  - Container sandbox option.
  - Runtime policy and trust integration.
- Later enterprise feature:
  - gVisor/Firecracker/Kubernetes isolation.
  - Privileged ring elevation approvals.
  - Distributed saga execution.
  - Advanced session isolation.

## 9. Marketplace And Plugin Lifecycle

For the marketplace feature, create a Marketplace dashboard that visualizes plugin catalog items, manifests, signatures, trust tiers, install state, quality scores, policy compatibility, runtime permissions, and usage trust. It must include Catalog, Installed, Plugin Detail, Publish, Review Queue, Signing Keys, Policies, and Usage menus to configure plugin approvals, allowed types, capability permissions, signing requirements, organization restrictions, and rollout state.

### What Exists

- Plugin manifest model in `packages/agent-marketplace/src/agent_marketplace/manifest.py`.
- Registry in `packages/agent-marketplace/src/agent_marketplace/registry.py`.
- Installer in `packages/agent-marketplace/src/agent_marketplace/installer.py`.
- Marketplace policy in `packages/agent-marketplace/src/agent_marketplace/marketplace_policy.py`.
- Trust tiers, usage trust, quality assessment, and CLI commands.

### Mocked Or Demo-Only

- Registry is in-memory or file-backed.
- Trust and quality scores are not automatically fed by production telemetry.
- Signature verification exists but key and publishing workflows are not a hosted product lifecycle.
- Restricted import checks are partial/static.

### Missing

- Persistent hosted catalog.
- Plugin install records per environment.
- Signing key management.
- Review and approval workflow.
- Runtime telemetry feedback into usage trust.
- Compatibility checks against policies and agent capabilities.

### Build Required

- Backend:
  - `plugins`, `plugin_versions`, `plugin_manifests`, `plugin_installations`, `plugin_reviews`, `plugin_signing_keys`, `plugin_trust_events`, `plugin_policy_results`.
  - APIs for publish, review, install, uninstall, verify, evaluate, promote.
  - Adapter over existing registry, installer, policy, quality, and trust scoring.
- UI:
  - Catalog.
  - Installed plugins.
  - Plugin detail.
  - Publish wizard.
  - Review queue.
  - Signing keys.
  - Usage trust.
- Jobs:
  - Signature verification.
  - Quality scan.
  - Usage trust recomputation.
  - Dependency vulnerability scan.

### Dashboard Visualization

- Catalog table columns: name, version, type, publisher, signature, trust tier, quality score, installs, required capabilities, policy status.
- Plugin Detail tabs:
  - Overview, Manifest, Permissions, Versions, Trust, Usage, Reviews, Audit.
- Install flow:
  - Select environment and target agents.
  - Show required permissions and policy compatibility.
  - Require approval for risky permissions.
  - Install and emit audit event.

### Scope

- Must have for demo:
  - Load two sample plugins into catalog.
  - Verify manifest/signature state.
  - Install one plugin after policy check.
  - Block one plugin due to missing signature or restricted capability.
- Must have for sellable MVP:
  - Persistent catalog.
  - Publish/review/install lifecycle.
  - Signing key management.
  - Usage trust from real telemetry.
- Later enterprise feature:
  - Private marketplaces per tenant.
  - Vendor risk workflow.
  - SBOM and vulnerability integration.
  - Revenue/licensing workflows.

## 10. Shadow AI And Agent Discovery

For the discovery feature, create a Shadow AI Discovery dashboard that visualizes discovered agent processes, config files, GitHub findings, unregistered MCP servers, risk scores, owners, evidence, reconciliation status, and registration actions. It must include Scan Runs, Findings, Risk Triage, Reconciliation, Register Agent, Suppressions, and Scanner Settings menus to configure scan targets, credentials, schedules, rules, risk weights, and registration workflows.

### What Exists

- Agent discovery package with process, config, and GitHub scanners.
- Inventory model and file-backed inventory.
- Reconciler with registry provider abstraction.
- Risk scoring for shadow/unregistered/no-owner/no-identity agents.

### Mocked Or Demo-Only

- Inventory is file-backed by default.
- Registry provider is generic/static; no full product registry integration by default.
- GitHub scan requires token.
- No cloud, Kubernetes, network, or endpoint fleet scanner as a default product workflow.

### Missing

- Scheduled scan orchestration.
- Persistent findings and evidence.
- Integration with central agent registry.
- Triage workflow: assign owner, suppress, register, decommission.
- Scanner credential management.
- Cloud/Kubernetes/repository scanning expansion.

### Build Required

- Backend:
  - `discovery_scanners`, `discovery_targets`, `discovery_runs`, `discovery_findings`, `discovery_evidence`, `discovery_suppressions`, `reconciliation_actions`.
  - APIs to configure and run scans.
  - Registry provider backed by product agent registry.
  - Risk scoring adapter.
- UI:
  - Scan run history.
  - Findings table.
  - Risk detail drawer.
  - Reconciliation workflow.
  - Scanner settings.
- Jobs:
  - Scheduled scans.
  - GitHub organization scan.
  - Local process scan for demo.
  - Reconciliation against registry.

### Dashboard Visualization

- Scan Runs table columns: scanner, target, status, started, duration, findings, high risk, errors.
- Findings table columns: detected name, type, source, owner, identity status, registry match, risk score, evidence count, first seen, last seen, status.
- Finding detail:
  - Evidence list with file/process/repo path.
  - Risk factors.
  - Matched registry candidates.
  - Actions: register as agent, assign owner, suppress, create policy, decommission.

### Scope

- Must have for demo:
  - Run config scanner on repo and local process scanner.
  - Detect one unregistered demo agent.
  - Reconcile it into the product registry from UI.
- Must have for sellable MVP:
  - Scheduled process/config/GitHub scans.
  - Persistent findings.
  - Registry reconciliation.
  - Suppression and owner workflow.
- Later enterprise feature:
  - Kubernetes, cloud, EDR, network, CI/CD, and SaaS scanners.
  - Organization-wide GitHub/GitLab/Bitbucket scanning.
  - CMDB integration.

## 11. Observability, Metrics, And Dashboarding

For observability, create an Operations dashboard that visualizes policy latency, agent uptime, SLOs, cost budgets, incidents, chaos experiments, rollouts, trace links, logs, metrics, and governance outcomes. It must include Overview, SLOs, Incidents, Costs, Chaos, Rollouts, Metrics, Logs, Traces, and Alerts menus to configure objectives, thresholds, budgets, alert routes, experiments, and rollout gates.

### What Exists

- AgentMesh observability metrics, OTel, Prometheus exporter, Grafana dashboards.
- Agent SRE SLOs, cost guards, incidents, circuit breakers, chaos, rollouts, FastAPI API, integrations with Datadog, Langfuse, LangSmith, Arize, AgentOps, MLflow, Braintrust, WandB, OpenLIT, PagerDuty, Prometheus, OpenTelemetry.
- Grafana dashboard JSON files.

### Mocked Or Demo-Only

- Agent SRE API managers are in-memory by default.
- Example dashboards are isolated.
- No central correlation between policy events, trust changes, MCP calls, runtime controls, and SRE incidents.
- Some incident/circuit breaker functions are public-preview/basic.

### Missing

- Unified metric/event ingestion.
- Persistent SLO, cost, incident, chaos, rollout stores.
- Dashboard embedded into central UI.
- Alerts and notification routing.
- Trace correlation IDs across agents, policies, MCP, runtime.

### Build Required

- Backend:
  - `slo_objectives`, `slo_measurements`, `cost_budgets`, `cost_events`, `incidents`, `incident_events`, `chaos_experiments`, `rollouts`, `alerts`, `trace_links`.
  - Adapter over Agent SRE managers.
  - OTel collector ingestion and correlation.
  - Optional Prometheus/Grafana integration.
- UI:
  - Operations overview.
  - SLO management.
  - Incident inbox.
  - Cost dashboard.
  - Chaos experiment runner.
  - Rollout gate monitor.
- Jobs:
  - SLO burn-rate calculator.
  - Cost budget evaluator.
  - Alert dispatcher.
  - Incident auto-correlation.

### Dashboard Visualization

- Operations Overview cards: healthy agents, policy deny rate, critical incidents, SLO burn, cost today, trust average, blocked MCP calls.
- SLO page:
  - Objective table with current value, target, error budget remaining, burn rate, status.
  - Create SLO form: name, SLI, target, window, alert threshold.
- Incidents:
  - Timeline, affected agents, related policies/MCP tools, trust impact, runbook, status.
- Costs:
  - Spend by model/provider/agent/tool/user.
  - Budget actions: warn, throttle, kill.
- Chaos:
  - Experiment catalog and run history.
  - Guardrails and blast radius.

### Scope

- Must have for demo:
  - Persist SLO and cost events from the demo scenario.
  - Show one incident or alert caused by repeated denials/failures.
  - Link event to policy and agent.
- Must have for sellable MVP:
  - OTel/Prometheus integration.
  - Persistent SLO/cost/incident stores.
  - Alerting.
  - Embedded Grafana or native charts.
- Later enterprise feature:
  - Datadog/LangSmith/Langfuse/Arize deep links.
  - Multi-region SLOs.
  - Runbook automation.
  - Advanced chaos scheduling.

## 12. Framework Integrations

For framework integrations, create an Integrations dashboard that visualizes connected frameworks, SDK versions, agents using each framework, policy coverage, telemetry status, model provider credentials, and last successful governed action. It must include Frameworks, Model Providers, Connector Health, Setup Guides, Sample Agents, Webhooks, and SDK Keys menus to configure adapters, provider credentials, bootstrap commands, health checks, and integration-specific policy bindings.

### What Exists

- Agent OS integrations for OpenAI, OpenAI Agents SDK, CrewAI, smolagents, LangChain, LlamaIndex, AutoGen, Google ADK, Semantic Kernel, Anthropic, Gemini, Mistral, Pydantic AI, Guardrails, and more.
- AgentMesh integration package for LangChain, LangGraph, LlamaIndex, Agent Lightning, Dify, OpenAI Agents, OpenClaw, Nostr scaffold.
- Top-level governed examples for OpenAI Agents, CrewAI, and smolagents.

### Mocked Or Demo-Only

- Many demos can run in simulated mode if provider credentials are absent.
- Framework examples are not centrally registered.
- No integration health or telemetry coverage UI.
- No single onboarding wizard.

### Missing

- Connector registry and status.
- Provider credential setup.
- Framework-specific setup snippets.
- Health checks for each integration.
- Integration test matrix.
- Event hooks that standardize telemetry across frameworks.

### Build Required

- Backend:
  - `integrations`, `integration_instances`, `provider_credentials`, `framework_agents`, `integration_health_checks`, `sdk_keys`, `webhooks`.
  - Adapter registry for existing framework integrations.
  - Health check runner.
  - Standard event envelope for all adapters.
- UI:
  - Framework catalog.
  - Connector detail and setup.
  - Provider credentials.
  - Health check output.
  - Sample agent launcher.
- Jobs:
  - Connector health checks.
  - SDK version drift.
  - Provider quota/cost sync.

### Dashboard Visualization

- Frameworks table columns: framework, status, version, connected agents, last event, policy coverage, trust coverage, telemetry status.
- Setup wizard:
  - Select framework.
  - Add provider credentials.
  - Choose agent template.
  - Bind policies.
  - Copy bootstrap config or run demo agent.
- Health detail:
  - Import check, credential check, sample model call, policy enforcement check, event ingestion check.

### Scope

- Must have for demo:
  - OpenAI Agents or LangChain as the primary real demo.
  - CrewAI and smolagents visible as configured examples if credentials are available.
  - Health check and last governed action.
- Must have for sellable MVP:
  - Connector registry.
  - Standard telemetry envelope.
  - Provider secret handling.
  - Framework onboarding wizard.
- Later enterprise feature:
  - Customer SDK distribution.
  - Framework marketplace.
  - Compatibility certification.

## 13. CLI Tools And Scripts As Product Workflows

For CLI/script functionality, create a Workflows dashboard that visualizes available checks, recent runs, outputs, failures, policy lint issues, integrity baselines, SBOM generation, dependency confusion checks, and governance attestations. It must include Workflow Catalog, Runs, Schedules, Artifacts, Attestations, and CLI Export menus to configure recurring jobs, repositories, environments, and exportable commands.

### What Exists

- `agt` CLI with `verify`, `integrity`, `lint-policy`, `doctor`.
- Root scripts for security scan, SBOM generation, dependency confusion checks, vendor import checks, governance checks.
- Many package-specific CLIs for discovery and marketplace.

### Mocked Or Demo-Only

- Runs are local and manual.
- Outputs are terminal text or local artifacts.
- No scheduled execution or product artifact store.
- No UI for lint findings or attestation history.

### Missing

- Workflow runner service.
- Scheduled jobs.
- Artifact capture.
- UI output rendering.
- Linkage to policies, agents, plugins, reports, and compliance evidence.

### Build Required

- Backend:
  - `workflow_definitions`, `workflow_runs`, `workflow_artifacts`, `workflow_schedules`, `workflow_logs`.
  - Runner process that invokes existing CLI functions safely.
  - Artifact storage.
- UI:
  - Workflow catalog.
  - Run detail page.
  - Schedule editor.
  - Artifact browser.
  - Export CLI command.
- Jobs:
  - Recurring scans.
  - Retention cleanup.

### Dashboard Visualization

- Workflow Catalog columns: workflow, source package, purpose, last run, status, artifacts, schedule.
- Run Detail:
  - Logs, status, duration, inputs, output artifacts, linked evidence, rerun button.
- Schedule form:
  - Cron/time interval, target repo/path, environment, credentials, retention, notification.

### Scope

- Must have for demo:
  - Run policy lint and governance verify from UI.
  - Capture output and attach as compliance evidence.
- Must have for sellable MVP:
  - Scheduled workflows.
  - Artifact storage.
  - Notification on failure.
  - CLI export for reproducibility.
- Later enterprise feature:
  - Distributed runners.
  - Air-gapped runner.
  - CI/CD provider integrations.

## 14. Existing Dashboards, Demos, Examples, And Notebooks

For the existing demos, create a Demo Lab dashboard that visualizes runnable scenarios, prerequisites, seed data, live agents, scenario steps, expected policy decisions, audit events, trust changes, and reset controls. It must include Scenario Catalog, Scenario Runner, Prerequisites, Live Evidence, Reset Environment, and Export Script menus to configure which demo agents, policies, MCP servers, model providers, and fixtures are active.

### What Exists

- Streamlit governance dashboard.
- Streamlit AgentMesh trust dashboard.
- Agent SRE and hypervisor example dashboards.
- Grafana dashboard JSONs.
- Dozens of use-case demos.
- Notebooks for educational walkthroughs.

### Mocked Or Demo-Only

- Several dashboards use generated data.
- Examples require manual setup.
- Notebooks are explanatory, not operational.
- No scenario orchestration or common evidence store.

### Missing

- Scenario registry.
- One-click demo start/stop/reset.
- Live state instead of random dashboard data.
- Prerequisite validation.
- Scripted sequence of events.
- Demo proof checklist.

### Build Required

- Backend:
  - `demo_scenarios`, `demo_steps`, `demo_runs`, `demo_fixtures`, `demo_prerequisites`.
  - Scenario runner that starts sample agents/MCP server, loads policies, triggers actions, records evidence.
  - Reset endpoint for demo data.
- UI:
  - Scenario catalog.
  - Step-by-step runner.
  - Live evidence panel.
  - Reset seed.
  - Export demo script.
- Jobs:
  - Environment health check.
  - Scenario cleanup.

### Dashboard Visualization

- Scenario Catalog columns: name, value proof, required services, duration, status, last run, pass/fail.
- Scenario Runner:
  - Left: step list with expected outcome.
  - Center: live event stream.
  - Right: dashboard links and proof checklist.
- Prerequisites:
  - Model provider, database, Redis, MCP server, sample agents, OPA optional, GitHub token optional.

### Scope

- Must have for demo:
  - One end-to-end governed agent scenario.
  - Resettable local data.
  - Live events and dashboard evidence.
- Must have for sellable MVP:
  - Multiple vertical scenarios.
  - Scenario templates.
  - Exportable demo reports.
- Later enterprise feature:
  - Customer-specific scenario builder.
  - Sales engineering demo tenant provisioning.
  - Synthetic data generation controls.
