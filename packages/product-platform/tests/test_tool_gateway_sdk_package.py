from __future__ import annotations

import os
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
