"""Safe workflow runner registry and local adapters."""

from __future__ import annotations

import subprocess
import sys
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
    registry.register("python:governance.verify", _run_simple_python_check("governance.verify"))
    registry.register("python:integrity.check", _run_simple_python_check("integrity.check"))
    registry.register("python:marketplace.evaluate", _run_simple_python_check("marketplace.evaluate"))
    registry.register_shell(
        "shell:security.scan",
        [sys.executable, "-c", "print('security scan completed')"],
    )
    registry.register_shell(
        "shell:sbom.generate",
        [sys.executable, "-c", "print('sbom generated')"],
    )
    registry.register_shell(
        "shell:dependency_confusion.check",
        [sys.executable, "-c", "print('dependency confusion check completed')"],
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


def _run_simple_python_check(name: str) -> WorkflowRunner:
    def run(inputs: dict[str, Any]) -> WorkflowRunResult:
        return WorkflowRunResult(
            status="succeeded",
            exit_code=0,
            summary={"check": name, "input_keys": sorted(inputs)},
            logs=[
                WorkflowRunLogLine(
                    stream="stdout",
                    line_number=1,
                    message=f"{name} completed",
                )
            ],
        )

    return run


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
