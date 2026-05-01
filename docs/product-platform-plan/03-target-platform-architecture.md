# Target Platform Architecture

## Architecture Goal

Build a centralized product control plane around the existing governance toolkit. Do not rebuild the core policy engine, identity model, trust logic, MCP controls, sandboxing primitives, marketplace logic, discovery scanners, compliance tools, or SRE engines. Wrap them with persistent services, a unified event model, a web UI, and repeatable deployment.

## High-Level Shape

```text
Browser UI
  |
  v
Product Control Plane API
  |
  +-- Policy Adapter -> existing Agent OS policy evaluator, OPA, Cedar
  +-- Agent Registry Adapter -> existing AgentMesh identity, registry, lifecycle
  +-- Trust Adapter -> existing trust cards, handshake, reward scoring
  +-- Credential Adapter -> existing credential manager and signing helpers
  +-- MCP Adapter -> existing gateway, scanner, response scanner, signer
  +-- Runtime Adapter -> existing hypervisor, sandbox provider, saga, rings
  +-- Marketplace Adapter -> existing marketplace registry, installer, trust tiers
  +-- Discovery Adapter -> existing discovery scanners, inventory, reconciler
  +-- Compliance Adapter -> existing agt verify, lint, integrity, attestations
  +-- SRE Adapter -> existing SLO, cost, incident, chaos, rollout managers
  |
  +-- PostgreSQL: canonical product state and audit
  +-- Redis: cache, live presence, queues, rate limits
  +-- Object storage: reports, exports, SBOMs, scan artifacts
  +-- Event bus: CloudEvents-style governance event stream
  +-- OTel collector: metrics, traces, logs
```

## Product Components

### 1. Web Frontend

Recommended implementation: React or Next.js using a product design system. This is a product surface, not another Streamlit demo.

Responsibilities:

- Single authenticated UI for all major toolkit capabilities.
- Real-time dashboards via WebSocket or server-sent events.
- CRUD workflows for policies, agents, credentials, MCP servers, marketplace items, discovery scans, and SRE objects.
- Demo Lab scenario runner.
- Evidence/report viewers.

### 2. Product Control Plane API

Recommended implementation: FastAPI because several packages already expose or use Python/FastAPI patterns.

Responsibilities:

- Authenticate users and API clients.
- Expose stable product APIs.
- Enforce RBAC.
- Persist product state.
- Call existing toolkit components through adapters.
- Ingest events from agents, gateways, scanners, runtime, and jobs.
- Emit audit records for every product action.

### 3. Adapter Layer

The adapter layer is the main boundary that prevents a rewrite.

Each adapter should:

- Accept product IDs and persisted state.
- Translate product data into existing toolkit class/function calls.
- Convert toolkit return values into product events.
- Record decisions, failures, and latency.
- Preserve raw engine outputs for explainability.

Adapters needed:

- Policy adapter.
- Agent identity and lifecycle adapter.
- Trust scoring adapter.
- Credential adapter.
- MCP gateway and scanner adapter.
- Runtime/hypervisor adapter.
- Marketplace adapter.
- Discovery adapter.
- Compliance workflow adapter.
- SRE adapter.
- Framework integration adapter.

### 4. Database

Use PostgreSQL as the canonical store. The existing generic storage provider can help, but the product needs a relational model that supports joins across policies, agents, trust, audit, credentials, tools, reports, and incidents.

Core tables:

