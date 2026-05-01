# Product Platform Work Tree

This folder breaks the productization work into atomic implementation plans. The previous folder, `docs/product-platform-plan`, explains what exists and what is missing. This folder turns those findings into executable work.

## Navigation Convention

The tree uses a consistent three-level structure:

```text
NN-grand-feature/
  NN-capability-group/
    NN-atomic-feature.md
```

Rules:

- A top-level folder is a grand feature or product workstream.
- A second-level folder groups closely related features.
- Each `.md` file is a single, narrowly scoped implementation plan.
- Each plan is intended to be implementable by one AI agent without needing to infer broad product requirements.
- Every plan includes independently testable phases and final validation.

## Grand Feature Order

1. `00-platform-foundation`: shared API, auth, data, event, worker, and frontend foundations.
2. `01-agent-registry`: agent identity, lifecycle, credentials, and shadow AI discovery.
3. `02-policy-governance`: policy management, policy execution surfaces, audit, evidence, and reports.
4. `03-trust-mesh`: trust scores, trust cards, handshakes, and mesh communication.
5. `04-mcp-runtime-security`: MCP security, runtime sessions, sandboxing, sagas, and kill switch.
6. `05-ecosystem-operations`: marketplace, observability, integrations, and workflow runner.
7. `06-demo-delivery`: demo lab, resettable demo environment, and deployment packaging.

## Standard Plan Sections

Each leaf plan should contain:

- Feature scope.
- Existing repo assets to reuse.
- Out of scope.
- Data model.
- API surface.
- UI surface.
- Implementation phases.
- Tests for every phase.
- Overall validation.
- Dependencies.
- Definition of done.

## Execution Guidance

Build in dependency order. Start with `00-platform-foundation`, then implement vertical product slices. A useful first vertical slice is:

1. Product API shell.
2. Canonical database schema.
3. Event and audit pipeline.
4. Application shell navigation.
5. Agent registration wizard.
6. Policy library and versioning.
7. Policy bindings and simulator.
8. MCP server registry and proxy traffic.
9. Trust score pipeline.
10. Scenario catalog runner.

That slice is enough to produce a real end-to-end demo without redesigning the governance engines.
