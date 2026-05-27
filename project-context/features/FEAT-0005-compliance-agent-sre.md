---
type: feature
id: FEAT-0005
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
  - packages/agent-compliance/**
  - packages/agent-sre/**
  - docs/compliance/**
  - docs/audits/**
source_inputs:
  - packages/agent-compliance/README.md
  - packages/agent-sre/README.md
related_features:
  - FEAT-0002
  - FEAT-0003
  - FEAT-0006
related_issues: []
related_plans: []
related_decisions: []
tags: [feature, compliance, sre]
---

# Feature: Compliance And Agent SRE

## Purpose

Owns compliance verification, evidence mapping, audit surfaces, SLOs, reliability, dashboards, chaos/resilience behavior, and operational controls.

## Owned Paths

| Path | Responsibility |
|---|---|
| `packages/agent-compliance/` | Compliance CLI/source, schemas, examples, docs, and tests. |
| `packages/agent-sre/` | SRE implementation, operator, dashboards, deployments, specs, examples, and tests. |
| `docs/compliance/` | Regulatory and compliance mappings. |
| `docs/audits/` | Audit evidence and feature audit reports. |

## Invariants

- Evidence docs must link to concrete source, tests, commands, or controls.
- SRE dashboards/deployments must stay aligned with runtime behavior.
- Compliance claims must not be updated as prose-only assertions.

## Validation

- Compliance: package-local tests/CLI checks from `packages/agent-compliance/`.
- SRE: `python -m pytest` from `packages/agent-sre/`.
- Docs: verify evidence links and source paths.

## Agent Rules

- Preserve evidence chains.
- Record validation outcomes when updating compliance or production-readiness claims.
