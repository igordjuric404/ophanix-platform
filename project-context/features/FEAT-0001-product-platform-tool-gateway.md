---
type: feature
id: FEAT-0001
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
  - packages/product-platform/**
  - docs/product-platform-worktree/**
source_inputs:
  - packages/product-platform/README.md
related_features:
  - FEAT-0002
  - FEAT-0003
  - FEAT-0005
related_issues: []
related_plans: []
related_decisions: []
tags: [feature, product-platform, tool-gateway]
---

# Feature: Product Platform And Tool Gateway

## Purpose

Owns Ophanix-specific product-platform implementation and Tool Gateway-related backend/frontend work in the platform worktree.

## Owned Paths

| Path | Responsibility |
|---|---|
| `packages/product-platform/` | Product-platform package source, tests, examples, deploy material, and frontend when present. |
| `packages/product-platform/frontend/` | Product-platform frontend app and UI validation scripts. |
| `docs/product-platform-worktree/` | Historical product-platform plans, follow-up plans, execution logs, and audit remediation evidence. |

## Invariants

- Current source/tests outrank historical worktree logs.
- Public/client-facing gateway behavior must stay aligned with SDK contracts.
- Frontend and backend validation must both be considered when UI depends on API behavior.

## Validation

- Backend: `python -m pytest` from `packages/product-platform/`.
- Frontend: `npm run validate` from `packages/product-platform/frontend/` when frontend changed.

## Agent Rules

- Use worktree docs for rationale, not as current implementation truth.
- Update feature maps or ADRs when product-platform contracts cross package boundaries.
