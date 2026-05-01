from __future__ import annotations

import unittest
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parents[1]


class MVPCloudDeploymentPhase5Tests(unittest.TestCase):
    def test_pilot_readiness_covers_provisioning_support_retention_and_rollback(self) -> None:
        checklist = (PACKAGE_DIR / "deploy/cloud/PILOT_READINESS.md").read_text()

        for required in (
            "Tenant Provisioning",
            "IdP groups",
            "Smoke Demo",
            "Break-Glass",
            "Audit events: 1 year",
            "Demo run history: 90 days",
            "Rollback Procedure",
            "Rollback Drill",
            "customer-support refund scenario",
        ):
            self.assertIn(required, checklist)


if __name__ == "__main__":
    unittest.main()
