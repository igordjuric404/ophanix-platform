# SDK-AUDIT-044 Research: Cursor And Snapshot Pagination Model

## Problem

Gateway discovery uses offset pagination ordered by mutable fields such as `updated_at DESC, id DESC`. If tools are updated between page requests, clients can skip tools or receive duplicates. This affects SDK `list_all_tools()` and any large tenant catalog.

Current limitations:

- Offset pagination over a mutable sort order.
- No cursor token.
- No snapshot boundary.
- No duplicate/skip guarantee during concurrent updates.
- No SDK iterator contract for cursor pagination.

## Industry Pattern

Modern APIs use cursor pagination for mutable datasets. The common database implementation is keyset pagination, where the next page uses the last row's ordered key tuple rather than an offset. For stronger repeatability, APIs can add a snapshot upper bound captured on the first page.

Keyset pagination is a widely used PostgreSQL pattern and is documented by engineering organizations such as GitLab: https://docs.gitlab.com/development/database/keyset_pagination/

## Options

### Option A: Document Non-Snapshot Offset Semantics

Benefits:

- Minimal work.

Tradeoffs:

- Leaves duplicate/skip behavior.
- SDK convenience still has weak correctness.

Decision: insufficient.

### Option B: Cursor Pagination With Keyset Only

Benefits:

- Efficient for large catalogs.
- Avoids offset drift for forward traversal.
- Simple indexes.

Tradeoffs:

- Updates that move rows ahead of the cursor may be missed or duplicated depending on ordering.
- No page-number support.

Decision: useful but not enough for stable full-catalog sweeps.

### Option C: Cursor Pagination With Snapshot Boundary

Benefits:

- Stable traversal for a logical discovery snapshot.
- Efficient with keyset and indexes.
- Stateless cursor token can carry the boundary.

Tradeoffs:

- More complex token signing/encoding.
- Recently updated tools after snapshot start appear only in a later discovery run.

Decision: adopt.

## Final Architecture

Add cursor pagination to `GET /api/v1/gateway/tools` while preserving offset parameters during a deprecation window.

Cursor model:

- First request may omit `cursor`.
- Server captures `snapshot_upper_bound = (max(updated_at), max(id at that timestamp))` under the current visibility filter.
- Page query returns rows where:
  - row sort key is <= snapshot boundary;
  - row sort key is after the previous cursor position for descending traversal.
- Cursor payload:
  - version;
  - organization ID;
  - environment ID;
  - credential ID hash;
  - filters hash;
  - snapshot updated_at;
  - snapshot id;
  - last updated_at;
  - last id;
  - expires_at.
- Cursor is signed with HMAC using an app secret from the deployment secret store.
- Cursor expires after 15 minutes by default.

Response model:

```json
{
  "items": [],
  "next_cursor": "...",
  "has_more": true,
  "limit": 100
}
```

## AWS Fit

AWS services are not needed beyond the selected production database and normal secret management:

- PostgreSQL stores tool definitions and supports indexed keyset queries.
- The existing deployment secret store holds the cursor signing secret.

No non-AWS service is required.

## Tradeoffs

- Cursor tokens are opaque; clients cannot jump to page N.
- Snapshot boundary favors consistency over immediate inclusion of concurrent updates.
- Offset remains temporarily for backward compatibility but SDK should move to cursor first.
