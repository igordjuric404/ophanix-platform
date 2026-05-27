---
type: decision
id: ADR-0001
repo: ophanix-platform
status: accepted
created: 2026-05-27
last_updated: 2026-05-27
last_reviewed: 2026-05-27
last_verified_commit: unknown
owner: unassigned
canonical: true
stability: active
code_paths:
  - project-context/**
source_inputs:
  - project-context/MAP.md
  - project-context/FEATURE_MAP.md
  - project-context/CODEBASE_MAP.md
related_features:
  - FEAT-0001
  - FEAT-0002
  - FEAT-0003
  - FEAT-0004
  - FEAT-0005
  - FEAT-0006
supersedes: []
superseded_by: null
tags: [adr, project-context, agent-memory, monorepo]
---

# ADR-0001: Use Project Context For Agent Memory

## Status

Accepted.

## Context

The platform repo mixes inherited toolkit packages, Ophanix product-platform work, package-local docs, central docs, feature docs, quickstarts, examples, demos, compliance evidence, audits, and historical execution logs. Autonomous agents need a canonical routing layer that explains authority, ownership, workflows, and validation without duplicating every package README.

## Decision

Use `project-context/` as the canonical cross-repository agent-memory layer for maps, feature ownership, codebase routing, decisions, issues, implementation plans, execution logs, validation runbooks, schemas, and templates.

Keep package-specific implementation details close to their packages. Keep historical product-platform worktree evidence in `docs/product-platform-worktree/` unless explicitly migrated.

## Consequences

- Agents have a stable entrypoint for the monorepo.
- Package-local docs remain authoritative for package-specific details.
- Cross-package decisions and routing live in one predictable place.
- Historical logs stay available but are lower authority than current code/tests and current project-context docs.

## Alternatives Considered

- Make `docs/` the only knowledge root: rejected because `docs/` mixes stable docs, audits, historical logs, and generated-like evidence.
- Put all guidance in package READMEs: rejected because cross-package routing and decisions would remain fragmented.
- Put all guidance in root `AGENTS.md`: rejected because root agent files should stay short and operational.

## Links

- `project-context/MAP.md`
- `project-context/FEATURE_MAP.md`
- `project-context/CODEBASE_MAP.md`
- `project-context/runbooks/validation.md`
