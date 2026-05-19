# Ophanix Feature Audit Index

## Audit Scope

This index covers feature-level audits for `ophanix-platform` and `ophanix-python-sdk` against `competitor-analysis.md`. The reports inspect current implementation only and compare it to the Ophanix product vision plus benchmark patterns from Microsoft Agent 365, AWS Bedrock AgentCore, Google Agent Platform, LangGraph/LangSmith, CrewAI AMP, OpenAI Agents SDK, Arcade, Composio, JFrog MCP Registry, Temporal, Galileo, Onyx, and Agent Governance Toolkit.

## Created Feature Audits

| Feature | Code | Report |
|---|---:|---|
| Agent identity and registry | AIR | [report-v1](agent-identity-registry/report-v1) |
| Authentication, authorization, and API keys | AUTH | [report-v1](authentication-authorization-api-keys/report-v1) |
| Runtime sessions and durable execution | RDE | [report-v1](runtime-sessions-durable-execution/report-v1) |
| Sagas and compensation | SAG | [report-v1](sagas-compensation/report-v1) |
| Workers and background jobs | WRK | [report-v1](workers-background-jobs/report-v1) |
| AgentMesh and trust | AMT | [report-v1](agentmesh-trust/report-v1) |
| MCP proxy and tool governance | MCP | [report-v1](mcp-proxy-tool-governance/report-v1) |
| Plugin marketplace and plugin security | PLG | [report-v1](plugin-marketplace-security/report-v1) |
| Audit logs and compliance evidence | AUD | [report-v1](audit-compliance-evidence/report-v1) |
| Observability, runtime events, and artifacts | OBS | [report-v1](observability-runtime-events-artifacts/report-v1) |
| Integrations and provider secrets | INT | [report-v1](integrations-provider-secrets/report-v1) |
| Admin UX and developer experience | UXD | [report-v1](admin-ux-developer-experience/report-v1) |
| Tests, documentation, and production readiness | TST | [report-v1](tests-docs-production-readiness/report-v1) |

## Product Area Status

Implemented but not production-complete:

1. Agent registry records, lifecycle events, credentials, and UI views.
2. Tenant auth, RBAC constants, API key hashing, and gateway credential checks.
3. Runtime session/action records, saga builder, demo-safe saga executor, background job tables, and workers.
4. MCP registry, demo proxy tracking, approval records, rate-limit config, and Tool Gateway invocation.
5. Marketplace catalog, reviews, policy checks, signatures, install rows, and trust scoring.
6. Audit events, compliance controls, evidence records, artifacts, and export endpoints.
7. Observability dashboards for SLOs, cost, incidents, chaos, and rollouts.
8. Provider credentials, health checks, connector runs, and Tool Gateway upstream targets.
9. Frontend pages for most product areas and a Tool Gateway-focused Python SDK.

Partially implemented:

1. Durable execution, checkpoints, replay, compensation, worker recovery, and queue semantics.
2. Agent quarantine, revocation, workload identity, environment-scoped governance, and admin actions.
3. MCP policy enforcement, real MCP mediation, supply-chain scan gating, approval replay, and rate limits.
4. Plugin provenance, artifact scanning, signed packages, install policy, and lifecycle kill switches.
5. Trace/eval observability, OpenTelemetry propagation, runtime artifact evidence, and SIEM-grade exports.
6. Delegated OAuth, user-specific tool authorization, vault/KMS-backed secrets, and credential rotation.
7. Enterprise IdP/SSO/SCIM readiness, production CI gates, and SDK package identity.

Missing despite being referenced by the product vision or benchmarks:

1. Production-grade OIDC/JWKS/SAML/SCIM integration.
2. Temporal/LangGraph-style deterministic workflow history, replay, task queues, and checkpoints.
3. JFrog-style plugin/MCP provenance, SBOM, vulnerability, malware, and license gates.
4. Arcade/Composio-style authorization challenge and user-delegated tool execution.
5. LangSmith/Google-style traces, eval datasets, annotation queues, and regression gates.
6. Microsoft Agent 365-style quarantine/revocation workflows with enforcement consequences.
7. Enterprise deployment certification gates, image provenance, backup/restore drills, and live SDK contract coverage.

## P0 Findings Across Reports

1. F-AIR-002 - Agent lifecycle lacks quarantine/revocation states with enforcement consequences.
2. F-AIR-003 - Suspending or decommissioning an agent does not revoke credentials or identities.
3. F-AUTH-001 - Enterprise IdP configuration exists but runtime auth is still local HMAC/dev-token based.
4. F-AUTH-002 - User-delegated OAuth and per-user tool authorization are missing.
5. F-RDE-002 - Durable execution is a demo-safe saga executor, not replayable durable execution.
6. F-SAG-001 - Saga execution state is split between in-memory engines and draft database records.
7. F-WRK-001 - Persistent jobs are created, but the shipped worker loop does not consume the production job queue.
8. F-AMT-003 - AgentMesh policy-aware communication is caller-supplied instead of enforced.
9. F-MCP-001 - Product MCP proxy records demo calls instead of mediating a real MCP data plane.
10. F-MCP-002 - MCP policy bindings are linked but not enforced before tool execution.
11. F-MCP-006 - MCP approvals cannot safely replay original requests and lack execution-grade controls.
12. F-PLG-002 - Product plugin signatures are demo-grade and can trust arbitrary non-empty signatures.
13. F-PLG-003 - Plugin installation has no provenance, SBOM, vulnerability, malware, or license gate.
14. F-AUD-001 - Audit hash chain is stored in mutable database rows with no immutable anchor.
15. F-AUD-002 - Compliance recomputation and exports silently miss events at scale.
16. F-INT-003 - Provider secret handling is demo/env-only and exposes `secret_ref` too broadly.
17. F-INT-005 - Tool Gateway execution is agent-scoped but not user-delegated or approval-aware.

## Recommended Remediation Order

1. Close security enforcement gaps: AUTH, INT, MCP, PLG, AUD.
2. Make registry and trust enforcement real: AIR, AMT.
3. Define durable execution semantics and repair worker/saga behavior: RDE, SAG, WRK.
4. Unify runtime governance and evidence: MCP, OBS, AUD, INT.
5. Repair frontend/admin and SDK developer experience: UXD, TST.
6. Add production gates: CI, live SDK contracts, deployment smoke tests, supply-chain evidence, observability/eval tests.

