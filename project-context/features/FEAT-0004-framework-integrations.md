---
type: feature
id: FEAT-0004
repo: ophanix-platform
status: active
created: 2026-05-27
last_updated: 2026-05-27
last_reviewed: 2026-05-27
last_verified_commit: unknown
owner: unassigned
canonical: true
stability: active
code_paths:
  - packages/agentmesh-integrations/**
  - examples/**
source_inputs:
  - packages/agentmesh-integrations/README.md
related_features:
  - FEAT-0002
  - FEAT-0003
related_issues: []
related_plans: []
related_decisions: []
tags: [feature, integrations]
---

# Feature: Framework Integrations

## Purpose

Owns adapter packages and runnable examples for external agent frameworks and governance/trust integrations.

## Owned Paths

| Path | Responsibility |
|---|---|
| `packages/agentmesh-integrations/` | Adapter packages, integration docs, tests, and templates. |
| `examples/*-governed/` | Runnable examples for governed framework usage. |
| `examples/mcp-trust-verified-server/` | MCP trust verification example surface. |

## Invariants

- Adapter behavior must match framework-specific README guidance.
- Integration examples should remain runnable and safe.
- Shared governance/trust semantics must stay aligned with Agent OS and Agent Mesh.

## Validation

Run package-local tests for the changed adapter and at least one representative example path when feasible.

## Agent Rules

- Do not generalize one adapter's conventions to all adapters without checking local docs.
- Update examples when adapter usage changes.
