"""Local queue and worker process for product background jobs."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from product_platform.db.ids import generate_id


@dataclass(frozen=True)
class JobRequest:
    """Queued job request."""

    job_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: generate_id("job"))


@dataclass
class JobContext:
    """Context passed to a job handler."""

    job_id: str
    job_type: str
    payload: dict[str, Any]
    logs: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def log(self, message: str) -> None:
        self.logs.append(message)


@dataclass(frozen=True)
class JobResult:
    """Job handler result."""

    status: str = "succeeded"
    result: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JobExecution:
    """Result of one worker execution attempt."""

    job_id: str
    job_type: str
    status: str
    logs: list[str] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


JobHandler = Callable[[JobContext], JobResult]


class JobRegistry:
    """Maps job types to handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    @property
    def job_types(self) -> tuple[str, ...]:
        return tuple(self._handlers.keys())

    def resolve(self, job_type: str) -> JobHandler:
        try:
            return self._handlers[job_type]
        except KeyError as exc:
            raise KeyError(f"Unknown job type: {job_type}") from exc


class InMemoryJobQueue:
    """Simple FIFO queue for local development and tests."""

    def __init__(self) -> None:
        self._jobs: deque[JobRequest] = deque()

    def enqueue(self, request: JobRequest) -> JobRequest:
        self._jobs.append(request)
        return request

    def dequeue(self) -> JobRequest | None:
        if not self._jobs:
            return None
        return self._jobs.popleft()

    def __len__(self) -> int:
        return len(self._jobs)


class Worker:
    """Executes jobs from a queue using a registry."""

    def __init__(self, queue: InMemoryJobQueue, registry: JobRegistry) -> None:
        self.queue = queue
        self.registry = registry
        self._stopping = False

    @property
    def stopping(self) -> bool:
        return self._stopping

    def stop(self) -> None:
        self._stopping = True

    def run_once(self) -> JobExecution | None:
        if self._stopping:
            return None
        request = self.queue.dequeue()
        if request is None:
            return None
        context = JobContext(
            job_id=request.id,
            job_type=request.job_type,
            payload=dict(request.payload),
        )
        try:
            handler = self.registry.resolve(request.job_type)
            result = handler(context)
        except Exception as exc:
            return JobExecution(
                job_id=request.id,
                job_type=request.job_type,
                status="failed",
                logs=list(context.logs),
                error_message=str(exc),
            )
        return JobExecution(
            job_id=request.id,
            job_type=request.job_type,
            status=result.status,
            logs=list(context.logs),
            result=result.result,
            metrics=result.metrics | context.metrics,
        )

    def run_until_empty(self) -> list[JobExecution]:
        executions: list[JobExecution] = []
        while not self._stopping:
            execution = self.run_once()
            if execution is None:
                break
            executions.append(execution)
        return executions
