# SDK-AUDIT-003 Implementation Plan: Production DB Backend And Multi-Worker Transactions

## Repository Changes

Create or update:

```text
packages/product-platform/src/product_platform/db/
├── base.py
├── connection.py
├── migrator.py
├── postgres.py
├── sqlite.py
└── migrations/
    ├── postgres/
    └── sqlite/
packages/product-platform/tests/
├── test_db_backend_postgres.py
├── test_db_production_settings.py
└── test_tool_gateway_transaction_boundaries.py
packages/product-platform/docker-compose.postgres.yml
docs/deployment/aws-product-platform.md
```

Keep existing migration numbers. Move current SQLite SQL files to `migrations/sqlite/`. Add PostgreSQL equivalents under `migrations/postgres/`.

## Implementation Steps

1. Add dependencies in `packages/product-platform/pyproject.toml`:
   - `psycopg[binary,pool]>=3.2,<4`
   - `sqlparse>=0.5,<1` only if the migrator needs safe statement splitting.

2. Add `db/base.py` with protocols/classes:
   - `DatabaseBackend`
   - `DatabaseConnection`
   - `transaction()`
   - `execute()`
   - `fetchone()`
   - `fetchall()`
   - `close()`
   - `dialect`

3. Split current `connection.py` into:
   - `sqlite.py`: existing behavior, renamed `SqliteDatabase`.
   - `postgres.py`: `PostgresDatabase` using `psycopg_pool.ConnectionPool`.
   - `connection.py`: factory `create_database(database_url, environment)`.

4. Update production validation in `api/app.py`:
   - reject all `sqlite://` URLs when `OPHANIX_ENVIRONMENT` is not `local` or `test`;
   - require `postgresql://` or `postgresql+psycopg://` for `staging` and `production`;
   - require `OPHANIX_DATABASE_SSLMODE=require|verify-full` outside local/test.

5. Update `api/settings.py` environment variables:
   - `OPHANIX_DATABASE_URL`
   - `OPHANIX_DATABASE_POOL_MIN_SIZE`
   - `OPHANIX_DATABASE_POOL_MAX_SIZE`
   - `OPHANIX_DATABASE_POOL_TIMEOUT_SECONDS`
   - `OPHANIX_DATABASE_SSLMODE`
   - `OPHANIX_DATABASE_STATEMENT_TIMEOUT_MS`

6. Update repository SQL placeholders:
   - Keep repository methods parameterized.
   - Add a small placeholder compiler if needed: `?` for SQLite, `%s` for PostgreSQL.
   - Avoid string interpolation for values.

7. Update migrations:
   - Convert JSON `TEXT` columns that are queried or filtered to `JSONB` in PostgreSQL.
   - Convert `INTEGER PRIMARY KEY` to `BIGSERIAL` or text IDs where current code supplies IDs.
   - Add indexes for gateway hot paths:
     - `tool_definitions(status, updated_at desc, id desc)`
     - `tool_runtime_actions(agent_id, created_at desc)`
     - `agent_credentials(token_hash)`
     - `agent_credential_scopes(credential_id, scope, resource_type, resource_id)`
   - Add migration ledger table with unique migration ID.

8. Refactor gateway invocation transaction scope:
   - Transaction 1: authenticate, load tool, evaluate policy, create runtime action with status `pending_upstream`, commit.
   - Outside transaction: perform upstream HTTP request and response redaction.
   - Transaction 2: update runtime action to `succeeded`, `denied`, `upstream_failed`, or `response_blocked`; persist sanitized audit payload; commit.
   - On uncaught exception: transaction 3 marks the action `failed` when an action ID exists.

9. Add PostgreSQL local integration service:
   - `packages/product-platform/docker-compose.postgres.yml`
   - service `postgres:16`
   - database `ophanix_product`
   - user `ophanix`
   - password `ophanix_local_password`
   - exposed port `55432`.

