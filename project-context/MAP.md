---
type: project-map
id: MAP-ophanix-platform
repo: ophanix-platform
status: active
created: 2026-05-25
last_updated: 2026-05-27
last_reviewed: 2026-05-27
last_verified_commit: unknown
owner: unassigned
canonical: true
stability: active
code_paths:
  - packages/**
  - features/**
  - docs/**
  - examples/**
  - demo/**
  - action/**
tags: [map, navigation, platform, monorepo]
---

# Project Map: Ophanix Platform

## Summary

`ophanix-platform` is the broad platform monorepo. It contains inherited Agent Governance Toolkit surfaces plus Ophanix product-platform work, governance/runtime packages, framework integrations, demos, feature docs, quickstarts, compliance docs, audits, and execution history.

This repo is large enough that agents should not try to understand it by reading file lists. The useful model is layered: package ownership, feature ownership, documentation authority, workflow entry points, and validation surfaces.

## Repository Role

This repository owns:

- Platform packages and governance/runtime primitives.
- Policy, trust, identity, compliance, SRE, runtime, hypervisor, and integration packages.
- Product-platform worktree material and implementation history.
- Framework integrations and runnable examples.
- Demos and quickstarts.
- Compliance, audit, security, ADR, deployment, and tutorial docs.
- Upstream toolkit documentation and contribution/security rules.
- Agent-oriented repository memory under `project-context/`.

This repository does not own:

- Production infrastructure deployment topology. That belongs in infrastructure repos when present.
- External Python SDK package behavior. That belongs in `ophanix-python-sdk/`.
- Standalone customer demo runtime behavior. That belongs in `ophanix-agent-demo/`.
- Website/marketing implementation. That belongs in `ophanix-site/`.

## Current State

- `packages/` is the main implementation surface.
- `docs/` is large and mixed: stable docs, ADRs, compliance docs, audits, product-platform plans, execution logs, and historical evidence coexist.
- `features/` is a capability-level documentation layer parallel to package docs.
- `quickstart/`, `examples/`, and `demo/` provide runnable onboarding and proof points.
- `.github/copilot-instructions.md` still matters for inherited upstream toolkit rules.
- `project-context/` is the current standardized agent-memory layer.

## Read Order

Use this order when entering the repo:

1. `AGENTS.md`
2. `project-context/MAP.md`
3. `project-context/FEATURE_MAP.md`
4. `project-context/CODEBASE_MAP.md`
5. `README.md`
6. `.github/copilot-instructions.md` when editing inherited toolkit surfaces
7. Relevant package README/docs
8. Relevant tests and examples
9. `docs/product-platform-worktree/` only when product-platform history is needed

## Authority Model

When information conflicts, use this precedence:

1. Current source code and tests.
2. Current package-local docs for package-specific behavior.
3. Accepted decisions in `project-context/decisions/` and upstream ADRs when applicable.
4. `project-context/` maps, feature docs, active plans, and issues.
5. Stable central docs under `docs/`.
6. Feature docs and quickstarts for product semantics.
7. Historical implementation plans and execution logs.
8. Generated artifacts, caches, and local runtime output.

If a historical plan explains why code exists, preserve the rationale in current docs rather than treating the old plan as executable truth.

## Directory Map

This is intentionally shallow. Use `rg --files` for exact files.

```text
ophanix-platform/
|-- AGENTS.md
|-- CLAUDE.md
|-- README.md
|-- .github/
|-- action/
|-- benchmarks/
|-- demo/
|-- docs/
|   |-- adr/
|   |-- audits/
|   |-- compliance/
|   |-- contracts/
|   |-- deployment/
|   |-- product-platform-worktree/
|   |-- security/
|   `-- tutorials/
|-- examples/
|-- features/
|-- fuzz/
|-- notebooks/
|-- packages/
|   |-- agent-compliance/
|   |-- agent-discovery/
|   |-- agent-hypervisor/
|   |-- agent-mesh/
|   |-- agent-os/
|   |-- agent-runtime/
|   |-- agent-sre/
|   |-- agentmesh-integrations/
|   `-- product-platform/
|-- project-context/
|   |-- MAP.md
|   |-- FEATURE_MAP.md
|   |-- CODEBASE_MAP.md
|   |-- INDEX.yaml
|   |-- audits/
|   |-- decisions/
|   |-- execution-logs/
|   |-- features/
|   |-- implementation-plans/
|   |-- issues/
|   |-- qa/
|   |-- research/
|   |-- runbooks/
|   |-- security/
|   |-- specifications/
|   `-- templates/
`-- scripts/
```

## Platform Layers

| Layer | Paths | Responsibility |
|---|---|---|
| Product platform | `packages/product-platform/`, `docs/product-platform-worktree/` | Ophanix-specific platform implementation and historical worktree planning/logs. |
| Governance core | `packages/agent-os/`, `features/policy-engine/` | Policy evaluation, governance runtime, modules, services, templates, examples, and tests. |
| Trust and identity | `packages/agent-mesh/`, `features/trust-scoring/`, `features/zero-trust-identity/` | Trust scoring, credentials, mesh communication, schemas, dashboards, services, SDKs, and deployment assets. |
| Integrations | `packages/agentmesh-integrations/`, `examples/*-governed/` | Framework adapters and runnable governed-agent examples. |
| Compliance and evidence | `packages/agent-compliance/`, `docs/compliance/`, `docs/audits/` | Compliance CLI, schemas, mappings, audits, evidence, and reporting logic. |
| Operations and reliability | `packages/agent-sre/`, `benchmarks/`, dashboards/deployments under packages | SLOs, resilience, observability, chaos, dashboards, operators, and reliability validation. |
| Runtime isolation | `packages/agent-runtime/`, `packages/agent-hypervisor/`, `features/execution-sandboxing/` | Runtime behavior, execution sandboxing, privilege boundaries, benchmarks, tutorials, and tests. |
| Developer tooling | `packages/agent-os-vscode/`, `.github/`, `action/` | Editor tooling, CI workflows, custom actions, security scans, and contribution automation. |
| Examples and onboarding | `quickstart/`, `examples/`, `demo/`, `notebooks/` | Runnable examples, dashboard, onboarding flows, policy samples, and tutorials. |

## Package Areas

| Package Area | Primary Path | Start Here When |
|---|---|---|
| Agent OS | `packages/agent-os/` | The request mentions policies, policy evaluation, governance runtime, modules, services, templates, or governance CLI-adjacent behavior. |
| Agent Mesh | `packages/agent-mesh/` | The request mentions trust, identity, credentials, mesh communication, schemas, services, dashboards, or deployment assets. |
| Integrations | `packages/agentmesh-integrations/` | The request mentions LangChain, CrewAI, OpenAI Agents, ADK, MCP trust proxy, or another framework adapter. |
| Agent Compliance | `packages/agent-compliance/` | The request mentions compliance CLI, schemas, evidence, regulatory mappings, or verification reports. |
| Agent SRE | `packages/agent-sre/` | The request mentions SLOs, reliability, dashboards, chaos, observability, deployments, or operators. |
| Agent Runtime | `packages/agent-runtime/` | The request mentions runtime behavior or governed execution surfaces. |
| Agent Hypervisor | `packages/agent-hypervisor/` | The request mentions sandboxing, privilege rings, isolation, runtime controls, or hypervisor benchmarks. |
| Agent Discovery | `packages/agent-discovery/` | The request mentions shadow AI discovery, agent inventory, or discovery behavior. |
| VS Code Extension | `packages/agent-os-vscode/` | The request mentions editor UX, extension views, snippets, or VS Code assets. |
| Product Platform | `packages/product-platform/` | The request mentions Ophanix product-platform implementation, tool gateway, admin, frontend, runtime, or product-specific backend/frontend work. |

## Documentation Areas

| Area | Path | Use |
|---|---|---|
| Agent context | `project-context/` | Current maps, decisions, issues, plans, logs, schemas, and templates. |
| Central docs | `docs/` | Stable docs, ADRs, audits, compliance, contracts, deployment, diagrams, tutorials, and security docs. |
| Product-platform history | `docs/product-platform-worktree/` | Existing product-platform implementation plans, follow-up plans, logs, audit remediation records, and worktree history. |
| Feature docs | `features/` | Capability-level semantics and product behavior. |
| Package docs | `packages/*/docs/`, package READMEs | Package-local implementation and usage guidance. |
| Quickstarts | `quickstart/` | Numbered onboarding path. |
| Examples and demos | `examples/`, `demo/`, `notebooks/` | Runnable proof points and tutorial material. |

## Project Context Areas

| Path | Purpose |
|---|---|
| `project-context/MAP.md` | Human-readable repository overview and routing. |
| `project-context/FEATURE_MAP.md` | Feature ownership and subsystem routing. |
| `project-context/CODEBASE_MAP.md` | More detailed implementation/test routing. |
| `project-context/INDEX.yaml` | Machine-readable lookup for canonical docs. |
| `project-context/decisions/` | Stable ADRs with status in frontmatter, not status folders. |
| `project-context/issues/` | Tracked issues by status. |
| `project-context/implementation-plans/` | Active/completed/archived implementation plans. |
| `project-context/execution-logs/` | Work logs and validation evidence. |
| `project-context/templates/` | Reusable artifact templates. |

## Common Workflows

### Product Platform Change

1. Confirm the product-platform package/path exists in the current worktree.
2. Read `project-context/FEATURE_MAP.md` entry for Product Platform and Tool Gateway.
3. Inspect `docs/product-platform-worktree/` only for history and rationale.
4. Inspect the owning source paths under `packages/product-platform/`.
5. Locate nearest tests and package-local docs.
6. Implement the narrowest scoped change.
7. Update public/product docs, project-context plans, or ADRs if behavior or contracts change.

### Governance Core Change

1. Start with `packages/agent-os/` and relevant feature docs.
2. Check `.github/copilot-instructions.md` for upstream rules.
3. Identify policy/runtime modules and nearest tests.
4. Validate deterministic policy behavior and negative paths.
5. Update feature docs or ADRs if governance semantics change.

### Trust, Identity, Or Mesh Change

1. Start with `packages/agent-mesh/`.
2. Check relevant feature docs such as trust scoring or zero-trust identity.
3. Locate schemas, services, SDK surfaces, and tests before editing.
4. Treat identity/trust behavior as security-sensitive.
5. Update compliance/security docs when controls or guarantees change.

### Integration Change

1. Start with `packages/agentmesh-integrations/`.
2. Identify the specific framework adapter.
3. Check runnable examples under `examples/`.
4. Validate adapter behavior against representative examples.
5. Update package docs and example docs together.

### Compliance Or SRE Change

1. For compliance, start in `packages/agent-compliance/`, `docs/compliance/`, and `docs/audits/`.
2. For reliability/SRE, start in `packages/agent-sre/`, dashboards, deployments, and benchmarks.
3. Preserve evidence links and validation commands.
4. Record verification evidence in execution logs or QA reports when tracked.

### Documentation Or Repository-Structure Change

1. Decide whether the document is stable guidance, historical evidence, or generated output.
2. Put current agent guidance in `project-context/`.
3. Keep package-specific details close to the package.
4. Keep historical worktree evidence under `docs/product-platform-worktree/` unless explicitly migrating it.
5. Update templates when changing repeated artifact formats.

## Tests And Quality Gates

- Use package-local tests as the first validation surface.
- Run focused tests before broader test suites.
- Broaden validation when the change crosses package boundaries, public contracts, security controls, or examples.
- Benchmark-sensitive changes should include benchmark or performance evidence.
- Security-sensitive changes should include negative-path tests or explicit review evidence.
- Documentation-only changes should still be checked for links, frontmatter, and consistency with prompts/templates.

## Automation And Tooling

| Area | Path | Use |
|---|---|---|
| GitHub automation | `.github/` | Workflows, templates, code owners, and Copilot instructions. |
| Custom actions | `action/` | Governance attestation and security scan action packaging. |
| Benchmarks | `benchmarks/` | Performance evidence and benchmark tests. |
| Fuzzing | `fuzz/` | Fuzz entrypoints for robustness/security-sensitive behavior. |
| Scripts | `scripts/` | Repo-level helper automation when present. |

## Generated And Ignored Surfaces

| Path | Treatment |
|---|---|
| `.venv-codex-product/` | Local virtual environment; exclude. |
| `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `__pycache__/` | Generated tool/bytecode caches; exclude. |
| `node_modules/`, package-local dependency folders | Installed dependencies; exclude. |
| `dist/`, `build/` | Generated build output; exclude unless needed as evidence. |
| Benchmark result artifacts | Evidence only when relevant to the task. |

