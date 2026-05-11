# SPDX-License-Identifier: MIT
"""Validate product-platform release artifacts before publishing."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


EXPECTED_PACKAGE_FILES = (
    "product_platform/__init__.py",
    "product_platform/cli.py",
    "product_platform/py.typed",
    "ophanix_tool_gateway/__init__.py",
    "ophanix_tool_gateway/sdk.py",
    "ophanix_tool_gateway/py.typed",
)
FORBIDDEN_ARTIFACT_MARKERS = (
    ".db",
    ".sqlite",
    "__pycache__",
    ".pyc",
    "node_modules/",
    "frontend/dist/",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Directory for generated artifacts. Defaults to a temporary directory.",
    )
    parser.add_argument(
        "--skip-twine-check",
        action="store_true",
        help="Skip metadata validation with twine.",
    )
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    with _artifact_directory(args.out_dir) as artifact_dir:
        _run_module(
            "build",
            ["--sdist", "--wheel", "--outdir", str(artifact_dir)],
            package_root,
            missing_hint="Install release extras first: python3 -m pip install '.[release]'",
        )
        wheel = _single_artifact(artifact_dir, "*.whl")
        sdist = _single_artifact(artifact_dir, "*.tar.gz")
        _validate_wheel(wheel)
        _validate_sdist(sdist)
        _validate_installed_wheel_import(wheel)
        if not args.skip_twine_check:
            _run_module(
                "twine",
                ["check", str(wheel), str(sdist)],
                package_root,
                missing_hint="Install release extras first: python3 -m pip install '.[release]'",
            )
        print(f"Product release artifacts validated in {artifact_dir}")
    return 0


class _artifact_directory:
    def __init__(self, requested: Path | None) -> None:
        self.requested = requested
        self.path: Path | None = None
        self._temporary: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> Path:
        if self.requested is not None:
            self.path = self.requested.resolve()
            if self.path.exists():
                shutil.rmtree(self.path)
            self.path.mkdir(parents=True)
            return self.path
        self._temporary = tempfile.TemporaryDirectory(prefix="ophanix-product-release-")
        self.path = Path(self._temporary.name)
        return self.path

    def __exit__(self, *_exc_info: object) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()


def _single_artifact(artifact_dir: Path, pattern: str) -> Path:
    matches = sorted(artifact_dir.glob(pattern))
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one {pattern} artifact, found {len(matches)}")
    return matches[0]


def _validate_wheel(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    missing = [path for path in EXPECTED_PACKAGE_FILES if path not in names]
    if missing:
        raise SystemExit(f"Wheel is missing expected files: {', '.join(missing)}")
    _validate_archive_names(names, artifact="Wheel")
    if not any(name.endswith("LICENSE") for name in names):
        raise SystemExit("Wheel is missing a LICENSE file")
    if not any(name.endswith(".dist-info/METADATA") for name in names):
        raise SystemExit("Wheel is missing METADATA")


def _validate_sdist(sdist: Path) -> None:
    with tarfile.open(sdist, "r:gz") as archive:
        names = set(archive.getnames())
    missing = [
        f"src/{path}"
        for path in EXPECTED_PACKAGE_FILES
        if not any(name.endswith(f"/src/{path}") for name in names)
    ]
    if missing:
        raise SystemExit(f"Sdist is missing expected files: {', '.join(missing)}")
    _validate_archive_names(names, artifact="Sdist")
    for required in ["LICENSE", "README.md", "pyproject.toml"]:
        if not any(name.endswith(f"/{required}") for name in names):
            raise SystemExit(f"Sdist is missing {required}")


def _validate_archive_names(names: set[str], *, artifact: str) -> None:
    forbidden = [
        name
        for name in names
        if any(marker in name for marker in FORBIDDEN_ARTIFACT_MARKERS)
    ]
    if forbidden:
        raise SystemExit(
            f"{artifact} contains forbidden generated/local files: "
            f"{', '.join(sorted(forbidden)[:20])}"
        )


def _validate_installed_wheel_import(wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="ophanix-product-install-") as target:
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                target,
                str(wheel),
            ],
            cwd=wheel.parent,
        )
        _run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    f"sys.path.insert(0, {target!r}); "
                    "import product_platform; "
                    "import ophanix_tool_gateway; "
                    "assert product_platform.__version__; "
                    "assert ophanix_tool_gateway.OphanixToolGatewayClient"
                ),
            ],
            cwd=wheel.parent,
        )


def _run_module(module: str, args: list[str], cwd: Path, *, missing_hint: str) -> None:
    command = [sys.executable, "-m", module, *args]
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode == 0:
        if result.stdout:
            print(result.stdout, end="")
        return
    output = f"{result.stdout}{result.stderr}"
    if f"No module named {module}" in output:
        raise SystemExit(missing_hint)
    raise SystemExit(output.strip() or f"{' '.join(command)} failed")


def _run(command: list[str], *, cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise SystemExit((result.stdout + result.stderr).strip())


if __name__ == "__main__":
    raise SystemExit(main())
