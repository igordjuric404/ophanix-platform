# SDK-AUDIT-006 Research: Server-Side Idempotency Key And Replay Contract

## Problem

The gateway SDK intentionally avoids automatic retries for mutating tool calls because the server has no idempotency contract. If a client times out after the gateway sends a request upstream, the client cannot know whether the tool mutation happened. Retrying can duplicate side effects.

Current limitations:

- No `Idempotency-Key` request header is accepted or persisted.
- No server-side replay cache keyed by principal, tool, payload fingerprint, and key.
- No conflict response when the same key is reused for a different payload.
- No deterministic replay response for completed calls.
- No in-progress behavior for concurrent duplicate requests.
- No TTL, storage, or observability model.

## Industry Pattern

Payment APIs and mutation-heavy APIs commonly require caller-supplied idempotency keys for unsafe methods. The server stores a ledger record before executing the side effect, returns the stored response for identical retries, and returns a conflict for key reuse with different request semantics. The ledger must be durable and shared across workers.

AWS-native building blocks:

- PostgreSQL unique constraints when the main relational DB is already the source of truth.
- DynamoDB conditional writes for a dedicated idempotency ledger. AWS documents DynamoDB conditional writes and transactions as mechanisms for idempotent and atomic workflows: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html and https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transactions.html

## Options

### Option A: Client-Only Retries

Benefits:

- No server changes.

Tradeoffs:

- Unsafe for mutating calls.
- Cannot resolve timeout/unknown outcome.
- Pushes correctness to every SDK consumer.

Decision: reject.

### Option B: Store Idempotency In PostgreSQL

Benefits:

- Simple if SDK-AUDIT-003 PostgreSQL backend exists.
- ACID transaction can create the ledger and runtime action together.
- Easy joins to runtime actions for audit and support.

Tradeoffs:

- Hot idempotency keys increase relational write load.
- TTL cleanup requires scheduled job.
- Cross-region active-active would need additional design.

Decision: adopt as the default because the gateway already needs relational audit state.

### Option C: Store Idempotency In DynamoDB

Benefits:

- AWS-managed, horizontally scalable, low-latency key-value store.
- Conditional writes are ideal for first-writer-wins.
- Native TTL cleanup.

Tradeoffs:

- Adds a second consistency store.
- Requires careful transaction choreography with the SQL runtime action table.
- More operational surface for the first production database remediation.

Decision: keep as a future high-throughput option. Use only if relational ledger hot spots appear.

## Final Architecture

Adopt a PostgreSQL-backed idempotency ledger tied to gateway runtime actions.

Contract:

- Clients MAY send `Idempotency-Key` on `POST /api/v1/gateway/tools/{tool_name}/invoke`.
- Mutating tools SHOULD require `Idempotency-Key`; read-only tools MAY ignore it.
- Key format: 8 to 128 characters, ASCII visible characters, no whitespace/control characters.
- Idempotency scope: organization, environment, agent credential, tool ID, HTTP method, normalized route, idempotency key.
- Payload fingerprint: SHA-256 over canonical JSON request body plus tool ID and version.
- First request inserts ledger row with status `in_progress` and owns execution.
- Concurrent identical request receives `409 idempotency_in_progress` with `Retry-After`.
- Completed identical retry returns the stored gateway response with header `Idempotency-Replayed: true`.
- Same key with different fingerprint returns `409 idempotency_key_conflict`.
- Failed validation before side effects is not stored unless the request reaches gateway execution ownership.
- Upstream timeout after dispatch is stored as `unknown` unless the upstream supports its own idempotency key or reconciliation query.

## AWS Fit

AWS-managed services are sufficient:

- PostgreSQL on the MVP RDS instance for ledger storage.
- An application cleanup command or opportunistic startup-safe cleanup for ledger TTL removal.
- Application metrics/logs for conflicts, replays, and in-progress age.
- Existing deployment secret management inherited from the DB plan.

No non-AWS service is required.

## Tradeoffs And Decisions

- Server-generated keys are not enough because clients need to retry the same logical operation after network failure.
- Storing only success responses is insufficient; denials and safe gateway errors must replay too.
- Storing raw upstream responses is unsafe; store the final sanitized SDK response envelope only.
- The SDK will expose idempotency support but still will not retry mutations automatically unless the caller opts in or the tool is marked idempotent.
