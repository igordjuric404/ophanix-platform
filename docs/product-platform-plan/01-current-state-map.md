# Current-State Map

## Executive Summary

The repository is best understood as a broad toolkit rather than a product. It contains meaningful governance primitives spread across packages, examples, quickstarts, notebooks, scripts, Streamlit demos, Grafana dashboards, and framework integrations. The current experience is code-first and manually assembled. A buyer or evaluator cannot open one product surface, register agents, bind policies, run governed actions, observe trust changes, inspect audit evidence, and export compliance reports without reading repo internals.

The product opportunity is a centralized control plane that wraps the existing engines and examples, persists their state, connects their events, and exposes them through one web UI.

## Major Packages

| Area | Path | What Exists | Current Interface | Product Readiness |
| --- | --- | --- | --- | --- |
| Policy engine and Agent OS | `packages/agent-os` | YAML/JSON policy schema, policy evaluator, OPA and Cedar backends, MCP gateway, MCP scanners, prompt injection detection, sandbox helpers, audit logger, framework integrations, FastAPI service for a small subset of capabilities | Python APIs, examples, partial FastAPI API, YAML files | Strong core primitives. Missing central policy CRUD, versioning, approval, bindings, persistence, product UI, and live event aggregation |
| Agent Mesh | `packages/agent-mesh` | DID identity, registry, credentials, lifecycle manager, trust cards, trust handshake, reward scoring, event bus, dashboard API, storage abstractions, protocol bridges, observability, Grafana dashboards | Python APIs, examples, Streamlit trust dashboards, generic storage providers | Strong primitives. Missing persisted product registry, real topology, operational API, cross-package event pipeline, UI workflows, and real integrations for some bridge actions |
| Runtime and hypervisor | `packages/agent-hypervisor`, `packages/agent-runtime` | Sessions, rings, sagas, kill switch, liability, audit commitments, FastAPI API, Docker/Kubernetes examples | Python APIs, FastAPI API, examples | Useful runtime control skeleton. Several controls are public-preview or stub-level. Missing persistent orchestration, real executors, UI, auth, deployment story |
| Compliance | `packages/agent-compliance` | Unified `agt` CLI, policy linting, integrity verification, governance attestation, security/supply-chain helpers | CLI, Python APIs, examples | Useful build-time and verification tooling. Missing recurring scans, evidence store, report lifecycle, control mapping UI, and live runtime compliance |
| Agent Discovery | `packages/agent-discovery` | Local process scanner, config scanner, GitHub scanner, inventory, reconciliation, risk scoring | CLI/Python APIs, JSON inventory | Useful shadow AI foundation. Missing scheduled scanning, cloud/Kubernetes/network scanners, registry integration, UI triage, and product ownership workflow |
| Marketplace | `packages/agent-marketplace` | Plugin manifests, registry, installer, trust tiers, usage trust scoring, quality assessment, policy enforcement, CLI commands | CLI/Python APIs, file/in-memory registry | Good primitive set. Missing hosted catalog, persistent installs, signing workflow, review gates, runtime usage telemetry, UI lifecycle |
| Agent SRE | `packages/agent-sre` | SLOs, cost guards, incident handling, circuit breaker, chaos tests, rollouts, observability integrations, FastAPI API, Grafana dashboards | Python APIs, FastAPI API, examples, dashboards | Good operations layer. Missing persistent telemetry ingestion, cross-agent correlation, UI workflows, incident lifecycle tied to governance events |
| Framework integrations | `packages/agent-os/src/agent_os/integrations`, `packages/agentmesh-integrations`, `examples/*-governed` | Adapters and examples for OpenAI Agents, CrewAI, smolagents, LangChain, LlamaIndex, Google ADK, AutoGen, Semantic Kernel, Mistral, Gemini, Anthropic, Dify, LangGraph, Agent Lightning, MCP | Python packages, demos, framework-specific examples | Broad integration story exists. Missing a connector registry, onboarding wizard, health checks, sample deployments, integration test matrix, UI configuration |
| VS Code extension | `packages/agent-os-vscode` | Local dashboard extension with mock/live backend concepts, local WebSocket token security | VS Code extension | Useful developer surface, but not the sellable product control plane |

## Demos, Examples, and Notebooks