- `organizations`
- `users`
- `roles`
- `api_keys`
- `environments`
- `agents`
- `agent_identities`
- `agent_capabilities`
- `agent_protocols`
- `agent_heartbeats`
- `agent_lifecycle_events`
- `agent_credentials`
- `credential_scopes`
- `credential_rotations`
- `policies`
- `policy_versions`
- `policy_bindings`
- `policy_evaluations`
- `policy_exceptions`
- `trust_scores`
- `trust_dimensions`
- `trust_events`
- `trust_cards`
- `handshake_events`
- `mcp_servers`
- `mcp_tools`
- `mcp_scan_runs`
- `mcp_findings`
- `mcp_tool_calls`
- `mcp_approvals`
- `runtime_sessions`
- `runtime_actions`
- `runtime_ring_decisions`
- `sandbox_profiles`
- `sagas`
- `saga_steps`
- `kill_switch_events`
- `audit_events`
- `audit_event_hashes`
- `evidence_items`
- `control_frameworks`
- `controls`
- `control_mappings`
- `compliance_reports`
- `plugins`
- `plugin_versions`
- `plugin_installations`
- `plugin_reviews`
- `plugin_signing_keys`
- `discovery_scanners`
- `discovery_targets`
- `discovery_runs`
- `discovery_findings`
- `discovery_suppressions`
- `slo_objectives`
- `slo_measurements`
- `cost_budgets`
- `cost_events`
- `incidents`
- `chaos_experiments`
- `rollouts`
- `integrations`
- `provider_credentials`
- `integration_health_checks`
- `workflow_definitions`
- `workflow_runs`
- `workflow_artifacts`
- `demo_scenarios`
- `demo_runs`

### 5. Event And Audit Pipeline

Use a standard event envelope for all product and runtime activity.

Minimum fields:

- `event_id`
- `timestamp`
- `event_type`
- `source_component`
- `organization_id`
- `environment_id`
- `actor_type`
- `actor_id`
- `agent_id`
- `resource_type`
- `resource_id`
- `decision`
- `severity`
- `correlation_id`
- `trace_id`
- `policy_id`
- `policy_version_id`
- `trust_delta`
- `payload`
- `hash_previous`
- `hash_current`

Every existing toolkit component should be connected to this event pipeline by an adapter. The demo should prove this by showing policy, MCP, credential, trust, runtime, discovery, marketplace, and compliance events in one Audit Explorer.

### 6. Background Workers

Use a queue-backed worker system. For the simplest demo, Redis-backed RQ, Celery, or Arq is enough.

Jobs:

- Policy lint and drift detection.
- Policy rollout health checks.
- Trust recalculation and decay.
- Credential expiry and rotation.
- MCP scheduled scans and tool diffing.
- Discovery scheduled scans.
- Compliance report generation.
- Audit hash verification.
- SLO burn-rate calculation.
- Cost budget evaluation.
- Integration health checks.
- Workflow runs for existing CLIs/scripts.
- Demo scenario orchestration and reset.

### 7. Integration Layer

Integration layer responsibilities:

- Model provider credentials and health checks.
- Framework adapter setup for OpenAI Agents, LangChain, CrewAI, smolagents, and others.
- MCP server registration and proxy routing.
- Identity provider integration.
- Observability integration.
- SIEM/webhook export.

Minimum demo integrations:

- One model provider key.
- One local MCP server.
- One framework agent, preferably OpenAI Agents or LangChain.
- Local PostgreSQL.
- Local Redis.

100% coverage integrations:

- OPA and Cedar runtimes.
- Entra/Okta/Auth0 for user auth.
- SPIFFE/SPIRE or workload identity.
- KMS/HSM/Vault for signing and secrets.
- Kubernetes runtime.
- Prometheus/OpenTelemetry/Grafana plus Datadog or another commercial observability backend.
- SIEM export.
- GitHub/GitLab/Bitbucket scanners.
- Cloud/Kubernetes discovery.

## Product API Groups

The control plane should expose a stable API with these groups:

