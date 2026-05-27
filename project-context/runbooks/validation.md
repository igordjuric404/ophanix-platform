---
type: runbook
id: RUNBOOK-validation-ophanix-platform
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
  - packages/**
  - docs/**
  - examples/**
  - action/**
source_inputs:
  - packages/*/pyproject.toml
  - packages/*/package.json
related_features:
  - FEAT-0001
  - FEAT-0002
  - FEAT-0003
  - FEAT-0004
  - FEAT-0005
  - FEAT-0006
tags: [runbook, validation, tests, monorepo]
---

# Validation Runbook: Ophanix Platform

## Purpose

Defines how agents should select validation for the platform monorepo without running unrelated package suites by default.

## General Rule

Validate at the owning package first. Broaden only when a change crosses package boundaries, public contracts, security controls, compliance evidence, or examples.

## Package Command Matrix

| Change Surface | Preferred Command | Working Directory |
|---|---|---|
| Product-platform backend | `python -m pytest` | `packages/product-platform/` |
| Product-platform frontend | `npm run validate` | `packages/product-platform/frontend/` |
| Agent OS governance | `python -m pytest` | `packages/agent-os/` |
| Agent Mesh trust/identity | `python -m pytest` | `packages/agent-mesh/` |
| Agent SRE | `python -m pytest` | `packages/agent-sre/` |
| Agent Hypervisor | `python -m pytest` | `packages/agent-hypervisor/` |
| Agent Runtime | package-local tests from config | `packages/agent-runtime/` |
| Agent Compliance | package-local tests/CLI checks from docs/config | `packages/agent-compliance/` |
| Adapter package | package-local pytest/npm command | specific adapter under `packages/agentmesh-integrations/` |
| VS Code extension | npm scripts from `package.json` | `packages/agent-os-vscode/` |
| GitHub actions | action-specific tests or dry-run checks | `action/` or `.github/` |
| Docs/project-context | YAML/frontmatter parse plus link/path review | repository root |

## Feature-Based Validation

| Feature | Minimal Validation |
|---|---|
| FEAT-0001 Product Platform and Tool Gateway | Product-platform backend tests; frontend `npm run validate` if UI changed. |
| FEAT-0002 Agent OS Governance | Agent OS package tests and negative-path policy checks when behavior changes. |
| FEAT-0003 Agent Mesh Trust and Identity | Agent Mesh package tests; schema/security review for identity/trust changes. |
| FEAT-0004 Framework Integrations | Adapter package tests and at least one representative example path when feasible. |
| FEAT-0005 Compliance and Agent SRE | Compliance/SRE package tests; evidence links and dashboard/deployment docs when touched. |
| FEAT-0006 Runtime Sandboxing | Runtime/hypervisor tests; benchmark or negative-path validation when isolation/performance changes. |

## Documentation Validation

For `project-context/` changes:

1. Verify Markdown frontmatter parses.
2. Verify `INDEX.yaml` parses.
3. Verify paths referenced in maps/templates are intentional.
4. Check that new structured file types use templates.
5. Update feature/codebase maps when source ownership changes.

## External Or Expensive Validation

Some suites may require provider credentials, containers, browser installs, cloud services, or long-running benchmarks. Do not run those silently. If they are required but unavailable, record:

- command that should be run
- missing prerequisite
- residual risk
- narrower validation that was run instead

## Rules

- Do not run every package suite by default.
- Do not validate generated caches or dependency folders.
- For inherited toolkit surfaces, preserve `.github/copilot-instructions.md` expectations.
- Security-sensitive changes require negative-path tests or explicit review evidence.
- Compliance/evidence changes require source links, not only prose updates.
