# Pilot Readiness Checklist

## Tenant Provisioning

1. Create the pilot organization and default staging environment.
2. Assign IdP groups to `Platform Admin`, `Operator`, and `Viewer` roles.
3. Run `python -m product_platform.cli db migrate`.
4. Run `python -m product_platform.cli db seed` for demo fixtures.
5. Confirm `/ready` is healthy.

## Smoke Demo

1. Log in through the configured IdP test user.
2. Open Demo Lab.
3. Confirm baseline status is healthy or only optional provider credentials are warning.
4. Run the customer-support refund scenario through completion.
5. Reset Demo Lab and confirm the baseline returns to healthy.

## Support And Break-Glass

- Break-glass access requires an approved incident ticket.
- Support access is time-boxed to 4 hours.
- All support actions must include a correlation ID and audit entry.
- Disable break-glass credentials after the incident is resolved.

## Retention Defaults

- Audit events: 1 year.
- Demo run history: 90 days.
- Application logs: 30 days.
- Backups: hourly for 24 hours, daily for 14 days.
- Exported pilot artifacts: 90 days unless the customer contract requires longer.

## Rollback Procedure

1. Freeze new deploys.
2. Capture current image tags and migration version.
3. Restore the previous API, worker, and frontend image tags.
4. If schema rollback is required, restore the latest verified backup into staging first.
5. Run `/ready` and the smoke demo.
6. Record rollback duration, owner, and customer impact.

## Rollback Drill

Run one rollback drill before pilot launch and after each schema-changing release.
The drill passes only when readiness, login, smoke demo, and retention checks pass.
