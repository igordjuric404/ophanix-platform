# Cloud Backup And Restore Runbook

## Backup Defaults

- Product database: PostgreSQL.
- Database backup schedule: hourly for 24 hours, daily for 14 days.
- Object storage versioning: enabled for artifact buckets.
- Secret manager replication: provider managed regional replication.

## Restore Drill

1. Provision an isolated staging PostgreSQL database.
2. Restore the latest production-like PostgreSQL backup into staging.
3. Run `python3 -m product_platform.cli db migrate`.
4. Start API and worker images against the restored database.
5. Confirm `/ready` is healthy.
6. Run a reduced Demo Lab scenario.
7. Record restore duration and any failed checks.

## Acceptance

- Restore drill is run before pilot launch and after schema-changing releases.
- Restored staging data must pass smoke demo and readiness checks.
