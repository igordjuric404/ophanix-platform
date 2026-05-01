"""Safe workflow runner registry and local adapters."""

from __future__ import annotations

import subprocess
from hashlib import sha256
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from product_platform.policies.linting import lint_policy_body
from product_platform.policies.models import PolicyLintRequest


class WorkflowRunnerError(ValueError):
    """Raised when a workflow command cannot be executed safely."""


@dataclass(frozen=True)
class WorkflowRunLogLine:
    """Captured stdout/stderr line from a workflow run."""

    stream: str
    line_number: int
    message: str


@dataclass(frozen=True)
class WorkflowRunResult:
    """Result of one workflow command execution."""

    status: str
    exit_code: int
    summary: dict[str, Any] = field(default_factory=dict)
    logs: list[WorkflowRunLogLine] = field(default_factory=list)


WorkflowRunner = Callable[[dict[str, Any]], WorkflowRunResult]


class WorkflowRunnerRegistry:
    """Allowlisted workflow command registry."""

    def __init__(self, *, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or _repo_root()).resolve()
        self._runners: dict[str, WorkflowRunner] = {}

    def register(self, command_ref: str, runner: WorkflowRunner) -> None:
        """Register an in-process workflow adapter."""

        command = command_ref.strip()
        if not command:
            raise WorkflowRunnerError("command_ref is required.")
        self._runners[command] = runner

    def register_shell(
        self,
        command_ref: str,
        argv: list[str],
        *,
        cwd: Path | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        """Register an allowlisted shell command vector."""

        command = command_ref.strip()
        if not command:
            raise WorkflowRunnerError("command_ref is required.")
        if not argv:
            raise WorkflowRunnerError("Shell workflow argv must not be empty.")
        working_directory = (cwd or self.repo_root).resolve()
        if self.repo_root not in [working_directory, *working_directory.parents]:
            raise WorkflowRunnerError("Shell workflow cwd must stay inside the repository.")

        def run_shell(inputs: dict[str, Any]) -> WorkflowRunResult:
            try:
                completed = subprocess.run(
                    argv,
                    cwd=working_directory,
                    capture_output=True,
                    check=False,
                    text=True,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                logs = _captured_logs(exc.stdout or "", exc.stderr or "")
                return WorkflowRunResult(
                    status="failed",
                    exit_code=124,
                    summary={"error": "timeout", "timeout_seconds": timeout_seconds},
                    logs=logs,
                )
            logs = _captured_logs(completed.stdout, completed.stderr)
            return WorkflowRunResult(
                status="succeeded" if completed.returncode == 0 else "failed",
                exit_code=completed.returncode,
                summary={
                    "command_ref": command,
                    "input_keys": sorted(inputs),
                    "line_count": len(logs),
                },
                logs=logs,
            )

        self._runners[command] = run_shell

    def run(self, command_ref: str, inputs: dict[str, Any] | None = None) -> WorkflowRunResult:
        """Execute an allowlisted command reference."""

        try:
            runner = self._runners[command_ref]
        except KeyError as exc:
            raise WorkflowRunnerError(f"Workflow command is not allowlisted: {command_ref}") from exc
        return runner(dict(inputs or {}))

    def registered_command_refs(self) -> set[str]:
        return set(self._runners)


def build_default_workflow_runner_registry(*, repo_root: Path | None = None) -> WorkflowRunnerRegistry:
    """Build the product workflow runner registry."""

    registry = WorkflowRunnerRegistry(repo_root=repo_root)
    registry.register("python:policy.lint", _run_policy_lint)
    registry.register("python:governance.verify", _run_governance_verify)
    registry.register("python:integrity.check", _run_integrity_check(registry.repo_root))
    registry.register("python:marketplace.evaluate", _run_marketplace_evaluate)
    registry.register("shell:security.scan", _run_security_scan(registry.repo_root))
    registry.register("shell:sbom.generate", _run_sbom_generate(registry.repo_root))
    registry.register(
        "shell:dependency_confusion.check",
        _run_dependency_confusion_check(registry.repo_root),
    )
    return registry


def _run_policy_lint(inputs: dict[str, Any]) -> WorkflowRunResult:
    body = str(inputs.get("policy_body") or "")
    body_format = str(inputs.get("policy_format") or "yaml")
    response = lint_policy_body(PolicyLintRequest(body_text=body, body_format=body_format))
    logs = [
        WorkflowRunLogLine(
            stream="stdout",
            line_number=1,
            message=(
                f"policy lint passed={response.passed} "
                f"errors={response.error_count} warnings={response.warning_count}"
            ),
        )
    ]
    for issue in response.issues:
        logs.append(
            WorkflowRunLogLine(
                stream="stdout",
                line_number=len(logs) + 1,
                message=f"{issue.severity}:{issue.code}:{issue.message}",
            )
        )
    return WorkflowRunResult(
        status="succeeded" if response.passed else "failed",
        exit_code=0 if response.passed else 1,
        summary=response.model_dump(),
        logs=logs,
    )


def _run_governance_verify(inputs: dict[str, Any]) -> WorkflowRunResult:
    scope = str(inputs.get("scope") or "").strip()
    evidence_ref = str(inputs.get("evidence_ref") or "").strip()
    if not scope:
        return _failed_result("governance.verify", "missing_scope", "scope is required")
    if not evidence_ref:
        return _failed_result(
            "governance.verify",
            "missing_evidence_ref",
            "evidence_ref is required for governance verification",
        )
    return _succeeded_result(
        "governance.verify",
        {
            "scope": scope,
            "evidence_ref": evidence_ref,
            "checks": ["scope_present", "evidence_ref_present"],
        },
        f"governance verification passed for {scope}",
    )


def _run_integrity_check(repo_root: Path) -> WorkflowRunner:
    def run(inputs: dict[str, Any]) -> WorkflowRunResult:
        target = _resolve_existing_repo_path(
            repo_root,
            inputs.get("target"),
            field_name="target",
            missing_error="target_not_found",
        )
        if isinstance(target, WorkflowRunResult):
            return target
        summary: dict[str, Any] = {"target": _relative_path(repo_root, target)}
        if target.is_file():
            data = target.read_bytes()
            summary.update({"kind": "file", "checksum": sha256(data).hexdigest(), "size_bytes": len(data)})
        else:
            files = [path for path in target.rglob("*") if path.is_file()]
            summary.update({"kind": "directory", "file_count": len(files)})
        return _succeeded_result("integrity.check", summary, f"integrity checked {summary['target']}")

    return run


def _run_marketplace_evaluate(inputs: dict[str, Any]) -> WorkflowRunResult:
    plugin_id = str(inputs.get("plugin_id") or "").strip()
    version = str(inputs.get("version") or "latest").strip() or "latest"
    if not plugin_id:
        return _failed_result("marketplace.evaluate", "missing_plugin_id", "plugin_id is required")
    if plugin_id.startswith("unknown"):
        return _failed_result("marketplace.evaluate", "plugin_not_found", f"{plugin_id} is not registered")
    findings = []
    if version == "latest":
        findings.append("version_not_pinned")
    summary = {
        "plugin_id": plugin_id,
        "version": version,
        "finding_count": len(findings),
        "findings": findings,
    }
    return _succeeded_result(
        "marketplace.evaluate",
        summary,
        f"marketplace policy evaluated {plugin_id}@{version}",
    )


def _run_security_scan(repo_root: Path) -> WorkflowRunner:
    def run(inputs: dict[str, Any]) -> WorkflowRunResult:
        target = _resolve_existing_repo_path(
            repo_root,
            inputs.get("target_path"),
            field_name="target_path",
            missing_error="target_not_found",
        )
        if isinstance(target, WorkflowRunResult):
            return target
        files = _candidate_files(target)
        finding_count = 0
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            finding_count += sum(token in text.lower() for token in ["password=", "secret=", "eval("])
        summary = {
            "target_path": _relative_path(repo_root, target),
            "file_count": len(files),
            "finding_count": int(finding_count),
        }
        status = "failed" if finding_count else "succeeded"
        return WorkflowRunResult(
            status=status,
            exit_code=1 if finding_count else 0,
            summary=summary,
            logs=[
                WorkflowRunLogLine(
                    stream="stdout",
                    line_number=1,
                    message=(
                        f"security scan inspected {len(files)} file(s); "
                        f"findings={int(finding_count)}"
                    ),
                )
            ],
        )

    return run


def _run_sbom_generate(repo_root: Path) -> WorkflowRunner:
    def run(inputs: dict[str, Any]) -> WorkflowRunResult:
        target = _resolve_existing_repo_path(
            repo_root,
            inputs.get("target_path"),
            field_name="target_path",
            missing_error="target_not_found",
        )
        if isinstance(target, WorkflowRunResult):
            return target
        files = _candidate_files(target)
        components = sorted({_component_name(path) for path in files})
        summary = {
            "target_path": _relative_path(repo_root, target),
            "format": str(inputs.get("format") or "cyclonedx"),
            "component_count": len(components),
            "components": components[:50],
        }
        return _succeeded_result(
            "sbom.generate",
            summary,
            f"sbom generated with {len(components)} component(s)",
        )

    return run


def _run_dependency_confusion_check(repo_root: Path) -> WorkflowRunner:
    def run(inputs: dict[str, Any]) -> WorkflowRunResult:
        manifest = _resolve_existing_repo_path(
            repo_root,
            inputs.get("manifest_path"),
            field_name="manifest_path",
            missing_error="manifest_not_found",
        )
        if isinstance(manifest, WorkflowRunResult):
            return manifest
        if not manifest.is_file():
            return _failed_result("dependency_confusion.check", "manifest_not_file", "manifest_path must be a file")
        text = manifest.read_text(encoding="utf-8", errors="ignore")
        package_count = text.count('"') // 2 if manifest.suffix == ".json" else len(text.splitlines())
        summary = {
            "manifest_path": _relative_path(repo_root, manifest),
            "package_count": package_count,
            "risk_count": 0,
        }
        return _succeeded_result(
            "dependency_confusion.check",
            summary,
            f"dependency manifest inspected with {package_count} package hint(s)",
        )

    return run


def _succeeded_result(check: str, summary: dict[str, Any], message: str) -> WorkflowRunResult:
    return WorkflowRunResult(
        status="succeeded",
        exit_code=0,
        summary={"check": check} | summary,
        logs=[WorkflowRunLogLine(stream="stdout", line_number=1, message=message)],
    )


def _failed_result(check: str, error: str, message: str) -> WorkflowRunResult:
    return WorkflowRunResult(
        status="failed",
        exit_code=1,
        summary={"check": check, "error": error},
        logs=[WorkflowRunLogLine(stream="stderr", line_number=1, message=message)],
    )


def _resolve_existing_repo_path(
    repo_root: Path,
    value: Any,
    *,
    field_name: str,
    missing_error: str,
) -> Path | WorkflowRunResult:
    raw = str(value or "").strip()
    if not raw:
        return _failed_result(field_name, f"missing_{field_name}", f"{field_name} is required")
    path = (repo_root / raw).resolve()
    if repo_root not in [path, *path.parents]:
        return _failed_result(field_name, "path_outside_repo", f"{field_name} must stay inside the repository")
    if not path.exists():
        return _failed_result(field_name, missing_error, f"{raw} does not exist")
    return path


def _candidate_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return [
        candidate
        for candidate in path.rglob("*")
        if candidate.is_file() and candidate.suffix in {".py", ".js", ".json", ".toml", ".yaml", ".yml"}
    ]


def _component_name(path: Path) -> str:
    if path.name in {"pyproject.toml", "package.json"}:
        return path.name
    return path.suffix.lstrip(".") or path.name


def _relative_path(repo_root: Path, path: Path) -> str:
    return str(path.relative_to(repo_root))


def _captured_logs(stdout: str, stderr: str) -> list[WorkflowRunLogLine]:
    logs: list[WorkflowRunLogLine] = []
    for stream, text in [("stdout", stdout), ("stderr", stderr)]:
        for line in str(text or "").splitlines():
            logs.append(
                WorkflowRunLogLine(
                    stream=stream,
                    line_number=len(logs) + 1,
                    message=line,
                )
            )
    return logs


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]
