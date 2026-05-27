---
type: feature
id: FEAT-0002
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
  - packages/agent-os/**
  - features/policy-engine/**
  - quickstart/**
source_inputs:
  - packages/agent-os/README.md
related_features:
  - FEAT-0006
related_issues: []
related_plans: []
related_decisions: []
tags: [feature, governance, policy]
---

# Feature: Agent OS Governance

## Purpose

Owns core governance and policy behavior: policy evaluation, governance runtime semantics, templates, modules, services, tutorials, and tests.

## Owned Paths

| Path | Responsibility |
|---|---|
| `packages/agent-os/` | Governance package implementation, modules, examples, services, templates, and tests. |
| `features/policy-engine/` | Capability-level policy-engine documentation. |
| `quickstart/` | Onboarding flows that may exercise governance behavior. |

## Invariants

- Policy behavior must remain deterministic.
- Security-sensitive governance changes need negative-path validation.
- Upstream contribution/security guidance applies when changing inherited toolkit surfaces.

## Validation

```bash
python -m pytest
```

Run from `packages/agent-os/`.

## Agent Rules

- Check `.github/copilot-instructions.md` before editing inherited toolkit behavior.
- Update feature docs or ADRs when governance semantics change.
