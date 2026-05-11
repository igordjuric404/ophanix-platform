# SDK-AUDIT-046 Research: Gateway API Modularization

## Problem

`packages/product-platform/src/product_platform/api/app.py` is a very large monolithic FastAPI module. Tool gateway routes, auth helpers, middleware, health routes, system config, and unrelated product domains live in one file. This increases review cost and regression risk.

Current limitations:

- Gateway behavior is hard to isolate.
- Route dependencies are implicit.
- Tests must import a very large app factory.
- Small gateway changes risk unrelated merge conflicts.
- Security-sensitive auth and invocation paths are mixed with unrelated UI/control-plane endpoints.

## Industry Pattern

Large FastAPI services typically use:

- `APIRouter` per bounded domain.
- Dependency providers for shared settings, DB, auth, and clients.
- Service modules for business logic.
- Thin route handlers.
- Import-level route registration tests.
- Backward-compatible path preservation during refactors.

## Options

### Option A: Leave Monolith And Add Comments

Benefits:

- No behavior change.

Tradeoffs:

- Does not reduce change risk.
- Does not improve ownership or testing.

Decision: reject.

### Option B: Big-Bang App Rewrite

Benefits:

- Clean architecture quickly.

Tradeoffs:

- High regression risk.
- Hard to review.
- Conflicts with ongoing remediation work.

Decision: reject.

### Option C: Incremental Router Extraction

Benefits:

- Preserves external API paths.
- Can be validated by existing tests.
- Allows gateway code to become separately owned and type-checked.

Tradeoffs:

- Some temporary duplication/adapters.
- Requires disciplined route parity tests.

Decision: adopt.

## Final Architecture

Extract Tool Gateway into a domain module:

```text
product_platform/api/
├── app.py
├── dependencies.py
├── routers/
│   ├── system.py
│   └── tool_gateway.py
└── middleware/
    ├── body_limit.py
    ├── request_context.py
    └── rate_limit.py
product_platform/tool_gateway/
├── service.py
├── auth.py
├── invocation.py
├── response.py
├── rate_limit.py
├── idempotency.py
└── repository.py
```

Principles:

- `app.py` owns app construction, settings, startup/shutdown, and router inclusion only.
- `routers/tool_gateway.py` owns HTTP request/response mapping.
- `tool_gateway/service.py` owns orchestration.
- Repository methods own persistence.
- Middleware is standalone ASGI/FastAPI middleware, not private request monkeypatching.
- Existing URLs remain unchanged.

## AWS Fit

No AWS service is needed for code modularization. This is an internal maintainability remediation. AWS deployment behavior remains unchanged except that extracted modules make production settings, rate limiting, database, and observability remediations easier to validate.

No non-AWS infrastructure is selected.

## Tradeoffs

- Incremental extraction means `app.py` will shrink over multiple PRs rather than all at once.
- Route parity tests are required to prevent accidental path changes.
- The gateway module becomes the first extracted domain because it contains the production readiness risk.
