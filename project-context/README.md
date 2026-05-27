---
type: project-context-guide
id: GUIDE-ophanix-platform-project-context
repo: ophanix-platform
status: active
created: 2026-05-25
last_updated: 2026-05-25
last_reviewed: 2026-05-25
last_verified_commit: unknown
owner: unassigned
canonical: true
stability: active
code_paths: []
tags: [agent-docs, navigation, platform]
---

# Project Context

## Purpose

`project-context/` is the agent-oriented knowledge layer for this repository. It gives agents a stable route through the platform monorepo without duplicating every upstream README, package doc, and feature note.

## Read Order

1. `MAP.md` for repository purpose and navigation.
2. `FEATURE_MAP.md` for product and subsystem ownership.
3. `CODEBASE_MAP.md` for implementation locations.
4. `INDEX.yaml` for machine-readable lookup.
5. `.github/copilot-instructions.md` for upstream contribution and security rules when changing inherited Agent Governance Toolkit code.

## Required Structure

Use Markdown with YAML frontmatter for authored knowledge. Use `INDEX.yaml` only as a lookup index. Keep ADR files stable under `decisions/`; decision status belongs in frontmatter and `decisions/index.md`.

## Naming Conventions

- Markdown docs: lowercase kebab-case unless a stable ID is required.
- Features: `FEAT-0001-feature-slug.md`.
- Decisions: `ADR-0001-decision-slug.md`.
- Time-bound packages: `YYYY-MM-DD-slug/`.
- Generated reports: `_generated/`.

## Agent Rules

- Decide whether the task changes Ophanix product-platform work or inherited upstream toolkit behavior before editing.
- Preserve upstream contribution, testing, and security rules from `.github/copilot-instructions.md`.
- Do not move upstream docs into `project-context/` unless the user asks for a migration.
- Keep this folder as routing, decisions, and reusable context; keep generated artifacts under `_generated/` or `assets/`.