- `/api/auth`
- `/api/environments`
- `/api/agents`
- `/api/agents/{id}/identity`
- `/api/agents/{id}/lifecycle`
- `/api/agents/{id}/credentials`
- `/api/policies`
- `/api/policies/{id}/versions`
- `/api/policy-bindings`
- `/api/policy-evaluations`
- `/api/trust`
- `/api/trust/cards`
- `/api/trust/handshakes`
- `/api/mcp/servers`
- `/api/mcp/tools`
- `/api/mcp/scans`
- `/api/mcp/traffic`
- `/api/mcp/approvals`
- `/api/runtime/sessions`
- `/api/runtime/rings`
- `/api/runtime/sagas`
- `/api/runtime/kill-switch`
- `/api/marketplace/plugins`
- `/api/marketplace/installations`
- `/api/discovery/scanners`
- `/api/discovery/runs`
- `/api/discovery/findings`
- `/api/audit/events`
- `/api/compliance/controls`
- `/api/compliance/reports`
- `/api/observability/slo`
- `/api/observability/incidents`
- `/api/observability/costs`
- `/api/integrations`
- `/api/workflows`
- `/api/demo/scenarios`

## Deployment Architecture

### Demo Deployment

Goal: one command starts a real, repeatable demo.

Services:

- Web UI.
- Control plane API.
- Worker.
- PostgreSQL.
- Redis.
- OpenTelemetry Collector.
- Prometheus and Grafana optional.
- Local MCP server with safe demo tools.
- Two or three sample governed agents.
- Optional OPA container for Rego demo.

The demo must use seeded data only for static reference entities. It should not use random fleet, policy, trust, or audit data. The events shown in the UI should come from actual scenario runs.

### Sellable MVP Deployment

Goal: customer pilot can run in a secure cloud environment.

Services:

- Containerized web/API/worker.
- Managed PostgreSQL.
- Managed Redis or queue.
- Object storage.
- Identity provider.
- Secret manager.
- OTel collector and metrics backend.
- TLS and API gateway.
- Backup and restore.
- Tenant/environment isolation.

### Enterprise Deployment

Goal: regulated organization deployment.

Services:

- Kubernetes/Helm.
- Multi-region optional.
- SPIFFE/SPIRE or workload identity.
- Vault/KMS/HSM.
- Kafka/NATS/SNS/SQS style event pipeline.
- SIEM export.
- SSO, SCIM, RBAC, audit retention.
- Customer policy engines.
- Air-gapped runner optional.

## Data Flow For A Governed Action

1. User or demo scenario triggers an agent action.
2. Agent sends action request with agent identity and correlation id.
3. Control plane or sidecar/gateway resolves agent, active credentials, trust score, and policy bindings.
4. Policy adapter evaluates action through existing policy evaluator or OPA/Cedar backend.
5. MCP adapter or runtime adapter executes, blocks, sanitizes, or escalates the action.
6. Result is written as audit event.
7. Trust adapter records score delta.
8. SRE adapter records latency, success, failure, and cost.
9. UI updates Policy Feed, Agent Detail, Trust Center, MCP Traffic, Runtime Session, and Audit Explorer.

## Architecture Decisions

| Decision | Recommendation | Rationale |
| --- | --- | --- |
| Core logic | Keep existing toolkit primitives | Avoid rebuilding what already works |
| Product API | Build one FastAPI control plane | Existing ecosystem is Python and several package APIs already use FastAPI |
| UI | Build a real web app, not Streamlit | Streamlit is useful for examples but insufficient for sellable product workflows |
| Database | PostgreSQL | Strong relational joins across agents, policies, audit, trust, compliance, and marketplace |
| Queue/cache | Redis | Simple local demo and MVP path |
| Events | CloudEvents-style envelope | Allows all packages to emit consistent audit and telemetry |
| Demo data | Use live scenario state | Buyers need to see real decisions, not random dashboards |
| Observability | OTel plus Prometheus/Grafana | Matches existing package direction and scales to commercial backends |
| Secrets | Local env for demo, secret manager for MVP | Keeps demo simple and production safe |

## Non-Goals

- Do not replace the policy evaluator.
- Do not replace identity, trust card, credential, marketplace, discovery, or SRE primitives.
- Do not claim public-preview stubs are production controls.
- Do not build another isolated demo dashboard.
- Do not use random generated governance data as proof.