| Area | Path | What It Shows | Current Limitation |
| --- | --- | --- | --- |
| Governance dashboard demo | `demo/governance-dashboard` | Fleet overview, shadow agents, lifecycle monitor, policy feed, trust heatmap | Uses generated random demo data from `demo_data.py`; not connected to real registry, policy engine, audit log, or trust engine |
| AgentMesh trust dashboard | `packages/agent-mesh/examples/06-trust-score-dashboard/trust_dashboard.py` | Trust network, trust scores, credential lifecycle, protocol traffic, compliance tabs | Explicit simulated data for agents, trust history, credentials, traffic, audit, and compliance |
| AgentMesh registration demos | `packages/agent-mesh/examples/00-registration-hello-world` and related examples | Identity, registration, MCP server examples, policies, Docker/Kubernetes samples | Mostly example-local. Not a persistent product onboarding workflow |
| Agent OS examples | `packages/agent-os/examples` | Use-case-specific governed agents: finance, healthcare, ecommerce, devops, SQL, chat, carbon, pharma, trading | Valuable scenarios but scattered. Each requires manual setup and separate policy/config understanding |
| Top-level framework demos | `examples/openai-agents-governed`, `examples/crewai-governed`, `examples/smolagents-governed` | Governance applied to popular agent frameworks | Good proof points. Need centralized setup, visible state, real dashboard evidence |
| Notebooks | `notebooks/*.ipynb` | Policy enforcement, MCP security proxy, multi-agent governance, LangChain chatbot | Good education artifacts, not a product workflow |
| Agent SRE examples | `packages/agent-sre/examples` | SLOs, chaos, cost guards, rollouts, monitoring, dashboards | Mostly isolated examples. Needs live telemetry linkage and product UI |
| Hypervisor examples | `packages/agent-hypervisor/examples` | Runtime sessions, rings, sagas, dashboard, Docker Compose | Useful runtime demo. Needs real executors, persistence, and integration with agent/policy/trust state |
| Marketplace examples | `examples/marketplace-governance`, `packages/agent-marketplace` CLI docs | Plugin manifests, installs, policy controls, trust tiers | Needs hosted/persistent catalog and lifecycle UI |

## Existing API Surfaces

| API Surface | Path | Capabilities | Gaps |
| --- | --- | --- | --- |
| Agent OS FastAPI | `packages/agent-os/src/agent_os/server/app.py` | Health, readiness, metrics, prompt injection detection, execute, audit injection listing | Fresh/stateless kernel usage, limited endpoints, no auth, no policy CRUD, no agent registry, no central audit store |
| Hypervisor FastAPI | `packages/agent-hypervisor/src/hypervisor/api/server.py` | Sessions, rings, sagas, liability, events, audit commitments, verification history | In-memory global state, no product auth, no DB, no connection to central agent registry/policy store, saga execution defaults to no-op executor |
| Agent SRE FastAPI | `packages/agent-sre/src/agent_sre/api/server.py` | SLOs, cost, chaos, incidents, rollouts, stats, metrics | In-memory managers, not wired to product audit/event pipeline by default |
| AgentMesh dashboard API class | `packages/agent-mesh/src/agentmesh/dashboard/api.py` | Live traffic, leaderboard, trust trends, audit logs, compliance report, overview | Python class over in-memory event bus/analytics plane. Not a deployed product API |

## Important Demo-Only or Non-Production Areas

These are not bad features; they are useful seeds. They must be surfaced honestly and replaced or connected for a product demo.

| Area | Current State | Product Implication |
| --- | --- | --- |
| Streamlit governance dashboard | Random generated fleet, policy events, trust matrix, lifecycle events | Replace with live reads from registry, policy evaluations, audit events, discovery findings, lifecycle records |
| AgentMesh trust dashboard | Hardcoded agents and simulated trust, credentials, protocol traffic, audit | Replace with live trust score store, credential store, event pipeline, MCP/mesh telemetry |
| Protocol bridge examples | Some bridge calls return placeholder success or discovered-agent data | For demo, use real local agents and MCP server. For MVP, implement adapter health checks and live traffic ingestion |
| Hypervisor ring elevation | Public Preview stub; elevation requests are always denied | UI should present current capability as "request denied by preview policy"; later implement enterprise approval/elevation if needed |
| Hypervisor intent locks/vector clocks/session isolation | Public Preview stubs or tracking-only controls | Do not sell as complete isolation/causal enforcement until implemented |
| Subprocess sandbox provider | Explicitly not container isolation | Demo can show policy/sandbox checks, but sellable runtime isolation needs Docker, gVisor, Firecracker, Kubernetes sandbox, or another real isolation provider |
| MCP scanners and sandbox sample rules | Built-in/sample rules require explicit configuration for production | Product needs policy packs, rule management, scan baselines, and customer-tuned exceptions |
| Compliance verifier | Verifies modules/control availability and creates attestations | Product compliance needs runtime evidence mapped to controls, not only installed capability checks |
| Registry, lifecycle, credentials, dashboard APIs | Mostly in-memory or JSON/file-backed defaults | Product needs a canonical database and migration path |
| Marketplace registry and trust | In-memory/file registry and telemetry-derived scoring not fully wired | Product needs catalog DB, signing workflow, install telemetry, and approval workflow |
| Shadow AI discovery | Local process/config/GitHub scanners | Product needs scheduled scanning and cloud/Kubernetes/source-code integrations |

## What The Repo Already Proves

The repository proves that the governance layer can evaluate policies, assign identities, score trust, issue credentials, scan MCP tools, redact or block unsafe content, model lifecycle states, manage runtime controls, discover shadow agents, lint and attest governance controls, and integrate with multiple agent frameworks.

## What The Repo Does Not Yet Prove

The repository does not yet prove that a non-author user can operate this as a platform. It lacks a single product UI, single authenticated API, shared database, event pipeline, workflow orchestration, connector setup, deployment composition, live demo scenario, and evidence/report lifecycle that would make the platform testable, repeatable, and sellable.
