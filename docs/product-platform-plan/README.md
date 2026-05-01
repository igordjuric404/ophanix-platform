# Product Platform Plan

This folder contains an implementation-oriented product analysis for turning the existing Agent Governance Toolkit repository into a centralized, interactive, demo-ready platform without redesigning the core governance engines.

Deliverables:

1. [Current-State Map](01-current-state-map.md)
2. [Product Gap Analysis](02-product-gap-analysis.md)
3. [Target Platform Architecture](03-target-platform-architecture.md)
4. [Dashboard Specification](04-dashboard-specification.md)
5. [End-to-End Demo Scenario](05-end-to-end-demo-scenario.md)
6. [Dependency Checklist](06-dependency-checklist.md)

The central conclusion is that the repository already contains many strong primitives: policy evaluation, agent identity, trust scoring, MCP controls, runtime controls, discovery, marketplace, compliance, SRE, framework adapters, CLIs, and examples. What is missing is the product control plane: a single persistent API, canonical data model, authenticated web UI, real event ingestion, workflow orchestration, and a repeatable end-to-end demo that uses live toolkit state instead of randomly generated dashboard data.