## Cross-Repository Relationships

| Repo | Relationship |
|---|---|
| `ophanix-python-sdk/` | External Python client boundary for the Tool Gateway implemented by product-platform surfaces. |
| `ophanix-agent-demo/` | Standalone customer demos. It may reference product-platform planning lineage but should not silently depend on platform runtime. |
| `ophanix-site/` | Public website/marketing boundary. |
| Infrastructure repos | Deployment boundary for production workload and product images when present. |

## Where Not To Start

- Do not start with recursive file listings; choose the owning package or feature first.
- Do not start in generated caches, dependency folders, build outputs, or local virtual environments.
- Do not treat `docs/product-platform-worktree/` logs as current implementation truth without checking code/tests.
- Do not edit inherited toolkit surfaces without checking upstream instructions.
- Do not put cross-repo agent memory in package-local docs when it belongs in `project-context/`.

## Agent Decision Flow

Use this flow for ambiguous tasks:

1. Is the request product-platform-specific? Start with `FEATURE_MAP.md`, then `packages/product-platform/` and `docs/product-platform-worktree/`.
2. Is it governance/policy behavior? Start with `packages/agent-os/`.
3. Is it identity/trust/mesh behavior? Start with `packages/agent-mesh/`.
4. Is it framework-specific? Start with `packages/agentmesh-integrations/`.
5. Is it compliance evidence or SRE? Start with `packages/agent-compliance/`, `packages/agent-sre/`, and relevant docs.
6. Is it docs/memory structure? Start with `project-context/` and templates.
7. Does it cross package boundaries? Check feature docs and consider an ADR or implementation plan update.

