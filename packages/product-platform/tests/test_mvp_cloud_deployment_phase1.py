from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = REPO_ROOT / "packages" / "product-platform"


class MVPCloudDeploymentPhase1Tests(unittest.TestCase):
    def test_production_dockerfiles_define_expected_entrypoints_and_healthchecks(self) -> None:
        frontend = (PACKAGE_DIR / "deploy/cloud/Dockerfile.frontend").read_text()
        api = (PACKAGE_DIR / "deploy/cloud/Dockerfile.api").read_text()
        worker = (PACKAGE_DIR / "deploy/cloud/Dockerfile.worker").read_text()

        self.assertIn("FROM nginx:1.27-alpine", frontend)
        self.assertIn("HEALTHCHECK", frontend)
        self.assertIn("FROM python:3.11-slim", api)
        self.assertIn('CMD ["serve", "--host", "0.0.0.0", "--port", "8088"]', api)
        self.assertIn("/ready", api)
        self.assertIn('CMD ["worker", "loop", "--interval-seconds", "10"]', worker)
        self.assertIn("worker noop", worker)

    def test_image_build_workflow_targets_frontend_api_and_worker(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/product-platform-images.yml").read_text()

        self.assertIn("Dockerfile.frontend", workflow)
        self.assertIn("Dockerfile.api", workflow)
        self.assertIn("Dockerfile.worker", workflow)
        self.assertIn("docker/build-push-action", workflow)

    def test_worker_image_smoke_command_executes_noop_job(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PACKAGE_DIR / "src")
        result = subprocess.run(
            [sys.executable, "-m", "product_platform.cli", "worker", "noop"],
            cwd=PACKAGE_DIR,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Worker no-op job succeeded: True", result.stdout)


if __name__ == "__main__":
    unittest.main()
