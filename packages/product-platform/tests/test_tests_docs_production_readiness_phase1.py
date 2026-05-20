from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
IMAGE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "product-platform-images.yml"
POSTGRES_URL = "postgresql://ophanix:ophanix-local@127.0.0.1:5432/ophanix_product"


class TestsDocsProductionReadinessPhase1Tests(unittest.TestCase):
    def test_ci_product_platform_backend_with_postgres(self) -> None:
        workflow = CI_WORKFLOW.read_text()

        self.assertIn("product-platform: ${{ steps.filter.outputs.product-platform }}", workflow)
        self.assertIn("product-platform-backend-postgres:", workflow)
        self.assertIn("image: postgres:16-alpine", workflow)
        self.assertIn(f"OPHANIX_DATABASE_URL: {POSTGRES_URL}", workflow)
        self.assertIn(f"OPHANIX_TEST_POSTGRES_URL: {POSTGRES_URL}", workflow)
        self.assertIn("python -m product_platform.cli db migrate", workflow)
        self.assertIn("pytest tests/ -q --tb=short", workflow)
        self.assertIn(
            "product-platform-backend-postgres",
            workflow.split("ci-complete:", maxsplit=1)[1],
        )

    def test_ci_product_frontend_validate_and_playwright(self) -> None:
        workflow = CI_WORKFLOW.read_text()

        self.assertIn(
            "product-platform-frontend: "
            "${{ steps.filter.outputs.product-platform-frontend }}",
            workflow,
        )
        self.assertIn("packages/product-platform/frontend/**", workflow)
        self.assertIn("product-platform-frontend:", workflow)
        self.assertIn(
            "cache-dependency-path: packages/product-platform/frontend/package-lock.json",
            workflow,
        )
        self.assertIn("npm ci", workflow)
        self.assertIn("npm run lint", workflow)
        self.assertIn("npm run typecheck", workflow)
        self.assertIn("npm test", workflow)
        self.assertIn("npx playwright install --with-deps chromium", workflow)
        self.assertIn("npm run test:e2e -- --project=chromium", workflow)
        self.assertIn("npm run build", workflow)
        self.assertIn(
            "product-platform-frontend",
            workflow.split("ci-complete:", maxsplit=1)[1],
        )

    def test_product_platform_images_use_provenance_and_smoke_checks(self) -> None:
        workflow = IMAGE_WORKFLOW.read_text()

        self.assertIn("id-token: write", workflow)
        self.assertIn("attestations: write", workflow)
        self.assertIn("provenance: true", workflow)
        self.assertIn("Smoke product platform images", workflow)
        self.assertIn("packages/product-platform/deploy/cloud/smoke-images.sh", workflow)


if __name__ == "__main__":
    unittest.main()
