from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path


class TestsDocsProductionReadinessPhase5Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.product_platform_root = Path(__file__).resolve().parents[1]
        self.platform_root = Path(__file__).resolve().parents[3]
        self.workspace_root = Path(__file__).resolve().parents[4]
        self.internal_sdk_root = self.platform_root / "packages" / "ophanix-tool-gateway-sdk"
        self.standalone_sdk_root = self.workspace_root / "ophanix-python-sdk"

    def test_sdk_package_metadata_docs_consistency(self) -> None:
        product_readme = self._read(self.product_platform_root / "README.md")
        internal_readme = self._read(self.internal_sdk_root / "README.md")
        standalone_readme = self._read(self.standalone_sdk_root / "README.md")
        internal_metadata = self._pyproject(self.internal_sdk_root)
        standalone_metadata = self._pyproject(self.standalone_sdk_root)

        self.assertEqual(standalone_metadata["project"]["name"], "ophanix-python-sdk")
        self.assertEqual(internal_metadata["project"]["name"], "ophanix-tool-gateway-sdk")
        self.assertIn("canonical external", product_readme)
        self.assertIn("pip install ophanix-python-sdk", product_readme)
        self.assertIn("stable Tool Gateway import path is\n`ophanix_tool_gateway`", product_readme)
        self.assertIn("internal compatibility package named\n`ophanix-tool-gateway-sdk`", internal_readme)
        self.assertIn("canonical public Python distribution is\n`ophanix-python-sdk`", internal_readme)
        self.assertIn("Install the public SDK with", internal_readme)
        self.assertIn("distribution is named `ophanix-python-sdk`", standalone_readme)
        self.assertIn("stable import path\nfor the Tool Gateway client remains `ophanix_tool_gateway`", standalone_readme)
        self.assertIn("test_standalone_sdk_live_gateway_contract", standalone_readme)

    def test_product_platform_readme_sdk_example_smoke(self) -> None:
        product_readme = self._read(self.product_platform_root / "README.md")
        sdk_section = product_readme.split("## Tool Gateway Python SDK", maxsplit=1)[1]
        python_block = re.search(r"```python\n(?P<code>.*?)\n```", sdk_section, re.DOTALL)
        self.assertIsNotNone(python_block)
        code = python_block.group("code")

        compile(code, "packages/product-platform/README.md#tool-gateway-python-sdk", "exec")
        self.assertIn("OphanixToolGatewayClient.from_env()", code)
        self.assertIn("client.check_compatibility()", code)
        self.assertIn("client.list_all_tools()", code)
        self.assertIn('client.call_tool("claims.lookup", {"claim_id": "claim_123"})', code)
        self.assertIn("ToolDeniedError", code)

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _pyproject(self, package_root: Path) -> dict:
        with (package_root / "pyproject.toml").open("rb") as handle:
            return tomllib.load(handle)


if __name__ == "__main__":
    unittest.main()
