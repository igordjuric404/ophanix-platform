# SDK-AUDIT-003 Research: Production DB Backend And Multi-Worker Transaction Model

## Problem

The product-platform runtime database layer is SQLite-only and process-local. `product_platform.db.migrator` rejects non-`sqlite:///` URLs, `Database` keeps one shared `sqlite3.Connection`, and transactions are serialized with a process-local lock. This is acceptable for local demos, but it is not a production model for a horizontally scaled FastAPI gateway running multiple workers or instances.

Current limitations:

- No shared durable state across ECS tasks, Kubernetes pods, or multiple Uvicorn/Gunicorn workers.
- One connection per process with a global lock, so write throughput is bounded by the slowest transaction.
- SQLite file locking is fragile in containerized multi-instance deployment.
- Migrations are raw SQLite SQL and not portable to PostgreSQL.
- Production startup rejects only the default SQLite URL, not SQLite generally.
- Long gateway transactions can hold locks while upstream network calls run.

## Industry Pattern

Production API control planes typically use a managed relational database with:

- PostgreSQL or MySQL as the source of truth.
- Connection pooling at the application and/or managed proxy layer.
- Short transactions that only wrap database work.
- Row-level locking and optimistic concurrency for state transitions.
- Online migrations with forward/backward-compatible deploys.
- Health checks that verify database reachability, migration level, and pool saturation.

For an MVP startup, the managed default should be a small Amazon RDS for PostgreSQL instance with automated backups. RDS Proxy, Aurora, Multi-AZ, read replicas, and IAM database auth are useful later, but they add cost and operational surface before the product has traffic that needs them.

## Options

### Option A: Keep SQLite And Add File Locking

Benefits:

- Minimal code change.
- Simple local development.

Tradeoffs:

- Still not horizontally scalable.
- No safe multi-instance state sharing.
- Poor lock behavior under gateway write load.
- Not acceptable for production readiness.

Decision: reject for production. Keep SQLite only as a local/test adapter.

### Option B: DynamoDB For All Runtime State

Benefits:

- AWS-managed, horizontally scalable, serverless.
- Excellent for simple key-value and event ledger workloads.
- Conditional writes and transactions are available for idempotency and atomic workflows.

Tradeoffs:

- Existing schema is relational and query-heavy.
- Reporting, joins, filters, and product UI queries would need substantial redesign.
- Migration from SQL repositories would be broad.

Decision: reject as the primary product-platform database. Use DynamoDB selectively where key-value semantics are dominant, such as optional idempotency ledger offload.

### Option C: Small Amazon RDS PostgreSQL Instance With Application Pooling

Benefits:

- AWS-managed relational database aligned with existing SQL repository model.
- Supports multi-worker and multi-instance deployments.
- Strong transactions, row-level locking, indexes, JSONB, and mature migration tooling.
- Lowest-cost AWS-native production database path for the MVP.

Tradeoffs:

- Requires SQL dialect migration and a DB abstraction layer.
- Local development needs PostgreSQL via Docker or a testcontainer.
- Connection pool sizing must be conservative because there is no RDS Proxy initially.

Decision: adopt.

## Final Architecture

Adopt PostgreSQL as the production database backend. For the MVP, deploy a single small Amazon RDS PostgreSQL instance and use PostgreSQL in Docker for local integration tests. Use application-level connection pooling through `psycopg_pool`; defer RDS Proxy, Aurora, Multi-AZ, read replicas, and IAM DB authentication until traffic or compliance requires them.

Architecture:

- `Database` becomes an adapter interface with `SqliteDatabase` and `PostgresDatabase`.
- Production uses `OPHANIX_DATABASE_URL=postgresql+psycopg://...`.
- SQLite remains allowed only when `OPHANIX_ENVIRONMENT` is `local` or `test`.
- Migrations move to dialect-aware files or a migration runner that selects `postgres` vs `sqlite`.
- Gateway invocation uses short transactions:
  - create runtime action and evaluate policy in transaction 1;
  - release DB connection before upstream network call;
  - update action/result/audit in transaction 2;
  - use explicit state transitions for retries and idempotency.
- Repository methods use parameterized SQL through `psycopg` for PostgreSQL and `sqlite3` for local compatibility.
- Transaction isolation defaults to `READ COMMITTED`; use row locks or unique constraints for state transitions that require exactly-once semantics.

## AWS Fit

AWS-managed services are sufficient and preferred:

- Amazon RDS for PostgreSQL for durable relational state.
- Automated RDS backups and point-in-time recovery.
- Application connection pooling with conservative limits.
- AWS Secrets Manager or the deployment platform's existing secret store for DB credentials.
- Amazon CloudWatch basic RDS metrics.

Deferred until justified by usage:

- RDS Proxy for connection surge management.
- Aurora Serverless v2 or Aurora provisioned clusters.
- Multi-AZ failover.
- Read replicas.
- IAM database authentication.

No non-AWS infrastructure is required for the production database path.

## Consequences

- Production readiness improves materially because all gateway workers share one transactional source of truth.
- Tests must run against both SQLite and PostgreSQL until SQLite is removed from non-local surfaces.
- SQL portability becomes an active engineering concern.
- Operational runbooks must include migrations, backup/restore, and connection pool sizing.
