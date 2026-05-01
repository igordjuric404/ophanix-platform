# Dependency Checklist

## Minimum Required For A Demo

| Dependency | Purpose | Notes |
| --- | --- | --- |
| Python environment | Run existing toolkit packages, API, workers, sample agents | Use the repo package layout and local editable installs |
| Node or frontend runtime | Run web UI | Required if building a real product UI instead of Streamlit |
| PostgreSQL | Canonical product state and audit events | Local Docker container is enough for demo |
| Redis | Queue, live event fanout, cache, rate limits | Local Docker container is enough for demo |
| Product API | Central backend | FastAPI recommended |
| Background worker | Scans, trust updates, reports, rotations, demo runner | Redis-backed worker is enough |
| Local MCP server | Real governed tool calls | Include CRM, payments, messaging, and unsafe demo tools |
| Sample agents | Real action source | At least support, refund, and research agents |
| Model provider key | Real agent reasoning | OpenAI, Azure OpenAI, Anthropic, or other configured provider |
| Local signing keys | DID/trust card/credential demo | Demo keys can be generated locally |
| Policy pack | Enforce demo behavior | YAML policies imported into product DB |
| OpenTelemetry Collector | Trace and metric collection | Optional but recommended for demo credibility |
| Prometheus/Grafana | Metrics visualization | Optional if native UI charts are enough |
| OPA container or CLI | Rego-backed policy proof | Optional; local evaluator can be primary demo |
| GitHub token | Repository discovery | Optional; required only for GitHub scanner demo |

## Required For Sellable MVP

| Dependency | Purpose | Notes |
| --- | --- | --- |
| Managed PostgreSQL | Durable product state | Include backup, migration, and restore plan |
| Managed Redis or queue | Background jobs and live updates | Redis, SQS, Pub/Sub, or equivalent |
| Object storage | Reports, exports, scan artifacts, SBOMs | S3, Azure Blob, GCS, or local-compatible storage |
| Identity provider | User auth and RBAC | Auth0, Entra ID, Okta, or built-in auth for early pilots |
| Secret manager | Provider keys, signing keys, tokens | AWS Secrets Manager, Azure Key Vault, Vault, Doppler, etc. |
| TLS and API gateway | Secure product access | Required for customer pilots |
| Observability backend | Logs, metrics, traces | OTel plus Prometheus/Grafana, Datadog, or equivalent |
| CI/CD | Build and deploy product services | Include database migrations |
| Email or notification provider | Approvals, incidents, expiring credentials | Slack, email, PagerDuty optional |
| Model provider integrations | Live agents | At least one primary provider and one fallback path |
| MCP server deployment | Governed tool execution | Local demo server plus customer MCP server support |
| Framework SDK packages | Agent integration | OpenAI Agents, LangChain, CrewAI, smolagents prioritized |
| OPA/Cedar runtime optional | External policy backends | Needed if selling Rego/Cedar policy backend support |
| Report renderer | Compliance exports | PDF/Markdown/JSON generation |

## Required For 100% Enterprise Coverage

| Dependency | Purpose | Notes |
| --- | --- | --- |
| Kubernetes and Helm | Enterprise deployment | Multi-service product deployment |
| SPIFFE/SPIRE | Workload identity | Aligns with zero-trust agent identity story |
| KMS/HSM/Vault | Key protection and signing | Required for stronger credential/trust card posture |
| SCIM | User and group provisioning | Entra/Okta integration |
| SIEM integration | Security audit export | Splunk, Sentinel, Chronicle, QRadar |
| Event streaming | High-volume governance events | Kafka, NATS, SNS/SQS, Pub/Sub, Event Hubs |
| External ledger/notary | Tamper-evident audit anchoring | Optional but valuable for regulated buyers |
| EDR or endpoint inventory | Shadow AI discovery | CrowdStrike, Defender, osquery, etc. |
| Cloud scanners | Cloud-hosted agent discovery | AWS, Azure, GCP |
| Kubernetes scanners | Cluster agent discovery | Pods, deployments, services, config maps, secrets |
| Source control scanners | Code and config discovery | GitHub, GitLab, Bitbucket |
| Package registries | Marketplace and supply chain | npm, PyPI, internal registries |
| Vulnerability scanners | Plugin and dependency risk | OSV, Snyk, Dependabot, Trivy, Grype |
| Commercial observability | Enterprise telemetry | Datadog, New Relic, Grafana Cloud, Honeycomb |
| Runbook/incident provider | Enterprise response | PagerDuty, Opsgenie, ServiceNow |
| Data retention storage | Long-term evidence | WORM storage or compliance archive |

## Feature Dependency Matrix

