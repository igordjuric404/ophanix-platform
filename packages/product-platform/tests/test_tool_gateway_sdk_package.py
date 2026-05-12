from __future__ import annotations

import os
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path


class ToolGatewaySdkPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.product_platform_root = Path(__file__).resolve().parents[1]
        self.packages_root = self.product_platform_root.parent
        self.standalone_root = self.packages_root / "ophanix-tool-gateway-sdk"
        self.standalone_src = self.standalone_root / "src"

    def test_standalone_package_contains_sdk_source(self) -> None:
        package_root = self.standalone_src / "ophanix_tool_gateway"

        self.assertTrue(package_root.exists())
        self.assertTrue((package_root / "__init__.py").exists())
        self.assertTrue((package_root / "sdk.py").exists())
        self.assertTrue((package_root / "py.typed").exists())

    def test_product_platform_sdk_copy_matches_standalone_source(self) -> None:
        standalone_package = self.standalone_src / "ophanix_tool_gateway"
        product_package = self.product_platform_root / "src" / "ophanix_tool_gateway"

        for relative_path in ["__init__.py", "sdk.py", "py.typed"]:
            self.assertEqual(
                (product_package / relative_path).read_bytes(),
                (standalone_package / relative_path).read_bytes(),
                relative_path,
            )

    def test_product_wheel_depends_on_sdk_instead_of_shipping_duplicate_top_level_package(self) -> None:
        metadata = tomllib.loads((self.product_platform_root / "pyproject.toml").read_text())
        dependencies = metadata["project"]["dependencies"]
        wheel_packages = metadata["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]

        self.assertIn("src/product_platform", wheel_packages)
        self.assertNotIn("src/ophanix_tool_gateway", wheel_packages)
        self.assertTrue(
            any(dependency.startswith("ophanix-tool-gateway-sdk") for dependency in dependencies)
        )

    def test_standalone_package_imports_from_its_src_layout(self) -> None:
        env = {**os.environ, "PYTHONPATH": str(self.standalone_src)}
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from ophanix_tool_gateway import "
                    "AsyncOphanixToolGatewayClient, OphanixToolGatewayClient; "
                    "print(AsyncOphanixToolGatewayClient.__name__, "
                    "OphanixToolGatewayClient.__name__)"
                ),
            ],
            cwd=self.standalone_root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.stdout.strip(),
            "AsyncOphanixToolGatewayClient OphanixToolGatewayClient",
        )

    def test_product_compatibility_exports_include_validation_and_config_types(self) -> None:
        from product_platform.tool_gateway import (
            GatewayCompatibility,
            ToolGatewayClientConfig,
            ToolGatewayClientOptions,
            ToolGatewayValidationError,
        )
        from product_platform.tool_gateway.sdk import (
            GatewayCompatibility as ShimGatewayCompatibility,
            ToolGatewayClientConfig as ShimToolGatewayClientConfig,
            ToolGatewayClientOptions as ShimToolGatewayClientOptions,
            ToolGatewayValidationError as ShimToolGatewayValidationError,
        )

        self.assertIs(GatewayCompatibility, ShimGatewayCompatibility)
        self.assertIs(ToolGatewayClientConfig, ShimToolGatewayClientConfig)
        self.assertIs(ToolGatewayClientOptions, ShimToolGatewayClientOptions)
        self.assertIs(ToolGatewayClientOptions, ToolGatewayClientConfig)
        self.assertIs(ToolGatewayValidationError, ShimToolGatewayValidationError)

    def test_cloud_dockerfiles_install_local_tool_gateway_sdk_before_product_platform(self) -> None:
        dockerfiles = [
            self.product_platform_root / "deploy" / "cloud" / "Dockerfile.api",
            self.product_platform_root / "deploy" / "cloud" / "Dockerfile.worker",
            self.product_platform_root / "Dockerfile.demo",
        ]

        for dockerfile in dockerfiles:
            with self.subTest(dockerfile=dockerfile.name):
                contents = dockerfile.read_text()
                self.assertIn("packages/ophanix-tool-gateway-sdk", contents)
                self.assertLess(
                    contents.index("./packages/ophanix-tool-gateway-sdk"),
                    contents.index("./packages/product-platform"),
                    "Docker images must install the local SDK package before product-platform.",
                )


if __name__ == "__main__":
    unittest.main()
