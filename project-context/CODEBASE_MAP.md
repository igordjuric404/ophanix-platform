---
type: codebase-map
id: CODEBASE-MAP-ophanix-platform
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
  - docs/**
  - examples/**
  - demo/**
  - action/**
tags: [codebase, navigation, monorepo]
---

# Codebase Map: Ophanix Platform

## Purpose

Implementation-level router for agents. Use this after `MAP.md` and `FEATURE_MAP.md` to choose package, docs, tests, examples, and validation paths.

## Package Routing

| Path | Contains | Agent Use |
|---|---|---|
| `packages/product-platform/` | Ophanix product-platform backend/frontend package, deployment/examples, tests, and local product artifacts. | Start here for product-platform and Tool Gateway implementation. |
| `packages/agent-os/` | Governance and policy engine package, modules, services, templates, examples, tutorials, and tests. | Start here for core policy/governance behavior. |
| `packages/agent-mesh/` | Mesh trust, identity, schemas, deployments, dashboards, services, SDKs, integrations, and tests. | Start here for trust, identity, credentials, and mesh communication. |
| `packages/agentmesh-integrations/` | Framework adapter packages and adapter docs. | Start here for external framework integrations. |
| `packages/agent-compliance/` | Compliance CLI/source, schemas, examples, docs, and tests. | Start here for compliance verification and evidence behavior. |
| `packages/agent-sre/` | SRE source, operator, dashboards, deployments, charts, specs, examples, and tests. | Start here for reliability, SLOs, observability, and operational controls. |
| `packages/agent-runtime/` | Runtime package source and tests. | Start here for governed runtime execution surfaces. |
| `packages/agent-hypervisor/` | Hypervisor source, examples, benchmarks, notebooks, docs, tutorials, and tests. | Start here for sandboxing, isolation, and privilege controls. |
| `packages/agent-discovery/` | Discovery source and tests. | Start here for shadow AI or agent discovery behavior. |
| `packages/agent-os-vscode/` | VS Code extension source, assets, snippets, package scripts. | Start here for editor tooling. |
| `packages/ophanix-tool-gateway-sdk/` | Tool Gateway SDK package inside platform worktree. | Check before assuming SDK behavior belongs only in external SDK repo. |

## Documentation Routing

| Path | Contains | Agent Use |
|---|---|---|
| `project-context/` | Current agent maps, feature docs, decisions, plans, issues, logs, schemas, and templates. | Start here for repository orientation and durable agent memory. |
| `docs/adr/` | Upstream/inherited ADRs. | Check for architecture choices that predate project-context ADRs. |
| `docs/audits/` | Audit evidence and feature audit reports. | Use for compliance/security/production-readiness history. |
| `docs/compliance/` | Regulatory and framework mappings. | Use for compliance work and evidence updates. |
| `docs/contracts/` | Contract/schema docs. | Use when API/data contracts change. |
| `docs/deployment/` | Deployment docs. | Use for deployment guidance; infra ownership may still be external. |
| `docs/product-platform-worktree/` | Product-platform plans, logs, follow-ups, audit remediation history. | Use for product-platform rationale and historical evidence. |
| `docs/security/` | Security docs. | Use for security posture and controls. |
| `features/` | Capability-level product docs. | Use for feature semantics before package edits. |
| `quickstart/`, `examples/`, `demo/` | Onboarding flows, runnable examples, demos. | Use for smoke paths and expected user-facing flows. |

## Automation And Quality Routing

| Path | Contains | Agent Use |
|---|---|---|
| `.github/` | Workflows, issue templates, actions, Copilot instructions. | Start here for CI/GitHub behavior and upstream contribution rules. |
| `action/` | GitHub Action packaging for governance/security scans. | Start here for action behavior. |
| `benchmarks/` | Benchmarks and result artifacts. | Use when latency/performance claims or regressions matter. |
| `fuzz/` | Fuzzing entrypoints. | Use for security/robustness-sensitive input handling. |
| `notebooks/` | Tutorial and exploratory notebooks. | Use as examples, not source of truth. |

## Routing Matrix

| Task Type | First Files/Dirs | Required Follow-Up |
|---|---|---|
| Product-platform backend | `packages/product-platform/` | Product-platform tests, docs/product-platform-worktree history if needed |
| Product-platform frontend | `packages/product-platform/frontend/` | `npm run validate` from frontend package when available |
| Policy/governance | `packages/agent-os/` | Agent OS tests and relevant feature docs |
| Trust/identity/mesh | `packages/agent-mesh/` | Mesh schemas/services/tests and security docs when controls change |
| Adapter/integration | Specific adapter under `packages/agentmesh-integrations/` | Adapter README, tests, runnable example |
| Compliance/evidence | `packages/agent-compliance/`, `docs/compliance/`, `docs/audits/` | Evidence links and compliance tests |
| Reliability/SRE | `packages/agent-sre/` | SRE tests, dashboards/deployments, operational docs |
| Runtime/sandboxing | `packages/agent-runtime/`, `packages/agent-hypervisor/` | Runtime/hypervisor tests, benchmarks if performance-sensitive |
| VS Code extension | `packages/agent-os-vscode/` | package scripts, extension docs |
| CI/action | `.github/`, `action/` | Workflow/action validation and docs |
| Docs/memory structure | `project-context/`, prompts in workspace root | Frontmatter/YAML validation and template updates |

## Validation Routing

| Change Surface | Focused Validation |
|---|---|
| `packages/product-platform/` backend | `python -m pytest` from `packages/product-platform/` |
| `packages/product-platform/frontend/` | `npm run validate` from frontend package |
| `packages/agent-os/` | `python -m pytest` from `packages/agent-os/` |
| `packages/agent-mesh/` | `python -m pytest` from `packages/agent-mesh/` |
| `packages/agent-compliance/` | Package-local tests or CLI checks from package docs/config |
| `packages/agent-sre/` | `python -m pytest` from `packages/agent-sre/` |
| `packages/agent-runtime/` | Package-local tests when present |
| `packages/agent-hypervisor/` | `python -m pytest` from `packages/agent-hypervisor/` |
| `packages/agent-os-vscode/` | package-local npm scripts from `package.json` |
| Docs/project-context | Frontmatter/YAML validation and link/path review |

## Documentation Authority

| Document Type | Authority |
|---|---|
| Source/tests | Highest authority for current behavior. |
| Package-local README/docs | Best source for package-specific usage and implementation guidance. |
| `.github/copilot-instructions.md` | Required upstream contribution/security rules for inherited toolkit surfaces. |
| `project-context/` | Current cross-repo agent routing, decisions, issues, plans, and logs. |
| `docs/` stable docs | Stable architecture, compliance, deployment, security, and tutorial docs. |
| `docs/product-platform-worktree/` | Historical product-platform rationale and evidence. |

## Conventions

- Keep package-specific docs close to the package.
- Keep cross-repository agent memory, decisions, audits, plans, and execution logs under `project-context/`.
- Do not treat generated caches, build outputs, dependency folders, or local virtual environments as source.
- When a change crosses packages, update `FEATURE_MAP.md`, related feature docs, or ADRs.
- Preserve upstream toolkit security posture and contribution expectations when editing inherited packages.

## Ignored Surfaces

Ignore `.venv-codex-product/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `__pycache__/`, package-local dependency folders, `node_modules/`, `dist/`, `build/`, and generated benchmark artifacts unless explicitly needed as evidence.
