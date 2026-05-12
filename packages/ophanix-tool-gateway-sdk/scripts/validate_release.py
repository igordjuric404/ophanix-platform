# SPDX-License-Identifier: MIT
"""Validate standalone SDK release artifacts before publishing."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path


EXPECTED_PACKAGE_FILES = (
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
)
GENERATED_ARTIFACT_NAMES = {
    "ophanix-tool-gateway-sdk.cdx.json",
    "release-manifest.json",
}
GENERATED_ARTIFACT_PATTERNS = (
    re.compile(r"^ophanix_tool_gateway_sdk-[^-]+-(?:py3-none-any\.whl|.+\.tar\.gz)$"),
    re.compile(r"^ophanix_tool_gateway_sdk-[^-]+\.tar\.gz$"),
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
    parser.add_argument(
        "--require-dependency-audit",
        action="store_true",
        help="Run pip-audit after artifact validation. Install .[security] first.",
    )
    parser.add_argument(
        "--strict-git",
        action="store_true",
        help="Require a clean SDK git state and a tag matching the package version.",
    )
    parser.add_argument(
        "--expected-tag",
        help="Expected release tag. Defaults to v<project.version> when --strict-git is used.",
    )
    parser.add_argument(
        "--verify-index-install",
        action="store_true",
        help="After artifact validation, install the exact package version from the configured package index.",
    )
    parser.add_argument(
        "--index-url",
        help="Package index URL used with --verify-index-install. Defaults to pip's configured index.",
    )
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    _validate_vendored_sdk_parity(package_root)
    if args.strict_git:
        _validate_git_state(package_root, expected_tag=args.expected_tag)
    if args.skip_twine_check:
        print("WARNING: twine metadata validation skipped; release-manifest.json records this.")
    with _artifact_directory(args.out_dir) as artifact_dir:
        _run_build(package_root, artifact_dir)
        wheel = _single_artifact(artifact_dir, "*.whl")
        sdist = _single_artifact(artifact_dir, "*.tar.gz")
        _validate_wheel(wheel)
        _validate_sdist(sdist)
        _validate_installed_wheel(wheel)
        if not args.skip_twine_check:
            _run_module(
                "twine",
                ["check", str(wheel), str(sdist)],
                package_root,
                missing_hint="Install release extras first: python3 -m pip install '.[release]'",
            )
        if args.require_dependency_audit:
            _validate_runtime_dependency_audit(wheel)
        sbom = _write_minimal_sbom(artifact_dir, package_root=package_root, wheel=wheel, artifacts=[wheel, sdist])
        _write_release_manifest(
            artifact_dir,
            package_root=package_root,
            artifacts=[wheel, sdist],
            sbom=sbom,
            dependency_audit_required=args.require_dependency_audit,
            strict_git=args.strict_git,
            twine_check_skipped=args.skip_twine_check,
        )
        if args.verify_index_install:
            _validate_index_install(package_root, index_url=args.index_url)
        print(f"Release artifacts validated in {artifact_dir}")
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
                _clean_artifact_directory(self.path)
            else:
                self.path.mkdir(parents=True)
            return self.path
        self._temporary = tempfile.TemporaryDirectory(prefix="ophanix-sdk-release-")
        self.path = Path(self._temporary.name)
        return self.path

    def __exit__(self, *_exc_info: object) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()


def _run_build(package_root: Path, artifact_dir: Path) -> None:
    _run_module(
        "build",
        ["--sdist", "--wheel", "--outdir", str(artifact_dir)],
        package_root,
        missing_hint="Install release extras first: python3 -m pip install '.[release]'",
    )


def _validate_git_state(package_root: Path, *, expected_tag: str | None) -> None:
    repo_root = package_root.parents[1]
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", str(package_root.relative_to(repo_root))],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if status.returncode != 0:
        raise SystemExit((status.stdout + status.stderr).strip() or "git status failed")
    if status.stdout.strip():
        raise SystemExit("SDK release validation requires a clean SDK package worktree.")
    version_value = _project_version(package_root)
    expected = expected_tag or f"v{version_value}"
    if not _tag_matches_version(expected, version_value):
        raise SystemExit(
            f"Expected release tag {expected!r} must include package version {version_value!r}."
        )
    tag = subprocess.run(
        ["git", "describe", "--tags", "--exact-match"],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )
    if tag.returncode != 0 or tag.stdout.strip() != expected:
        raise SystemExit(f"SDK release must be built from tag {expected}.")


def _tag_matches_version(tag: str, version: str) -> bool:
    return tag == f"v{version}" or tag.endswith(f"-v{version}") or tag.endswith(f"/v{version}")


def _clean_artifact_directory(path: Path) -> None:
    if not path.is_dir():
        raise SystemExit(f"Artifact output path exists but is not a directory: {path}")
    children = sorted(path.iterdir())
    unexpected = [child.name for child in children if not _is_generated_artifact(child)]
    if unexpected:
        raise SystemExit(
            "Artifact output directory contains non-release files; choose an empty directory "
            f"or remove: {', '.join(unexpected[:10])}"
        )
    for child in children:
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _is_generated_artifact(path: Path) -> bool:
    return path.is_file() and (
        path.name in GENERATED_ARTIFACT_NAMES
        or any(pattern.fullmatch(path.name) for pattern in GENERATED_ARTIFACT_PATTERNS)
    )


def _project_version(package_root: Path) -> str:
    with (package_root / "pyproject.toml").open("rb") as handle:
        metadata = tomllib.load(handle)
    version_value = metadata.get("project", {}).get("version")
    if not isinstance(version_value, str) or not version_value:
        raise SystemExit("pyproject.toml is missing project.version")
    return version_value


def _project_name(package_root: Path) -> str:
    with (package_root / "pyproject.toml").open("rb") as handle:
        metadata = tomllib.load(handle)
    name_value = metadata.get("project", {}).get("name")
    if not isinstance(name_value, str) or not name_value:
        raise SystemExit("pyproject.toml is missing project.name")
    return name_value


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
    for required in ["LICENSE", "CHANGELOG.md", "SECURITY.md", "MIGRATION.md"]:
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
            f"{artifact} contains forbidden generated/local files: {', '.join(sorted(forbidden)[:20])}"
        )


def _validate_installed_wheel(wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="ophanix-sdk-install-") as target:
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
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
                    "import ophanix_tool_gateway as sdk; "
                    "assert sdk.OphanixToolGatewayClient; "
                    "assert sdk.ToolAuthenticationError"
                ),
            ],
            cwd=wheel.parent,
        )


def _validate_vendored_sdk_parity(package_root: Path) -> None:
    repo_root = package_root.parents[1]
    standalone_root = package_root / "src"
    vendored_root = repo_root / "packages" / "product-platform" / "src"
    mismatches: list[str] = []
    missing: list[str] = []
    for relative_path in EXPECTED_PACKAGE_FILES:
        standalone = standalone_root / relative_path
        vendored = vendored_root / relative_path
        if not standalone.exists() or not vendored.exists():
            missing.append(relative_path)
            continue
        if standalone.read_bytes() != vendored.read_bytes():
            mismatches.append(relative_path)
    if missing:
        raise SystemExit(
            "Standalone SDK or product-platform vendored copy is missing: "
            + ", ".join(sorted(missing))
        )
    if mismatches:
        raise SystemExit(
            "Standalone SDK and product-platform vendored SDK package differ; sync: "
            + ", ".join(sorted(mismatches))
        )


def _validate_index_install(package_root: Path, *, index_url: str | None) -> None:
    with tempfile.TemporaryDirectory(prefix="ophanix-sdk-index-install-") as target:
        requirement = f"{_project_name(package_root)}=={_project_version(package_root)}"
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--target",
            target,
            requirement,
        ]
        if index_url:
            command.extend(["--index-url", index_url])
        _run(command, cwd=package_root)
        _run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; "
                    f"sys.path.insert(0, {target!r}); "
                    "import ophanix_tool_gateway as sdk; "
                    f"assert sdk.__version__ == {_project_version(package_root)!r}; "
                    "assert sdk.OphanixToolGatewayClient"
                ),
            ],
            cwd=package_root,
        )


def _validate_runtime_dependency_audit(wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="ophanix-sdk-audit-") as target:
        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                target,
                str(wheel),
            ],
            cwd=wheel.parent,
        )
        _run_module(
            "pip_audit",
            ["--progress-spinner", "off", "--path", target],
            wheel.parent,
            missing_hint="Install security extras first: python3 -m pip install '.[security]'",
        )


def _write_release_manifest(
    artifact_dir: Path,
    *,
    package_root: Path,
    artifacts: list[Path],
    sbom: Path,
    dependency_audit_required: bool,
    strict_git: bool,
    twine_check_skipped: bool,
) -> None:
    manifest = {
        "package": "ophanix-tool-gateway-sdk",
        "version": _project_version(package_root),
        "dependency_audit_required": dependency_audit_required,
        "sbom_provenance": {
            "included": True,
            "sbom_file": sbom.name,
            "sbom_sha256": _sha256_file(sbom),
            "provenance_requirement": (
                "GitHub publish workflow signs artifacts and attests provenance before external release."
            ),
        },
        "strict_git": strict_git,
        "twine_check_skipped": twine_check_skipped,
        "artifacts": [
            {
                "filename": artifact.name,
                "sha256": _sha256_file(artifact),
                "size_bytes": artifact.stat().st_size,
            }
            for artifact in artifacts
        ],
    }
    (artifact_dir / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_minimal_sbom(
    artifact_dir: Path,
    *,
    package_root: Path,
    wheel: Path,
    artifacts: list[Path],
) -> Path:
    dependencies = _wheel_requires_dist(wheel)
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "library",
                "name": "ophanix-tool-gateway-sdk",
                "version": _project_version(package_root),
            },
            "tools": [{"name": "scripts/validate_release.py", "version": "1"}],
        },
        "components": [
            {
                "type": "file",
                "name": artifact.name,
                "hashes": [{"alg": "SHA-256", "content": _sha256_file(artifact)}],
            }
            for artifact in artifacts
        ]
        + [
            {
                "type": "library",
                "name": dependency,
            }
            for dependency in dependencies
        ],
    }
    path = artifact_dir / "ophanix-tool-gateway-sdk.cdx.json"
    path.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wheel_requires_dist(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            (name for name in archive.namelist() if name.endswith(".dist-info/METADATA")),
            None,
        )
        if metadata_name is None:
            raise SystemExit("Wheel is missing METADATA")
        metadata = archive.read(metadata_name).decode("utf-8", errors="replace")
    dependencies: list[str] = []
    for line in metadata.splitlines():
        if not line.startswith("Requires-Dist:"):
            continue
        raw = line.partition(":")[2].strip()
        if ";" in raw and "extra ==" in raw.split(";", 1)[1].lower():
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)", raw)
        if match:
            dependencies.append(match.group(1))
    return sorted(set(dependencies), key=str.lower)


def _run(command: list[str], *, cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise SystemExit((result.stdout + result.stderr).strip())


if __name__ == "__main__":
    raise SystemExit(main())