## Update Triggers

Update this map when:

- A major package is added, removed, or repurposed.
- Product-platform ownership changes.
- Feature docs or package boundaries are reorganized.
- Cross-repository relationships change.
- The authority model for docs changes.
- New validation workflows become canonical.

Update `FEATURE_MAP.md` when feature ownership, status, primary paths, or validation changes.

Update `CODEBASE_MAP.md` when source/test routing changes at implementation level.

Update `INDEX.yaml` when canonical project-context docs are added, removed, or renamed.

## Navigation Guide

| Need | Go To |
|---|---|
| Understand repo purpose and boundaries | This map. |
| Find feature or subsystem ownership | `project-context/FEATURE_MAP.md`. |
| Find implementation and tests | `project-context/CODEBASE_MAP.md`. |
| Work on package-specific behavior | Package README/docs plus package source/tests. |
| Work on inherited toolkit surfaces | `.github/copilot-instructions.md` plus package-local docs. |
| Work on product-platform history | `docs/product-platform-worktree/`. |
| Track new work | `project-context/issues/`, `implementation-plans/`, and `execution-logs/`. |
| Record long-lived architecture choices | `project-context/decisions/`. |

## Decision Rules

- Prefer package-local README/docs for package-specific behavior and `project-context/` for cross-repo routing and agent memory.
- Preserve upstream toolkit security posture and test expectations when editing inherited packages.
- Put new Ophanix planning, audits, issues, decisions, and execution logs under `project-context/`.
- Keep ADR paths stable under `project-context/decisions/`; status belongs in frontmatter and the decision index.
- Link implementation changes to features, ADRs, plans, or issues when the change affects cross-package contracts.
- Do not treat generated caches, dependency folders, or historical logs as the highest-authority source when code/tests disagree.
