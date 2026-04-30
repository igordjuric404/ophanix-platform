"""FastAPI application factory for the Ophanix product control plane."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from product_platform import __version__
from product_platform.api.api_keys import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyStore,
)
from product_platform.audit.events import AuditEventEnvelope, workflow_run_event
from product_platform.audit.hash_chain import AuditVerificationResult
from product_platform.audit.store import AuditEventQuery, AuditEventRepository
from product_platform.audit.streaming import format_sse_event
from product_platform.api.auth import (
    SESSION_COOKIE_NAME,
    AuthResponse,
    AuthService,
    DevLoginRequest,
    UserPrincipal,
    get_current_user,
)
from product_platform.api.dependencies import (
    DependencyRegistry,
    create_default_dependency_registry,
)
from product_platform.api.models import (
    ApiError,
    DependencyStatus,
    HealthStatus,
    PublicConfig,
    RequestContext,
    VersionInfo,
)
from product_platform.api.rbac import Permission, require_permission
from product_platform.api.settings import Settings, load_settings
from product_platform.api.tenancy import (
    Environment,
    EnvironmentCreateRequest,
    Organization,
    TenantStore,
    require_environment_context,
)
from product_platform.db.connection import Database
from product_platform.db.seed import seed_demo_data
from product_platform.worker.api_models import (
    JobCreateRequest,
    JobResponse,
    JobScheduleCreateRequest,
    JobSchedulePatchRequest,
    JobScheduleResponse,
    job_response,
    job_schedule_response,
)
from product_platform.worker.scheduler import JobScheduleRepository
from product_platform.worker.store import JobStateRepository


def _request_context_from_request(request: Request) -> RequestContext:
    existing = getattr(request.state, "request_context", None)
    if isinstance(existing, RequestContext):
        return existing
    fallback_id = request.headers.get("X-Request-ID") or str(uuid4())
    return RequestContext(
        request_id=fallback_id,
        correlation_id=request.headers.get("X-Correlation-ID") or fallback_id,
        organization_id=request.headers.get("X-Organization-ID"),
        environment_id=request.headers.get("X-Environment-ID"),
        user_id=request.headers.get("X-User-ID"),
        actor_type=request.headers.get("X-Actor-Type"),
    )


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    context = _request_context_from_request(request)
    return JSONResponse(
        status_code=status_code,
        content=ApiError(
            code=code,
            message=message,
            request_id=context.request_id,
            details=details or {},
        ).model_dump(),
        headers={
            "X-Request-ID": context.request_id,
            "X-Correlation-ID": context.correlation_id,
        },
    )


def create_app(
    settings: Settings | None = None,
    dependency_registry: DependencyRegistry | None = None,
    tenant_store: TenantStore | None = None,
    api_key_store: ApiKeyStore | None = None,
    database: Database | None = None,
) -> FastAPI:
    """Create and configure the FastAPI product API."""

    resolved_settings = settings or load_settings()
    registry = dependency_registry or create_default_dependency_registry()
    auth_service = AuthService(resolved_settings)
    tenants = tenant_store or TenantStore()
    api_keys = api_key_store or ApiKeyStore(resolved_settings.session_secret)
    started_at = time.monotonic()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        description="Control plane API for the Ophanix product platform.",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.settings = resolved_settings
    app.state.dependency_registry = registry
    app.state.auth_service = auth_service
    app.state.api_key_store = api_keys
    app.state.tenant_store = tenants
    app.state.database = database
    app.state.denied_audit_events = []
    app.state.started_at = started_at

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        correlation_id = request.headers.get("X-Correlation-ID") or request_id
        principal = getattr(request.state, "principal", None)
        request.state.request_context = RequestContext(
            request_id=request_id,
            correlation_id=correlation_id,
            organization_id=getattr(
                request.state,
                "selected_organization_id",
                request.headers.get("X-Organization-ID"),
            ),
            environment_id=getattr(
                request.state,
                "selected_environment_id",
                request.headers.get("X-Environment-ID"),
            ),
            user_id=principal.id if isinstance(principal, UserPrincipal) else request.headers.get("X-User-ID"),
            actor_type=principal.actor_type
            if isinstance(principal, UserPrincipal)
            else request.headers.get("X-Actor-Type"),
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    public_api_paths = {"/api/v1/auth/dev-login"}

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next: Any) -> Any:
        if request.url.path.startswith("/api/v1") and request.url.path not in public_api_paths:
            principal = auth_service.authenticate_request(request)
            if principal is None:
                authorization = request.headers.get("Authorization", "")
                scheme, _, token = authorization.partition(" ")
                if scheme.lower() == "bearer" and token:
                    principal = api_keys.authenticate(token)
            if principal is None:
                return _error_response(
                    request,
                    status_code=401,
                    code="UNAUTHENTICATED",
                    message="Authentication is required.",
                )
            request.state.principal = principal
            selected_organization_id = (
                request.headers.get("X-Organization-ID") or principal.organization_id
            )
            if not selected_organization_id or selected_organization_id != principal.organization_id:
                return _error_response(
                    request,
                    status_code=403,
                    code="FORBIDDEN",
                    message="Organization access is denied.",
                )
            if tenants.get_organization(selected_organization_id) is None:
                return _error_response(
                    request,
                    status_code=403,
                    code="FORBIDDEN",
                    message="Organization access is denied.",
                )
            selected_environment_id = request.headers.get("X-Environment-ID")
            if selected_environment_id:
                environment = tenants.get_environment(selected_environment_id)
                if environment is None or environment.organization_id != selected_organization_id:
                    return _error_response(
                        request,
                        status_code=403,
                        code="FORBIDDEN",
                        message="Environment access is denied.",
                    )
            request.state.selected_organization_id = selected_organization_id
            request.state.selected_environment_id = selected_environment_id
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details={"errors": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "HTTP error."
        return _error_response(
            request,
            status_code=exc.status_code,
            code="HTTP_ERROR",
            message=detail,
            details={},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(
            request,
            status_code=500,
            code="INTERNAL_ERROR",
            message="Internal server error.",
            details={"error_type": exc.__class__.__name__},
        )

    def _version_info() -> VersionInfo:
        return VersionInfo(
            app=resolved_settings.app_name,
            version=__version__,
            build_sha=resolved_settings.build_sha,
            build_time=resolved_settings.build_time,
            environment=resolved_settings.environment,
        )

    def _audit_database() -> Database:
        existing = getattr(app.state, "database", None)
        if isinstance(existing, Database):
            return existing
        created = Database("sqlite:///:memory:")
        created.migrate()
        with created.transaction() as connection:
            seed_demo_data(connection)
        app.state.database = created
        return created

    def _require_organization_id(current_user: UserPrincipal) -> str:
        if current_user.organization_id is None:
            raise HTTPException(status_code=400, detail="Organization context is required.")
        return current_user.organization_id

    def _serialize_job(repository: JobStateRepository, job_id: str) -> JobResponse:
        row = repository.get_job(job_id)
        return job_response(row, repository.runs_for_job(job_id))

    def _insert_job_audit_event(
        repository: AuditEventRepository,
        *,
        organization_id: str,
        environment_id: str,
        job_id: str,
        job_type: str,
        status: str,
    ) -> None:
        repository.insert(
            workflow_run_event(
                organization_id=organization_id,
                environment_id=environment_id,
                workflow_run_id=job_id,
                workflow_type=job_type,
                status=status,
            )
        )

    @app.get("/health", response_model=HealthStatus, tags=["system"])
    async def health() -> HealthStatus:
        """Return liveness information."""

        return HealthStatus(
            status="ok",
            version=__version__,
            dependencies=registry.check_all(),
            uptime_seconds=round(time.monotonic() - started_at, 3),
        )

    @app.get("/ready", response_model=HealthStatus, tags=["system"])
    async def ready() -> HealthStatus:
        """Return readiness information."""

        ready_status, dependencies = registry.readiness_status()
        payload = HealthStatus(
            status="ready" if ready_status else "unhealthy",
            version=__version__,
            dependencies=dependencies,
            uptime_seconds=round(time.monotonic() - started_at, 3),
        )
        if not ready_status:
            return JSONResponse(status_code=503, content=payload.model_dump())
        return payload

    @app.get("/version", response_model=VersionInfo, tags=["system"])
    async def version() -> VersionInfo:
        """Return version and build metadata."""

        return _version_info()

    @app.get("/api/openapi.json", include_in_schema=False)
    async def api_openapi_alias() -> dict:
        """Expose OpenAPI at the product API alias expected by the plan."""

        return app.openapi()

    @app.get("/api/v1/system/config", response_model=PublicConfig, tags=["system"])
    async def system_config() -> PublicConfig:
        """Return configuration safe for frontend clients."""

        return PublicConfig(
            app_name=resolved_settings.app_name,
            environment=resolved_settings.environment,
            api_base_path=resolved_settings.api_base_path,
            docs_url="/docs",
            cors_origins=resolved_settings.cors_origins,
            features={
                "auth": True,
                "audit": True,
                "worker": True,
                "frontend_shell": False,
            },
        )

    @app.post("/api/v1/auth/dev-login", response_model=AuthResponse, tags=["auth"])
    async def dev_login(body: DevLoginRequest) -> JSONResponse:
        """Development-only login for allowlisted local users."""

        try:
            auth_response = auth_service.login(body)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        response = JSONResponse(content=auth_response.model_dump())
        response.set_cookie(
            SESSION_COOKIE_NAME,
            auth_response.access_token,
            httponly=True,
            samesite="lax",
            max_age=resolved_settings.session_ttl_seconds,
        )
        return response

    @app.post("/api/v1/auth/logout", tags=["auth"])
    async def logout() -> JSONResponse:
        """Clear the development auth session cookie."""

        response = JSONResponse(content={"status": "logged_out"})
        response.delete_cookie(SESSION_COOKIE_NAME)
        return response

    @app.get("/api/v1/auth/me", response_model=UserPrincipal, tags=["auth"])
    async def auth_me(current_user: UserPrincipal = Depends(get_current_user)) -> UserPrincipal:
        """Return the authenticated user principal."""

        return current_user

    @app.get("/api/v1/organizations", response_model=list[Organization], tags=["tenancy"])
    async def list_organizations(
        current_user: UserPrincipal = Depends(require_permission(Permission.TENANT_READ)),
    ) -> list[Organization]:
        """List organizations visible to the current user."""

        organization_ids = [current_user.organization_id] if current_user.organization_id else []
        return tenants.list_organizations(organization_ids)

    @app.get("/api/v1/environments", response_model=list[Environment], tags=["tenancy"])
    async def list_environments(
        current_user: UserPrincipal = Depends(require_permission(Permission.TENANT_READ)),
    ) -> list[Environment]:
        """List environments for the selected organization."""

        organization_id = current_user.organization_id
        if organization_id is None:
            return []
        return tenants.list_environments(organization_id)

    @app.post("/api/v1/environments", response_model=Environment, status_code=201, tags=["tenancy"])
    async def create_environment(
        body: EnvironmentCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.TENANT_MANAGE)),
    ) -> Environment:
        """Create an environment in the current organization."""

        if current_user.organization_id is None:
            raise HTTPException(status_code=400, detail="Organization context is required.")
        return tenants.create_environment(
            organization_id=current_user.organization_id,
            name=body.name,
            slug=body.slug,
            environment_type=body.type,
        )

    @app.post("/api/v1/api-keys", response_model=ApiKeyCreateResponse, status_code=201, tags=["auth"])
    async def create_api_key(
        body: ApiKeyCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.API_KEYS_MANAGE)),
    ) -> ApiKeyCreateResponse:
        """Create a scoped API key and return its one-time secret."""

        if current_user.organization_id is None:
            raise HTTPException(status_code=400, detail="Organization context is required.")
        record, secret = api_keys.create_key(
            organization_id=current_user.organization_id,
            name=body.name,
            scopes=body.scopes,
            kind=body.kind,
            expires_at=body.expires_at,
        )
        return ApiKeyCreateResponse(key=record.to_response(), secret=secret)

    @app.get("/api/v1/api-keys", response_model=list[ApiKeyResponse], tags=["auth"])
    async def list_api_keys(
        current_user: UserPrincipal = Depends(require_permission(Permission.API_KEYS_MANAGE)),
    ) -> list[ApiKeyResponse]:
        """List API keys for the current organization without raw secrets."""

        if current_user.organization_id is None:
            return []
        return [record.to_response() for record in api_keys.list_keys(current_user.organization_id)]

    @app.delete("/api/v1/api-keys/{key_id}", status_code=204, tags=["auth"])
    async def revoke_api_key(
        key_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.API_KEYS_MANAGE)),
    ) -> None:
        """Revoke an API key for the current organization."""

        if current_user.organization_id is None or not api_keys.revoke(
            key_id, current_user.organization_id
        ):
            raise HTTPException(status_code=404, detail="API key not found.")

    @app.post("/api/v1/audit/events", response_model=AuditEventEnvelope, status_code=201, tags=["audit"])
    async def create_audit_event(
        event: AuditEventEnvelope,
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_WRITE)),
    ) -> AuditEventEnvelope:
        """Persist a canonical audit event."""

        if event.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Organization access is denied.")
        database_for_audit = _audit_database()
        with database_for_audit.transaction() as connection:
            return AuditEventRepository(connection).insert(event)

    @app.get("/api/v1/audit/events", response_model=list[AuditEventEnvelope], tags=["audit"])
    async def list_audit_events(
        event_type: str | None = None,
        agent_id: str | None = None,
        decision: str | None = None,
        severity: str | None = None,
        policy_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        correlation_id: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_READ)),
    ) -> list[AuditEventEnvelope]:
        """List audit events for the current organization."""

        if current_user.organization_id is None:
            return []
        return AuditEventRepository(_audit_database().connect()).query(
            AuditEventQuery(
                organization_id=current_user.organization_id,
                event_type=event_type,
                agent_id=agent_id,
                decision=decision,
                severity=severity,
                policy_id=policy_id,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                created_from=created_from,
                created_to=created_to,
                limit=limit,
                offset=offset,
            )
        )

    @app.get("/api/v1/audit/events/stream", tags=["audit"])
    async def stream_audit_events(
        event_type: str | None = None,
        last_event_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_READ)),
    ) -> StreamingResponse:
        """Stream current audit events as server-sent events."""

        if current_user.organization_id is None:
            events = []
        else:
            events = AuditEventRepository(_audit_database().connect()).stream_events(
                organization_id=current_user.organization_id,
                event_type=event_type,
                last_event_id=last_event_id,
                limit=limit,
            )

        def body() -> Any:
            for event in events:
                yield format_sse_event(event)

        return StreamingResponse(body(), media_type="text/event-stream")

    @app.get("/api/v1/audit/events/{event_id}", response_model=AuditEventEnvelope, tags=["audit"])
    async def get_audit_event(
        event_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_READ)),
    ) -> AuditEventEnvelope:
        """Get a single audit event."""

        if current_user.organization_id is None:
            raise HTTPException(status_code=404, detail="Audit event not found.")
        event = AuditEventRepository(_audit_database().connect()).get(
            event_id, current_user.organization_id
        )
        if event is None:
            raise HTTPException(status_code=404, detail="Audit event not found.")
        return event

    @app.post(
        "/api/v1/audit/events/{event_id}/verify",
        response_model=AuditVerificationResult,
        tags=["audit"],
    )
    async def verify_audit_event(
        event_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_READ)),
    ) -> AuditVerificationResult:
        """Verify one audit event hash."""

        if current_user.organization_id is None:
            raise HTTPException(status_code=404, detail="Audit event not found.")
        return AuditEventRepository(_audit_database().connect()).verify_event(
            event_id, current_user.organization_id
        )

    @app.post(
        "/api/v1/audit/verify-range",
        response_model=AuditVerificationResult,
        tags=["audit"],
    )
    async def verify_audit_range(
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_READ)),
    ) -> AuditVerificationResult:
        """Verify the current organization's audit hash chain."""

        if current_user.organization_id is None:
            return AuditVerificationResult(valid=True, checked_count=0)
        return AuditEventRepository(_audit_database().connect()).verify_range(
            current_user.organization_id
        )

    @app.post("/api/v1/jobs", response_model=JobResponse, status_code=201, tags=["jobs"])
    async def create_job(
        body: JobCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> JobResponse:
        """Create a background job in the selected environment."""

        organization_id = _require_organization_id(current_user)
        database_for_jobs = _audit_database()
        with database_for_jobs.transaction() as connection:
            jobs = JobStateRepository(connection)
            audit = AuditEventRepository(connection)
            created = jobs.create_job(
                organization_id=organization_id,
                environment_id=environment_id,
                job_type=body.job_type,
                payload=body.payload,
                max_attempts=body.max_attempts,
            )
            _insert_job_audit_event(
                audit,
                organization_id=organization_id,
                environment_id=environment_id,
                job_id=created["id"],
                job_type=created["job_type"],
                status=created["status"],
            )
            if body.run_immediately:
                if body.job_type != "demo.noop":
                    raise HTTPException(
                        status_code=400,
                        detail="Only demo.noop can run immediately in the foundation runtime.",
                    )
                jobs.mark_running(created["id"])
                completed = jobs.mark_succeeded(
                    created["id"],
                    logs=["queued", "started demo.noop", "completed demo.noop"],
                    metrics={"duration_ms": 0},
                    result={"ok": True, "job_type": body.job_type},
                )
                _insert_job_audit_event(
                    audit,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    job_id=completed["id"],
                    job_type=completed["job_type"],
                    status=completed["status"],
                )
            return _serialize_job(jobs, created["id"])

    @app.get("/api/v1/jobs", response_model=list[JobResponse], tags=["jobs"])
    async def list_jobs(
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
    ) -> list[JobResponse]:
        """List background jobs for the current organization."""

        organization_id = _require_organization_id(current_user)
        jobs = JobStateRepository(_audit_database().connect())
        return [
            job_response(row, jobs.runs_for_job(row["id"]))
            for row in jobs.list_jobs(organization_id, limit=limit, offset=offset)
        ]

    @app.get("/api/v1/jobs/{job_id}", response_model=JobResponse, tags=["jobs"])
    async def get_job(
        job_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
    ) -> JobResponse:
        """Get one background job and its run attempts."""

        organization_id = _require_organization_id(current_user)
        jobs = JobStateRepository(_audit_database().connect())
        row = jobs.get_job_for_org(job_id, organization_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return job_response(row, jobs.runs_for_job(job_id))

    @app.post("/api/v1/jobs/{job_id}/cancel", response_model=JobResponse, tags=["jobs"])
    async def cancel_job(
        job_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_CANCEL)),
    ) -> JobResponse:
        """Cancel a queued background job."""

        organization_id = _require_organization_id(current_user)
        database_for_jobs = _audit_database()
        with database_for_jobs.transaction() as connection:
            jobs = JobStateRepository(connection)
            row = jobs.get_job_for_org(job_id, organization_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Job not found.")
            canceled = jobs.cancel(job_id)
            if canceled["status"] == "canceled" and row["status"] != "canceled":
                _insert_job_audit_event(
                    AuditEventRepository(connection),
                    organization_id=organization_id,
                    environment_id=canceled["environment_id"],
                    job_id=canceled["id"],
                    job_type=canceled["job_type"],
                    status=canceled["status"],
                )
            return job_response(canceled, jobs.runs_for_job(job_id))

    @app.post(
        "/api/v1/job-schedules",
        response_model=JobScheduleResponse,
        status_code=201,
        tags=["jobs"],
    )
    async def create_job_schedule(
        body: JobScheduleCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> JobScheduleResponse:
        """Create a recurring background job schedule."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            schedule = JobScheduleRepository(connection).create_schedule(
                organization_id=organization_id,
                environment_id=environment_id,
                job_type=body.job_type,
                expression=body.cron_expression,
                payload=body.payload,
                enabled=body.enabled,
                next_run_at=body.next_run_at,
            )
            return job_schedule_response(schedule)

    @app.get("/api/v1/job-schedules", response_model=list[JobScheduleResponse], tags=["jobs"])
    async def list_job_schedules(
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
    ) -> list[JobScheduleResponse]:
        """List recurring background job schedules for the current organization."""

        organization_id = _require_organization_id(current_user)
        schedules = JobScheduleRepository(_audit_database().connect()).list_schedules(
            organization_id
        )
        return [job_schedule_response(schedule) for schedule in schedules]

    @app.patch(
        "/api/v1/job-schedules/{schedule_id}",
        response_model=JobScheduleResponse,
        tags=["jobs"],
    )
    async def patch_job_schedule(
        schedule_id: str,
        body: JobSchedulePatchRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
    ) -> JobScheduleResponse:
        """Patch schedule enablement and next-run controls."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            schedules = JobScheduleRepository(connection)
            schedule = schedules.update_schedule(
                schedule_id,
                organization_id,
                enabled=body.enabled,
                next_run_at=body.next_run_at,
            )
            if schedule is None:
                raise HTTPException(status_code=404, detail="Schedule not found.")
            return job_schedule_response(schedule)

    @app.post("/api/v1/policies", status_code=201, tags=["policies"])
    async def create_policy_placeholder(
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> dict[str, Any]:
        """Placeholder policy creation route used to enforce RBAC contracts."""

        return {
            "id": "policy_placeholder",
            "status": "created",
            "created_by": current_user.id,
            "environment_id": environment_id,
        }

    @app.get("/api/v1/system/dependencies", response_model=list[DependencyStatus], tags=["system"])
    async def system_dependencies(
        required_only: bool = Query(default=False),
    ) -> list[DependencyStatus]:
        """Return downstream dependency states."""

        dependencies = registry.check_all()
        if required_only:
            return [dependency for dependency in dependencies if dependency.required]
        return dependencies

    @app.get("/api/v1/system/not-found-probe", include_in_schema=False)
    async def not_found_probe() -> None:
        raise HTTPException(status_code=404, detail="Probe not found.")

    return app


app = create_app()
