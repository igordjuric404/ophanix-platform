"""Manual discovery scan execution."""

from __future__ import annotations

import json
from product_platform.db.postgres import Row
from typing import Any

from product_platform.discovery.repository import (
    DiscoveryRepository,
    DiscoveryTargetNotFoundError,
)


class DiscoveryScanRunner:
    """Invoke registered scanners and persist their raw output."""

    def __init__(self, repository: DiscoveryRepository) -> None:
        self.repository = repository

    async def run_target(self, target_id: str) -> Row:
        """Run one target synchronously and persist terminal state."""

        target = self.repository.get_target(target_id)
        if target is None:
            raise DiscoveryTargetNotFoundError("Discovery target not found.")
        run = self.repository.create_run(target)
        return await self.run_created_target(target, run)

    async def run_created_target(self, target: Row, run: Row) -> Row:
        """Run a target that already has a persisted running record."""

        if run["status"] != "running":
            return run
        if not bool(target["enabled"]):
            raise ValueError("Discovery target is disabled.")
        if self.repository.has_running_run_for_target(
            target["id"],
            exclude_run_id=run["id"],
        ):
            return self.repository.mark_run_skipped(
                run["id"],
                reason="A discovery scan is already running for this target.",
            )

        config = json.loads(target["config_json"])
        errors = self.repository.scanner_registry.validate_config(target["scanner_type"], config)
        if errors:
            return self.repository.mark_run_failed(
                run["id"],
                error_message="; ".join(errors),
                summary={"raw_finding_count": 0, "scanner_errors": errors},
            )

        scanner = self.repository.scanner_registry.scanner_registry.get(target["scanner_type"])
        if scanner is None:
            return self.repository.mark_run_failed(
                run["id"],
                error_message=f"Unknown scanner type: {target['scanner_type']}",
                summary={
                    "raw_finding_count": 0,
                    "scanner_errors": [f"Unknown scanner type: {target['scanner_type']}"],
                },
            )

        try:
            result = await scanner.scan(**config)
        except Exception as exc:
            return self.repository.mark_run_failed(
                run["id"],
                error_message=str(exc),
                summary={"raw_finding_count": 0, "scanner_errors": [str(exc)]},
            )

        raw_findings = [agent.model_dump(mode="json") for agent in result.agents]
        self.repository.persist_raw_findings(run["id"], raw_findings)
        summary: dict[str, Any] = {
            "raw_finding_count": len(raw_findings),
            "scanner_name": result.scanner_name,
            "scanned_targets": result.scanned_targets,
            "scanner_errors": list(result.errors),
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat()
            if result.completed_at is not None
            else None,
        }
        if result.errors:
            return self.repository.mark_run_failed(
                run["id"],
                error_message="; ".join(result.errors),
                summary=summary,
            )
        return self.repository.mark_run_succeeded(run["id"], summary=summary)
