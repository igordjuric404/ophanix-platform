---
type: feature-map
id: FEATURE-MAP-ophanix-platform
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
related_features:
  - FEAT-0001
  - FEAT-0002
  - FEAT-0003
  - FEAT-0004
  - FEAT-0005
  - FEAT-0006
tags: [features, ownership, platform]
---

# Feature Map: Ophanix Platform

## Purpose

Routes agents from platform capabilities to owning packages, feature docs, examples, tests, and validation. Use this after `MAP.md` and before `CODEBASE_MAP.md`.

## Feature Inventory

| ID | Feature | Status | Primary Paths | Supporting Docs | Validation Entry |
|---|---|---|---|---|---|
| FEAT-0001 | Product Platform and Tool Gateway | active | `packages/product-platform/**`, `docs/product-platform-worktree/**` | `packages/product-platform/README.md`, product-platform worktree docs | product-platform backend/frontend tests |
| FEAT-0002 | Agent OS Governance | active | `packages/agent-os/**`, `features/policy-engine/**`, `quickstart/**` | `packages/agent-os/README.md`, policy feature docs | agent-os package tests |
| FEAT-0003 | Agent Mesh Trust and Identity | active | `packages/agent-mesh/**`, `features/trust-scoring/**`, `features/zero-trust-identity/**` | `packages/agent-mesh/README.md`, mesh docs/schemas | agent-mesh package tests |
| FEAT-0004 | Framework Integrations | active | `packages/agentmesh-integrations/**`, `examples/*-governed/**` | integration package READMEs, examples | adapter-specific package tests/examples |
| FEAT-0005 | Compliance and Agent SRE | active | `packages/agent-compliance/**`, `packages/agent-sre/**`, `docs/compliance/**`, `docs/audits/**` | compliance/SRE package docs | compliance and SRE package tests |
| FEAT-0006 | Runtime Sandboxing | active | `packages/agent-runtime/**`, `packages/agent-hypervisor/**`, `features/execution-sandboxing/**`, `features/privilege-rings/**` | runtime/hypervisor package docs | runtime/hypervisor tests and benchmarks when relevant |

## Feature Responsibilities

### FEAT-0001 Product Platform and Tool Gateway

Owns Ophanix-specific product-platform implementation, tool-gateway/admin/runtime surfaces, frontend when present, direct HTTP examples, and historical product-platform worktree evidence.

Start here when requests mention Ophanix product platform, Tool Gateway, admin UX, product-platform backend/frontend, product runtime, product audits, or product-platform implementation plans/logs.

### FEAT-0002 Agent OS Governance

Owns policy evaluation, governance runtime behavior, policy templates, modules, services, quickstarts, tutorials, and governance tests.

Start here when requests mention policy engine, deterministic governance, policy templates, allow/deny behavior, policy YAML, governance services, or core Agent OS behavior.

### FEAT-0003 Agent Mesh Trust and Identity

Owns trust scoring, zero-trust identity, mesh communication, credentials, schemas, dashboards, services, deployments, and related SDK surfaces.

Start here when requests mention trust, identity, credentials, mesh, agent communication, trust score, SPIFFE/SVID-style identity, schemas, or mesh deployments.

### FEAT-0004 Framework Integrations

Owns adapter packages for external agent frameworks and runnable governed-agent examples.

Start here when requests mention LangChain, LangGraph, CrewAI, OpenAI Agents, Google ADK, LlamaIndex, Haystack, Dify, Flowise, MCP trust proxy, or other adapter packages.

### FEAT-0005 Compliance and Agent SRE

Owns compliance CLI, evidence mappings, audit surfaces, SLOs, reliability, dashboards, chaos/resilience behavior, operators, and observability examples.

Start here when requests mention compliance, SOC2, NIST, OWASP mappings, audit evidence, SLOs, reliability, error budgets, dashboards, chaos tests, or operational controls.

### FEAT-0006 Runtime Sandboxing

Owns runtime execution boundaries, hypervisor controls, execution sandboxing, privilege rings, kill switch relationships, and benchmark-sensitive runtime behavior.

Start here when requests mention sandboxing, execution rings, runtime isolation, privilege boundaries, kill switch, or runtime performance.

## Routing By Task

| User Request Mentions | Start With | Then Inspect |
|---|---|---|
| product platform, Tool Gateway, admin, product frontend | FEAT-0001 | `packages/product-platform/`, `docs/product-platform-worktree/`, product-platform tests |
| policy engine, governance rules, allow/deny | FEAT-0002 | `packages/agent-os/`, `features/policy-engine/`, agent-os tests |
| trust, identity, mesh, credentials | FEAT-0003 | `packages/agent-mesh/`, schemas, services, mesh tests |
| framework adapter or integration | FEAT-0004 | specific adapter under `packages/agentmesh-integrations/`, examples |
| compliance, evidence, audits | FEAT-0005 | `packages/agent-compliance/`, `docs/compliance/`, `docs/audits/` |
| SRE, SLO, dashboards, reliability | FEAT-0005 | `packages/agent-sre/`, dashboards/deployments, SRE tests |
| sandboxing, runtime isolation, privilege rings | FEAT-0006 | `packages/agent-runtime/`, `packages/agent-hypervisor/`, runtime/hypervisor tests |
| VS Code extension | FEAT-0002 or tooling | `packages/agent-os-vscode/`, package scripts |
| CI/custom action | relevant feature plus automation | `.github/`, `action/`, validation docs |

## Cross-Feature Rules

- Product-platform work can depend on governance, trust, compliance, runtime, and integration packages; update feature docs when contracts cross boundaries.
- Governance and runtime/security changes require negative-path validation.
- Compliance and SRE changes must preserve evidence links and validation commands.
- Integration changes must validate at least one representative adapter/example path.
- Historical worktree docs are useful evidence but lower authority than current code/tests.

## Required Feature Docs

- `features/FEAT-0001-product-platform-tool-gateway.md`
- `features/FEAT-0002-agent-os-governance.md`
- `features/FEAT-0003-agent-mesh-trust-identity.md`
- `features/FEAT-0004-framework-integrations.md`
- `features/FEAT-0005-compliance-agent-sre.md`
- `features/FEAT-0006-runtime-sandboxing.md`
