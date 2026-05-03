from __future__ import annotations

import os
import subprocess
import sys
import tomllib
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
        self.assertIn("COPY packages/agent-mesh/pyproject.toml", api)
        self.assertIn("python -m pip install ./packages/agent-mesh", api)
        self.assertIn("COPY packages/agent-discovery/pyproject.toml", api)
        self.assertIn("python -m pip install ./packages/agent-discovery", api)
        self.assertIn('CMD ["serve", "--host", "0.0.0.0", "--port", "8088"]', api)
        self.assertIn("/ready", api)
        self.assertIn("COPY packages/agent-mesh/pyproject.toml", worker)
        self.assertIn("python -m pip install ./packages/agent-mesh", worker)
        self.assertIn("COPY packages/agent-discovery/pyproject.toml", worker)
        self.assertIn("python -m pip install ./packages/agent-discovery", worker)
        self.assertIn('CMD ["worker", "loop", "--interval-seconds", "10"]', worker)
        self.assertIn("worker noop", worker)

    def test_image_build_workflow_targets_frontend_api_and_worker(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/product-platform-images.yml").read_text()

        self.assertIn("Dockerfile.frontend", workflow)
        self.assertIn("Dockerfile.api", workflow)
        self.assertIn("Dockerfile.worker", workflow)
        self.assertIn("docker/build-push-action", workflow)

    def test_production_package_installs_email_validation_dependency(self) -> None:
        pyproject = tomllib.loads((PACKAGE_DIR / "pyproject.toml").read_text())

        dependencies = pyproject["project"]["dependencies"]
        self.assertIn("agent-discovery>=0.1.0,<1.0", dependencies)
        self.assertIn("agentmesh-platform>=3.1.0,<4.0", dependencies)
        self.assertIn("pydantic[email]>=2.4.0,<3.0", dependencies)

    def test_image_smoke_script_builds_and_runs_expected_targets(self) -> None:
        script = (PACKAGE_DIR / "deploy/cloud/smoke-images.sh").read_text()

        self.assertIn('REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../../../.." && pwd)"', script)
        self.assertIn("docker build -f \"$SCRIPT_DIR/Dockerfile.api\"", script)
        self.assertIn("docker build -f \"$SCRIPT_DIR/Dockerfile.worker\"", script)
        self.assertIn("docker build -f \"$SCRIPT_DIR/Dockerfile.frontend\"", script)
        self.assertIn("-t \"$API_IMAGE\" \"$REPO_ROOT\"", script)
        self.assertIn("-t \"$WORKER_IMAGE\" \"$REPO_ROOT\"", script)
        self.assertIn("-t \"$FRONTEND_IMAGE\" \"$REPO_ROOT\"", script)
        self.assertIn("/health", script)
        self.assertIn("/ready", script)
        self.assertIn("worker noop", script)

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
