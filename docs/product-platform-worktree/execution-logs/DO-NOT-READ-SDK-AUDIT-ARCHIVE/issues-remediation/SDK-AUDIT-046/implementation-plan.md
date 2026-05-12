# SDK-AUDIT-046 Implementation Plan: Gateway API Modularization

## Repository Changes

Create or update:

```text
packages/product-platform/src/product_platform/api/
├── app.py
├── dependencies.py
├── routers/
│   ├── __init__.py
│   ├── system.py
│   └── tool_gateway.py
└── middleware/
    ├── __init__.py
    ├── body_limit.py
    ├── request_context.py
    └── rate_limit.py
packages/product-platform/src/product_platform/tool_gateway/
├── service.py
├── idempotency.py
├── pagination.py
├── rate_limit.py
└── redaction_engine.py
packages/product-platform/tests/test_api_route_parity.py
packages/product-platform/tests/test_tool_gateway_router.py
```

## Refactor Steps

1. Add route parity test before moving code:
   - import current `create_app()`;
   - collect route paths/methods;
   - snapshot gateway routes:
     - `/api/v1/gateway/tools`
     - `/api/v1/gateway/tools/{tool_name}/invoke`
     - any gateway health/admin routes.

2. Create `api/dependencies.py`:
   - `get_settings(request)`
   - `get_database(request)`
   - `get_gateway_http_client(request)`
   - `get_rate_limiter(request)`
   - `get_request_context(request)`

3. Create `api/routers/tool_gateway.py`:
   - instantiate `router = APIRouter(prefix="/api/v1/gateway", tags=["gateway"])`;
   - move gateway discovery route;
   - move gateway invocation route;
   - keep function names stable where possible.

4. Create `tool_gateway/service.py`:
   - `ToolGatewayService.list_tools_for_principal(...)`
   - `ToolGatewayService.invoke_tool(...)`
   - move orchestration out of route handlers.
   - return typed result objects, not FastAPI responses.

5. Update `api/app.py`:
   - include router with `app.include_router(tool_gateway.router)`;
   - leave compatibility helpers until all imports are moved;
   - remove moved route definitions only after route parity passes.

6. Extract middleware:
   - Move body limit logic from `app.py` into `api/middleware/body_limit.py`.
   - Implement supported ASGI receive wrapper at middleware level.
   - Move request ID/correlation context into `request_context.py`.
   - Move rate limit wrapper into `middleware/rate_limit.py` only after SDK-AUDIT-013.

7. Keep behavior stable:
   - No path changes.
   - No response shape changes.
   - No auth semantics changes in this refactor.
   - No database migration in this refactor unless required by other audit items.

8. Remove dead code from `app.py` after tests pass.

## Environment Variables

No new variables for modularization. Preserve all existing environment variables.

## Infrastructure Provisioning

No infrastructure changes.

## IAM And Security

- No IAM changes.
- Verify auth dependencies are still applied to all gateway routes.
- Add tests that unauthenticated discovery and invoke requests still return `401`.

## CI/CD Changes

- Add route parity tests to required product-platform test job.
- Add focused gateway router tests.
- Add optional product-platform type-check target for extracted modules:

```bash
cd packages/product-platform
python3 -m mypy src/product_platform/tool_gateway src/product_platform/api/routers/tool_gateway.py
```

## Rollout

1. PR 1: add parity tests and dependency helpers.
2. PR 2: extract gateway discovery route.
3. PR 3: extract gateway invocation service.
4. PR 4: extract middleware.
5. PR 5: clean dead helpers from `app.py`.

Each PR must be independently deployable.

## Observability

Preserve existing metrics/log fields. Add one structured field:

- `api_domain="tool_gateway"` for gateway route logs.

Track:

- route-level 4xx/5xx counts before and after refactor;
- latency parity before and after refactor.

## Validation

Run after each extraction PR:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m pytest tests/test_api_route_parity.py tests/test_tool_gateway_*.py -q
python3 -m ruff check src/product_platform/api src/product_platform/tool_gateway tests/test_api_route_parity.py
```

Manual smoke:

- start API locally;
- call gateway discovery with missing token and valid token;
- call gateway invocation success and denial.

## Rollback

- Revert the extraction PR only.
- Because each PR preserves route contracts and avoids schema migration, rollback is standard code redeploy.
- Keep route parity snapshot to verify rollback still matches expected routes.

## Acceptance Criteria

- Gateway routes live in `api/routers/tool_gateway.py`.
- Gateway orchestration lives in `tool_gateway/service.py`.
- `app.py` no longer contains the full gateway invocation implementation.
- Existing gateway tests pass unchanged.
- Route parity test proves no public API path/method changed.
