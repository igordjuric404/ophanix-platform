# SDK-AUDIT-044 Implementation Plan: Cursor And Snapshot Pagination

## Repository Changes

Create or update:

```text
packages/product-platform/src/product_platform/tool_gateway/
├── pagination.py
├── repository.py
└── schemas.py
packages/product-platform/src/product_platform/api/app.py
packages/ophanix-tool-gateway-sdk/src/ophanix_tool_gateway/sdk.py
packages/product-platform/src/ophanix_tool_gateway/sdk.py
packages/product-platform/tests/test_tool_gateway_cursor_pagination.py
packages/ophanix-tool-gateway-sdk/tests/test_cursor_pagination.py
```

## Server Implementation

1. Add `pagination.py`:
   - `GatewayToolCursorPayload`
   - `encode_cursor(payload, secret)`
   - `decode_cursor(token, secret)`
   - `cursor_filters_hash(filters)`
   - HMAC-SHA256 signing over base64url JSON payload.

2. Add settings:
   - `OPHANIX_GATEWAY_CURSOR_SIGNING_SECRET`
   - `OPHANIX_GATEWAY_CURSOR_TTL_SECONDS=900`
   - production requires non-default secret.

3. Update API query params:
   - `limit: int = 100`
   - `cursor: str | None = None`
   - keep `offset` only for deprecated compatibility.

4. Update response model:
   - Add `next_cursor`.
   - Add `has_more`.
   - Keep `offset` fields only for deprecated path.

5. Repository query:
   - Order by `updated_at DESC, id DESC`.
   - First page:
     - query visible rows with filters;
     - capture first page plus one;
     - set snapshot boundary to the maximum visible sort tuple at request start.
   - Next page:
     - validate cursor scope and filters hash;
     - query rows within snapshot and after last tuple.

6. Add indexes:
   - PostgreSQL: `(organization_id, environment_id, status, updated_at DESC, id DESC)`.
   - SQLite local equivalent.

7. SDK changes:
   - `list_tools(limit=..., cursor=None)` returns `ToolListPage`.
   - `list_all_tools()` follows cursor when present.
   - Preserve offset support only when server returns legacy shape.
   - Add `iter_tools(page_size=100, max_total=None)`.

## Environment Variables

- `OPHANIX_GATEWAY_CURSOR_SIGNING_SECRET`
- `OPHANIX_GATEWAY_CURSOR_TTL_SECONDS=900`

## IAM And Security

- Cursor signing secret stored in the existing deployment secret store.
- Runtime role can read only that secret if the deployment platform uses IAM-scoped secret access.
- Cursor payload must not include raw bearer token or raw credential secret.
- Cursor decode errors return `400 invalid_cursor`, not internal details.

## CI/CD Changes

- Add server tests for cursor pagination.
- Add SDK tests for cursor response parsing and fallback.
- Add migration/index test.
- Add production settings test requiring cursor signing secret.

## Rollout

1. Add cursor fields while retaining offset.
2. Release SDK that prefers cursor.
3. Log legacy offset usage.
4. After two release cycles, mark offset deprecated in docs.
5. Remove offset later only after consumer usage is zero.

## Observability

Metrics:

- `gateway.discovery.cursor_page`
- `gateway.discovery.offset_page`
- `gateway.discovery.invalid_cursor`
- `gateway.discovery.cursor_expired`
- `gateway.discovery.page_size`

Alarm:

- invalid cursor rate > 5% for 10 minutes.

## Validation

Run:

```bash
cd packages/product-platform
PYTHONPATH=src python3 -m pytest tests/test_tool_gateway_cursor_pagination.py -q
cd ../ophanix-tool-gateway-sdk
PYTHONPATH=src python3 -m pytest tests/test_cursor_pagination.py -q
```

Required cases:

- first page returns `next_cursor` when more rows exist.
- next page returns no duplicates.
- concurrent update during traversal does not skip rows within snapshot.
- cursor with changed filters is rejected.
- expired cursor is rejected.
- tampered cursor is rejected.

## Rollback

- Keep offset path active during rollout.
- If cursor bug appears, SDK can fall back to offset by feature flag `OPHANIX_SDK_DISABLE_CURSOR_PAGINATION=true`.
- Do not invalidate existing offset clients.

## Acceptance Criteria

- Gateway discovery supports signed cursor pagination.
- SDK follows cursor pagination by default.
- Concurrent catalog changes do not create duplicates or skips inside the snapshot.
- Cursor secrets are required in production.
- Offset pagination usage is observable and deprecated.