| Feature | Minimum Demo Dependencies | Sellable MVP Dependencies | 100% Coverage Dependencies |
| --- | --- | --- | --- |
| Policy engine | PostgreSQL, policy pack, local evaluator | Policy versioning DB, approval workflow, optional OPA/Cedar runtime | OPA/Cedar clusters, GitOps, formal review workflow |
| Agent identity | Local signing keys, product registry DB | Secret manager, bootstrap tokens, RBAC | SPIFFE/SPIRE, workload identity, HSM/KMS |
| Trust scoring | Audit events, trust score DB, sample agents | Trust signal pipeline, threshold config, score jobs | Federated trust, external trust providers |
| Credentials | Local generated credentials, DB metadata | Secret manager, rotation worker, revocation store | Customer CA, SPIFFE/SVID, HSM-backed signing |
| Agent mesh | Sample agents, event ingestion | SDK hooks, topology store, protocol adapter config | Cross-cluster federation, high-volume message bus |
| MCP governance | Local MCP server, gateway, scanner | Persistent server/tool registry, approval workflow, scheduled scans | Third-party MCP risk feeds, SIEM export |
| Audit and compliance | Audit table, control seed data, report renderer | Hash chain, evidence mapping, retention, exports | External notary, WORM storage, legal hold |
| Runtime controls | Hypervisor adapter, sample executor | Persistent sessions, real executor, container sandbox | gVisor/Firecracker/Kubernetes isolation, privileged elevation approvals |
| Marketplace | Sample plugin manifests, local signing key | Catalog DB, review workflow, install telemetry | Private tenant marketplaces, SBOM/vulnerability feeds |
| Discovery | Local process/config scanner | Scheduled scans, GitHub scanner, registry reconciliation | EDR, cloud, Kubernetes, network, CI/CD scanners |
| Observability | OTel optional, SLO/cost DB | OTel collector, metrics backend, alerts | Datadog/New Relic/Honeycomb, SIEM, runbook systems |
| Framework integrations | One model provider, one framework adapter | Connector registry, provider secrets, health checks | Certification matrix, customer SDK distribution |
| CLI workflows | Local CLI invocation, artifact capture | Scheduled runner, object storage, notifications | Distributed/air-gapped runners, CI/CD integrations |
| Demo Lab | Scenario runner, sample agents, MCP server | Multiple scenario templates, exportable reports | Sales demo tenant provisioning, customer-specific scenarios |

## Current Mock Or Demo Replacement Checklist

| Current Area | Replacement Needed |
| --- | --- |
| `demo/governance-dashboard/demo_data.py` random fleet and events | Read from product DB: agents, policy evaluations, trust events, lifecycle events, discovery findings |
| `packages/agent-mesh/examples/06-trust-score-dashboard/trust_dashboard.py` simulated trust data | Read from persisted trust scores, credentials, protocol traffic, audit events |
| In-memory AgentMesh registry | Product `agents` and `agent_identities` tables with adapter calls into existing registry logic |
| In-memory credential manager | Product credential metadata store plus secret manager-backed issuer |
| In-memory dashboard API state | Central event store and live event stream |
| Agent OS limited FastAPI API | Product API wrapping policy, MCP, audit, sandbox, and integration functionality |
| Hypervisor in-memory state | Product runtime session/saga/ring tables and runtime event ingestion |
| Agent SRE in-memory managers | Product SLO/cost/incident/chaos/rollout persistence |
| Marketplace file/in-memory registry | Product plugin catalog, install records, review workflow |
| Discovery file inventory | Product discovery runs/findings/evidence tables |
| Compliance CLI-only outputs | Workflow runner with artifact and evidence storage |
| Subprocess sandbox only | Container or external sandbox provider for production claims |
| Protocol bridge placeholder responses | Real sample agents/MCP traffic for demo; adapter health checks for MVP |

## Secrets And Credentials Needed

Demo:

- `MODEL_PROVIDER_API_KEY`
- Local signing seed or generated keys.
- Optional `GITHUB_TOKEN`.
- Optional OPA endpoint.

MVP:

- Model provider keys.
- Database credentials.
- Redis credentials.
- Secret manager credentials.
- IdP client id/secret.
- Webhook signing secrets.
- MCP server credentials.
- Marketplace signing keys.

Enterprise:

- KMS/HSM access.
- SPIFFE trust bundle.
- SIEM credentials.
- Cloud provider read-only scanner credentials.
- EDR/CMDB credentials.
- Package registry credentials.

## Deployment Assumptions

Demo:

- Single developer machine.
- Docker Compose available.
- One organization and one environment.
- Local sample agents and MCP server.
- Seed data is resettable.

Sellable MVP:

- One tenant or small multi-tenant deployment.
- Authenticated users.
- Durable storage.
- Backups.
- TLS.
- Basic RBAC.
- Operational monitoring.

Enterprise:

- Multi-tenant or isolated-tenant architecture.
- SSO and SCIM.
- Audit retention commitments.
- Network restrictions.
- Bring-your-own-key option.
- SIEM and compliance integrations.
