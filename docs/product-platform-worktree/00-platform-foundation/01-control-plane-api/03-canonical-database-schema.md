# Canonical Database Schema

## Feature Scope

Create the product database foundation: migration tooling, connection management, transaction conventions, base tables, and repository patterns. This feature does not build feature-specific behavior, but it creates the schemas required for later plans.

## Existing Repo Assets To Reuse

- Generic storage concepts from `packages/agent-mesh/src/agentmesh/storage/provider.py`.
- PostgreSQL storage provider ideas from `packages/agent-mesh/src/agentmesh/storage/postgres_provider.py`.

## Out Of Scope

- Replacing existing package-local storage abstractions.
- Full ORM models for every feature in one change. Add feature tables incrementally.

## Data Model

Base tables:

- `schema_migrations`.
- `organizations`.
- `environments`.
- `users`.
- `organization_memberships`.
- `audit_events`.
- `workflow_runs`.

Common columns:

- `id`.
- `organization_id`.
- `environment_id` when applicable.
- `created_at`.
- `updated_at`.
- `deleted_at` for soft deletes where needed.

## API Surface

No public API required. Internal repository and migration commands only.

## UI Surface

No UI required.

## Implementation Phases

### Phase 1: Migration Tooling

Steps:

1. Choose migration tool, preferably Alembic if using SQLAlchemy.
2. Add database URL settings.
3. Add first migration creating base auth and environment tables.
4. Add local migration command documented in the service README.

Tests:

- Test migration applies to empty database.
- Test migration can be rolled back where supported.
- Test local test database can be created and migrated automatically.

### Phase 2: Connection And Transaction Layer

Steps:

1. Add database connection pool.
2. Add request-scoped transaction dependency.
3. Add repository base class with organization scoping helpers.
4. Add integration test fixture for database cleanup.

Tests:

- Unit test repository scope helper applies organization id.
- Integration test writes and reads an organization.
- Integration test verifies transaction rollback on exception.

### Phase 3: ID, Time, And Soft Delete Conventions

Steps:

1. Standardize ID generation.
2. Standardize UTC timestamp handling.
3. Add soft-delete helpers where resources need recovery.
4. Add unique indexes for slugs and natural identifiers.

Tests:

- Unit test ID generation format.
- Integration test unique constraints.
- Integration test soft-deleted row is excluded by default query helper.

### Phase 4: Seed Data Support

Steps:

1. Add seed command for local demo organization, environment, admin user, and policy placeholders.
2. Ensure seed command is idempotent.
3. Add reset mode for demo-only resources.

Tests:

- Run seed twice and verify no duplicates.
- Verify seeded organization and environment are available through repositories.
- Verify reset does not remove admin user unless explicitly requested.

## Overall Validation

- Fresh database can migrate and seed from scratch.
- Test suite can run with isolated database state.
- Later feature plans can add tables without redefining database conventions.

## Dependencies

- PostgreSQL.
- Migration tool.
- Product API settings.

## Definition Of Done

- Database lifecycle is reproducible.
- Base tables and repository conventions are documented.
- Integration tests prove migrations and transactions work.