10. Add test commands:
   - SQLite: `PYTHONPATH=src python3 -m pytest tests -q`
   - PostgreSQL: `OPHANIX_DATABASE_URL=postgresql://ophanix:ophanix_local_password@127.0.0.1:55432/ophanix_product PYTHONPATH=src python3 -m pytest tests/test_db_backend_postgres.py tests/test_tool_gateway_*.py -q`

## Infrastructure Provisioning

Provision with the lightest existing infrastructure tool for the repo. For the MVP, this can be a documented AWS console setup first, then codified once the deployment stabilizes.

- Single-instance Amazon RDS PostgreSQL, smallest class that meets local staging/prod needs.
- Automated backups enabled, 7-day retention for MVP.
- Public access disabled.
- DB credentials in AWS Secrets Manager or the current deployment secret store.
- Security groups:
  - app runtime may connect to RDS on `5432`;
  - RDS accepts only the app security group.
- Default AWS-managed encryption key is acceptable for MVP unless customer requirements demand a customer-managed KMS key.
- Basic CloudWatch alarms:
  - RDS CPU > 80%;
  - free storage low;
  - database connections > 80% of instance limit;
  - migration failures.

## IAM And Security

- Runtime role may read only the specific DB secret.
- No public DB access.
- Enforce TLS to database outside local/test.
- Store DB password only in the deployment secret store.
- Manual credential rotation is acceptable for MVP; automated rotation is deferred until there is a stable production environment.

## Migration Strategy

1. Add PostgreSQL backend behind a feature flag with SQLite unchanged locally.
2. Add dual test coverage.
3. Deploy staging with an empty PostgreSQL database.
4. Run all migrations in staging.
5. Run seed and gateway smoke tests.
6. For existing environments with SQLite data:
   - stop writes;
   - export SQLite tables to CSV/JSON;
   - import into PostgreSQL with deterministic IDs preserved;
   - run consistency checks per table;
   - start app against PostgreSQL.

## CI/CD Changes

- Add a CI service container for PostgreSQL.
- Add a matrix entry `database=sqlite|postgres`.
- Require PostgreSQL gateway tests before merge.
- Add a migration check job that applies all PostgreSQL migrations to an empty database and rolls back if down migrations remain supported.

## Rollout

1. Merge adapter and migration support with local SQLite default.
2. Enable PostgreSQL in staging.
3. Run live gateway smoke and load tests.
4. Enable PostgreSQL in production during a maintenance window or blue/green cutover.
5. Keep SQLite code for local/test until PostgreSQL local development is comfortable for contributors.

## Observability

Emit:

- DB pool active/idle/waiting connections.
- Transaction duration histogram.
- Migration version gauge.
- Gateway action state transition counts.
- Database error counts by SQLSTATE.
- Long transaction warnings over 500 ms.

## Validation

- Unit tests for backend factory and production setting rejection.
- Migration tests for empty and seeded PostgreSQL.
- Concurrency test proving a slow upstream call does not block unrelated DB writes.
- Multi-worker test with at least 4 workers sharing PostgreSQL.
- Manual command:

```bash
cd packages/product-platform
docker compose -f docker-compose.postgres.yml up -d
OPHANIX_DATABASE_URL=postgresql://ophanix:ophanix_local_password@127.0.0.1:55432/ophanix_product \
  PYTHONPATH=src python3 -m pytest tests/test_db_backend_postgres.py tests/test_tool_gateway_*.py -q
```

## Rollback

- Code rollback: redeploy prior application version.
- Data rollback: restore latest RDS snapshot or point-in-time recovery.
- If staging cutover fails before production, keep SQLite local/test unchanged and disable production deployment.
- Do not automatically migrate PostgreSQL data back to SQLite.

## Acceptance Criteria

- Non-local startup fails for any SQLite URL.
- Product-platform runs all gateway tests against PostgreSQL.
- Multi-worker gateway instances share state through PostgreSQL.
- No upstream network call occurs inside a database transaction.
- DB metrics are visible in CloudWatch or the existing deployment dashboard.
- Deployment docs describe provisioning, migration, backup, restore, and rollback.
