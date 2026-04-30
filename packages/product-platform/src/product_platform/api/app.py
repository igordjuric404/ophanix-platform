"""FastAPI application factory for the Ophanix product control plane."""

from __future__ import annotations

import time
import json
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
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
from product_platform.audit.events import AuditEventEnvelope, agent_lifecycle_event, workflow_run_event
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
from product_platform.agents.models import (
    AgentCredentialIssueRequest,
    AgentCredentialIssueResponse,
    AgentCredentialRotationResponse,
    AgentCredentialResponse,
    AgentDetailResponse,
    AgentHeartbeatRequest,
    AgentIdentityCreateResponse,
    AgentInventorySummary,
    AgentLifecycleActionRequest,
    AgentOwnerChangeRequest,
    AgentPatchRequest,
    AgentRegistrationSimulationResponse,
    AgentRegistrationDraftCreate,
    AgentRegistrationDraftPatch,
    AgentRegistrationDraftResponse,
    AgentTimelineEvent,
    CredentialActionRequest,
    CredentialVerifyRequest,
    CredentialVerifyResponse,
    OrphanDetectionRunRequest,
    OrphanDetectionRunResponse,
)
from product_platform.agents.credentials import (
    AgentCredentialIssuer,
    AgentCredentialRepository,
    CredentialNotFoundError,
    CredentialExpiryMonitor,
    agent_credential_response,
)
from product_platform.agents.repository import (
    AgentNotFoundError,
    AgentRegistryRepository,
    DuplicateAgentNameError,
    agent_inventory_summary,
    agent_identity_response,
    agent_registration_draft_response,
    agent_detail_response,
    lifecycle_timeline_event,
)
from product_platform.agents.identity import AgentIdentityAdapter
from product_platform.agents.lifecycle import AgentLifecycleTransitionError
from product_platform.agents.simulation import simulate_registration_action
from product_platform.db.connection import Database
from product_platform.db.seed import seed_demo_data
from product_platform.discovery.models import (
    DiscoveryAssignOwnerRequest,
    DiscoveryFindingResponse,
    DiscoveryRegisterAgentRequest,
    DiscoveryRunCreateRequest,
    DiscoveryRunResponse,
    DiscoveryScannerResponse,
    DiscoveryTargetCreateRequest,
    DiscoveryTargetResponse,
    DiscoveryTargetSchedulePatch,
    DiscoverySuppressRequest,
)
from product_platform.discovery.findings import (
    DiscoveryFindingNotFoundError,
    DiscoveryFindingRepository,
    discovery_finding_response,
)
from product_platform.discovery.registry import DiscoveryScannerRegistry
from product_platform.discovery.repository import (
    DiscoveryRepository,
    DiscoveryTargetNotFoundError,
    discovery_run_response,
    discovery_target_response,
)
from product_platform.discovery.runner import DiscoveryScanRunner
from product_platform.policies.models import (
    PolicyBindingCreateRequest,
    PolicyBindingPatchRequest,
    PolicyBindingPromoteRequest,
    PolicyBindingResponse,
    PolicyCreateRequest,
    PolicyDetailResponse,
    PolicyExportResponse,
    PolicyAffectedResourcesResponse,
    PolicyExceptionCreateRequest,
    PolicyExceptionResponse,
    PolicyImportRequest,
    PolicyImportResponse,
    PolicyLintIssue,
    PolicyLintRequest,
    PolicyLintResponse,
    PolicyResponse,
    PolicyVersionCreateRequest,
    PolicyVersionResponse,
)
from product_platform.policies.bindings import (
    PolicyBindingNotFoundError,
    PolicyBindingRepository,
    PolicyBindingTargetError,
    policy_binding_response,
    policy_exception_response,
)
from product_platform.policies.importer import prepare_policy_import
from product_platform.policies.linting import lint_policy_body
from product_platform.policies.repository import (
    DuplicatePolicySlugError,
    PolicyNotFoundError,
    PolicyRepository,
    policy_detail_response,
    policy_export_response,
    policy_import_response,
    policy_lint_issue_response,
    policy_response,
    policy_version_response,
)
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
            details={"errors": jsonable_encoder(exc.errors())},
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

    def _default_environment_id_for_org(organization_id: str) -> str:
        environments = tenants.list_environments(organization_id)
        return environments[0].id if environments else "env_default"

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

    def _agent_registration_audit_event(
        *,
        row: Any,
        actor_id: str,
        event_type: str,
        correlation_id: str | None = None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=row["organization_id"],
            environment_id=row["environment_id"],
            event_type=event_type,
            source_component="agent-registry",
            actor_type="user",
            actor_id=actor_id,
            agent_id=row["id"],
            resource_type="agent",
            resource_id=row["id"],
            correlation_id=correlation_id,
            payload_json={
                "name": row["name"],
                "status": row["status"],
                "framework": row["framework"],
                "runtime_type": row["runtime_type"],
            },
        )

    def _discovery_scan_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        event_type: str,
        actor_id: str,
        run: Any,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="discovery-scan-runner",
            actor_type="user",
            actor_id=actor_id,
            resource_type="discovery_run",
            resource_id=run["id"],
            correlation_id=correlation_id,
            payload_json={
                "run_id": run["id"],
                "target_id": run["target_id"],
                "scanner_type": run["scanner_type"],
                "status": run["status"],
            },
        )

    def _discovery_finding_action_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        finding: Any,
        action_type: str,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="discovery.finding.action",
            source_component="discovery-reconciliation",
            actor_type="user",
            actor_id=actor_id,
            resource_type="discovery_finding",
            resource_id=finding["id"],
            correlation_id=correlation_id,
            payload_json={
                "action_type": action_type,
                "finding_id": finding["id"],
                "status": finding["status"],
                "risk_level": finding["risk_level"],
                "registry_agent_id": finding["registry_agent_id"],
            },
        )

    def _policy_version_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        event_type: str,
        actor_id: str,
        policy_id: str,
        version_id: str,
        version_number: int,
        correlation_id: str | None,
        payload_json: dict[str, Any] | None = None,
    ) -> AuditEventEnvelope:
        payload = {
            "policy_id": policy_id,
            "policy_version_id": version_id,
            "version_number": version_number,
        }
        payload.update(payload_json or {})
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="policy-library",
            actor_type="user",
            actor_id=actor_id,
            resource_type="policy_version",
            resource_id=version_id,
            policy_id=policy_id,
            policy_version_id=version_id,
            correlation_id=correlation_id,
            payload_json=payload,
        )

    def _policy_binding_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        event_type: str,
        actor_id: str,
        binding: Any,
        correlation_id: str | None,
        payload_json: dict[str, Any] | None = None,
    ) -> AuditEventEnvelope:
        payload = {
            "binding_id": binding["id"],
            "policy_id": binding["policy_id"],
            "policy_version_id": binding["policy_version_id"],
            "target_type": binding["target_type"],
            "target_id": binding["target_id"],
            "mode": binding["mode"],
            "rollout_percentage": binding["rollout_percentage"],
            "status": binding["status"],
        }
        payload.update(payload_json or {})
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="policy-bindings",
            actor_type="user",
            actor_id=actor_id,
            resource_type="policy_binding",
            resource_id=binding["id"],
            policy_id=binding["policy_id"],
            policy_version_id=binding["policy_version_id"],
            correlation_id=correlation_id,
            payload_json=payload,
        )

    def _resolve_sponsor_email(row: Any, current_user: UserPrincipal, connection: Any) -> str:
        sponsor_user_id = str(row["sponsor_user_id"])
        if "@" in sponsor_user_id:
            return sponsor_user_id
        user_row = connection.execute(
            "SELECT email FROM users WHERE id = ? AND deleted_at IS NULL",
            (sponsor_user_id,),
        ).fetchone()
        if user_row is not None:
            return str(user_row["email"])
        if sponsor_user_id == current_user.id:
            return current_user.email
        raise HTTPException(status_code=400, detail="Sponsor email could not be resolved.")

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
        "/api/v1/policies",
        status_code=201,
        tags=["policies"],
    )
    async def create_policy(
        request: Request,
        body: PolicyCreateRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
    ) -> Any:
        """Create a tenant-scoped policy library entry."""

        if body is None:
            environment_id = getattr(request.state, "selected_environment_id", None)
            if not environment_id:
                raise HTTPException(status_code=400, detail="X-Environment-ID is required.")
            return {
                "id": "policy_placeholder",
                "status": "created",
                "created_by": current_user.id,
                "environment_id": str(environment_id),
            }

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                row = PolicyRepository(connection, organization_id).create_policy(
                    body,
                    actor_id=current_user.id,
                )
                return policy_response(row)
        except DuplicatePolicySlugError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/policies", response_model=list[PolicyResponse], tags=["policies"])
    async def list_policies(
        scope: str | None = None,
        owner_user_id: str | None = None,
        backend: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
    ) -> list[PolicyResponse]:
        """List policies for the current organization."""

        organization_id = _require_organization_id(current_user)
        repository = PolicyRepository(_audit_database().connect(), organization_id)
        rows = repository.list_policies(
            scope=scope,
            owner_user_id=owner_user_id,
            backend=backend,
            status=status,
            tag=tag,
            limit=limit,
            offset=offset,
        )
        return [policy_response(row) for row in rows]

    @app.get(
        "/api/v1/policies/{policy_id}",
        response_model=PolicyDetailResponse,
        tags=["policies"],
    )
    async def get_policy(
        policy_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
    ) -> PolicyDetailResponse:
        """Get one policy with version history."""

        organization_id = _require_organization_id(current_user)
        repository = PolicyRepository(_audit_database().connect(), organization_id)
        row = repository.get_policy(policy_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Policy not found.")
        return policy_detail_response(repository, row)

    @app.post(
        "/api/v1/policies/{policy_id}/versions",
        response_model=PolicyVersionResponse,
        status_code=201,
        tags=["policies"],
    )
    async def create_policy_version(
        policy_id: str,
        body: PolicyVersionCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
    ) -> PolicyVersionResponse:
        """Create an immutable policy version."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                row = PolicyRepository(connection, organization_id).create_version(
                    policy_id,
                    body,
                    actor_id=current_user.id,
                )
                return policy_version_response(row)
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/policies/{policy_id}/versions",
        response_model=list[PolicyVersionResponse],
        tags=["policies"],
    )
    async def list_policy_versions(
        policy_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
    ) -> list[PolicyVersionResponse]:
        """List immutable versions for a policy."""

        organization_id = _require_organization_id(current_user)
        try:
            repository = PolicyRepository(_audit_database().connect(), organization_id)
            return [policy_version_response(row) for row in repository.list_versions(policy_id)]
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/policies/lint",
        response_model=PolicyLintResponse,
        tags=["policies"],
    )
    async def lint_unsaved_policy(
        body: PolicyLintRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
    ) -> PolicyLintResponse:
        """Lint an unsaved policy body."""

        _require_organization_id(current_user)
        return lint_policy_body(body)

    @app.post(
        "/api/v1/policies/{policy_id}/versions/draft",
        response_model=PolicyVersionResponse,
        status_code=201,
        tags=["policies"],
    )
    async def save_policy_draft_version(
        policy_id: str,
        body: PolicyVersionCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
    ) -> PolicyVersionResponse:
        """Save a non-active draft version and persist lint results."""

        organization_id = _require_organization_id(current_user)
        draft_body = PolicyVersionCreateRequest(
            body_format=body.body_format,
            body_text=body.body_text,
            backend=body.backend,
            status="draft",
        )
        lint_result = lint_policy_body(
            PolicyLintRequest(body_text=draft_body.body_text, body_format=draft_body.body_format)
        )
        try:
            with _audit_database().transaction() as connection:
                repository = PolicyRepository(connection, organization_id)
                row = repository.create_version(policy_id, draft_body, actor_id=current_user.id)
                repository.replace_lint_results(policy_id, row["id"], lint_result)
                return policy_version_response(row)
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/policies/{policy_id}/versions/{version_id}/lint",
        response_model=PolicyLintResponse,
        tags=["policies"],
    )
    async def lint_saved_policy_version(
        policy_id: str,
        version_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
    ) -> PolicyLintResponse:
        """Lint a saved policy version and persist the results."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = PolicyRepository(connection, organization_id)
                version = repository.get_version(policy_id, version_id)
                if version is None:
                    raise PolicyNotFoundError("Policy version not found.")
                lint_result = lint_policy_body(
                    PolicyLintRequest(
                        body_text=version["body_text"],
                        body_format=version["body_format"],
                    )
                )
                repository.replace_lint_results(policy_id, version_id, lint_result)
                return lint_result
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/policies/{policy_id}/versions/{version_id}/lint-results",
        response_model=list[PolicyLintIssue],
        tags=["policies"],
    )
    async def list_policy_version_lint_results(
        policy_id: str,
        version_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
    ) -> list[PolicyLintIssue]:
        """List persisted lint results for a saved policy version."""

        organization_id = _require_organization_id(current_user)
        try:
            repository = PolicyRepository(_audit_database().connect(), organization_id)
            return [
                policy_lint_issue_response(row)
                for row in repository.list_lint_results(policy_id, version_id)
            ]
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/policies/{policy_id}/affected-resources",
        response_model=PolicyAffectedResourcesResponse,
        tags=["policies"],
    )
    async def get_policy_affected_resources(
        policy_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
    ) -> PolicyAffectedResourcesResponse:
        """Return resources that currently reference a policy."""

        organization_id = _require_organization_id(current_user)
        try:
            return PolicyRepository(
                _audit_database().connect(),
                organization_id,
            ).affected_resources(policy_id)
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/policy-bindings",
        response_model=PolicyBindingResponse,
        status_code=201,
        tags=["policies"],
    )
    async def create_policy_binding(
        body: PolicyBindingCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> PolicyBindingResponse:
        """Create a policy binding for a selected environment target."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = PolicyBindingRepository(connection, organization_id, environment_id)
                row = repository.create_binding(body, actor_id=current_user.id)
                AuditEventRepository(connection).insert(
                    _policy_binding_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="policy.binding.created",
                        actor_id=current_user.id,
                        binding=row,
                        correlation_id=context.correlation_id,
                    )
                )
                return policy_binding_response(row)
        except (PolicyNotFoundError, PolicyBindingTargetError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/policy-bindings",
        response_model=list[PolicyBindingResponse],
        tags=["policies"],
    )
    async def list_policy_bindings(
        policy_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        status: str | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[PolicyBindingResponse]:
        """List policy bindings in the selected environment."""

        organization_id = _require_organization_id(current_user)
        repository = PolicyBindingRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        return [
            policy_binding_response(row)
            for row in repository.list_bindings(
                policy_id=policy_id,
                target_type=target_type,
                target_id=target_id,
                status=status,
            )
        ]

    @app.patch(
        "/api/v1/policy-bindings/{binding_id}",
        response_model=PolicyBindingResponse,
        tags=["policies"],
    )
    async def patch_policy_binding(
        binding_id: str,
        body: PolicyBindingPatchRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> PolicyBindingResponse:
        """Patch policy binding rollout controls."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = PolicyBindingRepository(connection, organization_id, environment_id)
                row = repository.update_binding(binding_id, body)
                AuditEventRepository(connection).insert(
                    _policy_binding_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="policy.binding.updated",
                        actor_id=current_user.id,
                        binding=row,
                        correlation_id=context.correlation_id,
                    )
                )
                return policy_binding_response(row)
        except PolicyBindingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete(
        "/api/v1/policy-bindings/{binding_id}",
        status_code=204,
        tags=["policies"],
    )
    async def delete_policy_binding(
        binding_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> None:
        """Delete a binding by marking it deleted and emitting an audit event."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = PolicyBindingRepository(connection, organization_id, environment_id)
                row = repository.delete_binding(binding_id)
                AuditEventRepository(connection).insert(
                    _policy_binding_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="policy.binding.deleted",
                        actor_id=current_user.id,
                        binding=row,
                        correlation_id=context.correlation_id,
                    )
                )
        except PolicyBindingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/policy-bindings/{binding_id}/promote",
        response_model=PolicyBindingResponse,
        tags=["policies"],
    )
    async def promote_policy_binding(
        binding_id: str,
        body: PolicyBindingPromoteRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> PolicyBindingResponse:
        """Promote binding mode or rollout percentage with an audit trail."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = PolicyBindingRepository(connection, organization_id, environment_id)
                row = repository.promote_binding(binding_id, body, actor_id=current_user.id)
                AuditEventRepository(connection).insert(
                    _policy_binding_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="policy.binding.promoted",
                        actor_id=current_user.id,
                        binding=row,
                        correlation_id=context.correlation_id,
                        payload_json={"reason": body.reason},
                    )
                )
                return policy_binding_response(row)
        except PolicyBindingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/policy-bindings/{binding_id}/exceptions",
        response_model=PolicyExceptionResponse,
        status_code=201,
        tags=["policies"],
    )
    async def create_policy_exception(
        binding_id: str,
        body: PolicyExceptionCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> PolicyExceptionResponse:
        """Create an exception for a visible binding."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = PolicyBindingRepository(connection, organization_id, environment_id)
                row = repository.create_exception(binding_id, body, actor_id=current_user.id)
                binding = repository.get_binding(binding_id)
                if binding is not None:
                    AuditEventRepository(connection).insert(
                        _policy_binding_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            event_type="policy.binding.exception_created",
                            actor_id=current_user.id,
                            binding=binding,
                            correlation_id=context.correlation_id,
                            payload_json={"exception_id": row["id"], "reason": row["reason"]},
                        )
                    )
                return policy_exception_response(row)
        except (PolicyBindingNotFoundError, PolicyBindingTargetError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/policy-exceptions",
        response_model=list[PolicyExceptionResponse],
        tags=["policies"],
    )
    async def list_policy_exceptions(
        binding_id: str | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[PolicyExceptionResponse]:
        """List exceptions in the selected environment."""

        organization_id = _require_organization_id(current_user)
        repository = PolicyBindingRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        return [
            policy_exception_response(row)
            for row in repository.list_exceptions(binding_id=binding_id)
        ]

    @app.post(
        "/api/v1/policies/{policy_id}/versions/{version_id}/activate",
        response_model=PolicyVersionResponse,
        tags=["policies"],
    )
    async def activate_policy_version(
        policy_id: str,
        version_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
    ) -> PolicyVersionResponse:
        """Activate a policy version and audit the change."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = PolicyRepository(connection, organization_id)
                row = repository.activate_version(policy_id, version_id)
                AuditEventRepository(connection).insert(
                    _policy_version_audit_event(
                        organization_id=organization_id,
                        environment_id=context.environment_id
                        or _default_environment_id_for_org(organization_id),
                        event_type="policy.version.activated",
                        actor_id=current_user.id,
                        policy_id=policy_id,
                        version_id=version_id,
                        version_number=int(row["version_number"]),
                        correlation_id=context.correlation_id,
                    )
                )
                return policy_version_response(row)
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/policies/{policy_id}/versions/{version_id}/rollback",
        response_model=PolicyVersionResponse,
        tags=["policies"],
    )
    async def rollback_policy_version(
        policy_id: str,
        version_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
    ) -> PolicyVersionResponse:
        """Roll back by activating the selected previous policy version."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = PolicyRepository(connection, organization_id)
                row = repository.activate_version(policy_id, version_id)
                AuditEventRepository(connection).insert(
                    _policy_version_audit_event(
                        organization_id=organization_id,
                        environment_id=context.environment_id
                        or _default_environment_id_for_org(organization_id),
                        event_type="policy.version.rolled_back",
                        actor_id=current_user.id,
                        policy_id=policy_id,
                        version_id=version_id,
                        version_number=int(row["version_number"]),
                        correlation_id=context.correlation_id,
                    )
                )
                return policy_version_response(row)
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/policies/{policy_id}/versions/{version_id}/archive",
        response_model=PolicyVersionResponse,
        tags=["policies"],
    )
    async def archive_policy_version(
        policy_id: str,
        version_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
    ) -> PolicyVersionResponse:
        """Archive a policy version so it cannot be activated."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = PolicyRepository(connection, organization_id)
                row = repository.archive_version(policy_id, version_id)
                AuditEventRepository(connection).insert(
                    _policy_version_audit_event(
                        organization_id=organization_id,
                        environment_id=context.environment_id
                        or _default_environment_id_for_org(organization_id),
                        event_type="policy.version.archived",
                        actor_id=current_user.id,
                        policy_id=policy_id,
                        version_id=version_id,
                        version_number=int(row["version_number"]),
                        correlation_id=context.correlation_id,
                    )
                )
                return policy_version_response(row)
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/policies/import",
        response_model=PolicyImportResponse,
        status_code=201,
        tags=["policies"],
    )
    async def import_policy(
        body: PolicyImportRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
    ) -> PolicyImportResponse:
        """Import a policy body or known repository policy path."""

        organization_id = _require_organization_id(current_user)
        try:
            prepared = prepare_policy_import(body)
            with _audit_database().transaction() as connection:
                repository = PolicyRepository(connection, organization_id)
                policy_row = repository.create_policy(prepared.policy, actor_id=current_user.id)
                version_row = repository.create_version(
                    policy_row["id"],
                    prepared.version,
                    actor_id=current_user.id,
                )
                import_row = repository.record_import(
                    source_type=prepared.source_type,
                    source_path=prepared.source_path,
                    status="succeeded",
                    summary={
                        **prepared.summary,
                        "policy_id": policy_row["id"],
                        "policy_version_id": version_row["id"],
                    },
                )
                return policy_import_response(
                    import_row,
                    policy=policy_response(policy_row),
                    version=policy_version_response(version_row),
                )
        except DuplicatePolicySlugError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/policies/{policy_id}/export",
        response_model=PolicyExportResponse,
        tags=["policies"],
    )
    async def export_policy(
        policy_id: str,
        version_id: str | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
    ) -> PolicyExportResponse:
        """Export a policy version body with checksum metadata."""

        organization_id = _require_organization_id(current_user)
        repository = PolicyRepository(_audit_database().connect(), organization_id)
        policy_row = repository.get_policy(policy_id)
        if policy_row is None:
            raise HTTPException(status_code=404, detail="Policy not found.")
        version_row = repository.latest_export_version(policy_id, version_id)
        if version_row is None:
            raise HTTPException(status_code=404, detail="Policy version not found.")
        return policy_export_response(policy_row, version_row)

    @app.get(
        "/api/v1/discovery/scanners",
        response_model=list[DiscoveryScannerResponse],
        tags=["discovery"],
    )
    async def list_discovery_scanners(
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
    ) -> list[DiscoveryScannerResponse]:
        """List built-in discovery scanner metadata and availability."""

        return DiscoveryScannerRegistry.default().list_scanners()

    @app.post(
        "/api/v1/discovery/targets",
        response_model=DiscoveryTargetResponse,
        status_code=201,
        tags=["discovery"],
    )
    async def create_discovery_target(
        body: DiscoveryTargetCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> DiscoveryTargetResponse:
        """Create a tenant-scoped discovery scanner target."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = DiscoveryRepository(connection, organization_id, environment_id)
                return discovery_target_response(repository.create_target(body))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/discovery/targets",
        response_model=list[DiscoveryTargetResponse],
        tags=["discovery"],
    )
    async def list_discovery_targets(
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[DiscoveryTargetResponse]:
        """List tenant-scoped discovery scanner targets."""

        organization_id = _require_organization_id(current_user)
        repository = DiscoveryRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        return [discovery_target_response(row) for row in repository.list_targets()]

    @app.get(
        "/api/v1/discovery/findings",
        response_model=list[DiscoveryFindingResponse],
        tags=["discovery"],
    )
    async def list_discovery_findings(
        risk_level: str | None = Query(default=None),
        status: str | None = Query(default=None),
        source: str | None = Query(default=None),
        owner: str | None = Query(default=None),
        registry_match: str | None = Query(default=None),
        include_suppressed: bool = Query(default=False),
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[DiscoveryFindingResponse]:
        """List normalized discovery findings."""

        organization_id = _require_organization_id(current_user)
        repository = DiscoveryFindingRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        try:
            rows = repository.list_findings(
                risk_level=risk_level,
                status=status,
                source=source,
                owner=owner,
                registry_match=registry_match,
                include_suppressed=include_suppressed or status == "suppressed",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return [discovery_finding_response(repository, row) for row in rows]

    @app.get(
        "/api/v1/discovery/findings/{finding_id}",
        response_model=DiscoveryFindingResponse,
        tags=["discovery"],
    )
    async def get_discovery_finding(
        finding_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> DiscoveryFindingResponse:
        """Get one normalized discovery finding with evidence and risk factors."""

        organization_id = _require_organization_id(current_user)
        repository = DiscoveryFindingRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        row = repository.get_finding(finding_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Discovery finding not found.")
        return discovery_finding_response(repository, row, include_evidence=True)

    @app.post(
        "/api/v1/discovery/findings/{finding_id}/assign-owner",
        response_model=DiscoveryFindingResponse,
        tags=["discovery"],
    )
    async def assign_discovery_finding_owner(
        finding_id: str,
        body: DiscoveryAssignOwnerRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> DiscoveryFindingResponse:
        """Assign an owner to a normalized discovery finding."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = DiscoveryFindingRepository(connection, organization_id, environment_id)
                row = repository.assign_owner(
                    finding_id,
                    body.owner_user_id,
                    actor_id=current_user.id,
                )
                AuditEventRepository(connection).insert(
                    _discovery_finding_action_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        finding=row,
                        action_type="assign_owner",
                        correlation_id=context.correlation_id,
                    )
                )
                return discovery_finding_response(repository, row, include_evidence=True)
        except DiscoveryFindingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/discovery/findings/{finding_id}/suppress",
        response_model=DiscoveryFindingResponse,
        tags=["discovery"],
    )
    async def suppress_discovery_finding(
        finding_id: str,
        body: DiscoverySuppressRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> DiscoveryFindingResponse:
        """Suppress a discovery finding with an operator reason."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = DiscoveryFindingRepository(connection, organization_id, environment_id)
                row = repository.suppress(
                    finding_id,
                    reason=body.reason,
                    expires_at=body.expires_at,
                    actor_id=current_user.id,
                )
                AuditEventRepository(connection).insert(
                    _discovery_finding_action_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        finding=row,
                        action_type="suppress",
                        correlation_id=context.correlation_id,
                    )
                )
                return discovery_finding_response(repository, row, include_evidence=True)
        except DiscoveryFindingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/discovery/findings/{finding_id}/mark-decommissioned",
        response_model=DiscoveryFindingResponse,
        tags=["discovery"],
    )
    async def mark_discovery_finding_decommissioned(
        finding_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> DiscoveryFindingResponse:
        """Mark a discovery finding as decommissioned."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = DiscoveryFindingRepository(connection, organization_id, environment_id)
                row = repository.mark_decommissioned(finding_id, actor_id=current_user.id)
                AuditEventRepository(connection).insert(
                    _discovery_finding_action_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        finding=row,
                        action_type="mark_decommissioned",
                        correlation_id=context.correlation_id,
                    )
                )
                return discovery_finding_response(repository, row, include_evidence=True)
        except DiscoveryFindingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/discovery/findings/{finding_id}/register-agent",
        response_model=DiscoveryFindingResponse,
        tags=["discovery"],
    )
    async def register_discovery_finding_as_agent(
        finding_id: str,
        body: DiscoveryRegisterAgentRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> DiscoveryFindingResponse:
        """Create an agent registration draft from a discovery finding."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                findings = DiscoveryFindingRepository(connection, organization_id, environment_id)
                finding = findings.get_finding(finding_id)
                if finding is None:
                    raise DiscoveryFindingNotFoundError("Discovery finding not found.")
                draft = AgentRegistryRepository(
                    connection,
                    organization_id,
                    environment_id,
                ).create_registration_draft(
                    AgentRegistrationDraftCreate(
                        name=finding["detected_name"],
                        owner_user_id=body.owner_user_id,
                        sponsor_user_id=body.sponsor_user_id,
                        framework=body.framework or finding["agent_type"],
                        runtime_type=body.runtime_type,
                        description=f"Discovered from {finding['source'] or 'discovery scan'}",
                        endpoint_url=finding["endpoint_url"],
                    ),
                    created_by=current_user.id,
                )
                row = findings.link_registration_draft(
                    finding_id,
                    agent_id=draft["id"],
                    actor_id=current_user.id,
                )
                audit = AuditEventRepository(connection)
                audit.insert(
                    _agent_registration_audit_event(
                        row=draft,
                        actor_id=current_user.id,
                        event_type="agent.registration_draft.created",
                        correlation_id=context.correlation_id,
                    )
                )
                audit.insert(
                    _discovery_finding_action_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        finding=row,
                        action_type="register_agent",
                        correlation_id=context.correlation_id,
                    )
                )
                return discovery_finding_response(findings, row, include_evidence=True)
        except DiscoveryFindingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DuplicateAgentNameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/discovery/reconcile-run/{run_id}",
        response_model=list[DiscoveryFindingResponse],
        tags=["discovery"],
    )
    async def reconcile_discovery_run(
        run_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[DiscoveryFindingResponse]:
        """Normalize, risk score, and registry-reconcile raw findings for a run."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = DiscoveryFindingRepository(connection, organization_id, environment_id)
            normalized = repository.reconcile_run(run_id)
            for finding in normalized:
                repository.score_finding(finding["id"])
            reconciled = repository.reconcile_registry()
            normalized_ids = {finding["id"] for finding in normalized}
            return [
                discovery_finding_response(repository, row, include_evidence=True)
                for row in reconciled
                if row["id"] in normalized_ids
            ]

    @app.patch(
        "/api/v1/discovery/targets/{target_id}/schedule",
        response_model=DiscoveryTargetResponse,
        tags=["discovery"],
    )
    async def patch_discovery_target_schedule(
        target_id: str,
        body: DiscoveryTargetSchedulePatch,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> DiscoveryTargetResponse:
        """Patch hourly/daily/manual scheduling controls for a target."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = DiscoveryRepository(connection, organization_id, environment_id)
                return discovery_target_response(
                    repository.update_target_schedule(target_id, body)
                )
        except DiscoveryTargetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/discovery/runs",
        response_model=DiscoveryRunResponse,
        status_code=201,
        tags=["discovery"],
    )
    async def create_discovery_run(
        body: DiscoveryRunCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> DiscoveryRunResponse:
        """Run a discovery scanner target and persist raw findings."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = DiscoveryRepository(connection, organization_id, environment_id)
                runner = DiscoveryScanRunner(repository)
                target = repository.get_target(body.target_id)
                if target is None:
                    raise DiscoveryTargetNotFoundError("Discovery target not found.")
                run = repository.create_run(target)
                audit = AuditEventRepository(connection)
                audit.insert(
                    _discovery_scan_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="discovery.scan.started",
                        actor_id=current_user.id,
                        run=run,
                        correlation_id=context.correlation_id,
                    )
                )
                completed = await runner.run_created_target(target, run)
                audit.insert(
                    _discovery_scan_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type=(
                            "discovery.scan.completed"
                            if completed["status"] == "succeeded"
                            else "discovery.scan.failed"
                        ),
                        actor_id=current_user.id,
                        run=completed,
                        correlation_id=context.correlation_id,
                    )
                )
                return discovery_run_response(repository, completed, include_findings=True)
        except DiscoveryTargetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/discovery/runs",
        response_model=list[DiscoveryRunResponse],
        tags=["discovery"],
    )
    async def list_discovery_runs(
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[DiscoveryRunResponse]:
        """List discovery scan runs for the selected environment."""

        organization_id = _require_organization_id(current_user)
        repository = DiscoveryRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        return [discovery_run_response(repository, row) for row in repository.list_runs()]

    @app.get(
        "/api/v1/discovery/runs/{run_id}",
        response_model=DiscoveryRunResponse,
        tags=["discovery"],
    )
    async def get_discovery_run(
        run_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> DiscoveryRunResponse:
        """Get one discovery scan run with raw findings."""

        organization_id = _require_organization_id(current_user)
        repository = DiscoveryRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        row = repository.get_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Discovery run not found.")
        return discovery_run_response(repository, row, include_findings=True)

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
                if body.job_type == "demo.noop":
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
                elif body.job_type == "discovery.scan":
                    target_id = str(body.payload.get("target_id") or "").strip()
                    if not target_id:
                        raise HTTPException(
                            status_code=400,
                            detail="payload.target_id is required for discovery.scan.",
                        )
                    jobs.mark_running(created["id"])
                    discovery_repository = DiscoveryRepository(
                        connection,
                        organization_id,
                        environment_id,
                    )
                    target = discovery_repository.get_target(target_id)
                    if target is None:
                        raise HTTPException(status_code=404, detail="Discovery target not found.")
                    run = discovery_repository.create_run(target)
                    audit.insert(
                        _discovery_scan_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            event_type="discovery.scan.started",
                            actor_id=current_user.id,
                            run=run,
                            correlation_id=None,
                        )
                    )
                    completed_run = await DiscoveryScanRunner(
                        discovery_repository
                    ).run_created_target(target, run)
                    terminal_event = {
                        "succeeded": "discovery.scan.completed",
                        "skipped": "discovery.scan.skipped",
                    }.get(completed_run["status"], "discovery.scan.failed")
                    audit.insert(
                        _discovery_scan_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            event_type=terminal_event,
                            actor_id=current_user.id,
                            run=completed_run,
                            correlation_id=None,
                        )
                    )
                    summary = json.loads(completed_run["summary_json"])
                    job_result = {
                        "ok": completed_run["status"] == "succeeded",
                        "discovery_run_id": completed_run["id"],
                        "discovery_status": completed_run["status"],
                        "raw_finding_count": summary.get("raw_finding_count", 0),
                    }
                    if completed_run["status"] == "failed":
                        completed = jobs.mark_failed(
                            created["id"],
                            error_message=completed_run["error_message"]
                            or "Discovery scan failed.",
                            logs=["queued", "started discovery.scan", "failed discovery.scan"],
                        )
                    else:
                        completed = jobs.mark_succeeded(
                            created["id"],
                            logs=["queued", "started discovery.scan", "completed discovery.scan"],
                            metrics={"raw_finding_count": job_result["raw_finding_count"]},
                            result=job_result,
                        )
                    _insert_job_audit_event(
                        audit,
                        organization_id=organization_id,
                        environment_id=environment_id,
                        job_id=completed["id"],
                        job_type=completed["job_type"],
                        status=completed["status"],
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="Only demo.noop can run immediately in the foundation runtime.",
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

    @app.post(
        "/api/v1/agents/registration-drafts",
        response_model=AgentRegistrationDraftResponse,
        status_code=201,
        tags=["agents"],
    )
    async def create_agent_registration_draft(
        body: AgentRegistrationDraftCreate,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentRegistrationDraftResponse:
        """Create a tenant-scoped agent registration draft."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                agents = AgentRegistryRepository(connection, organization_id, environment_id)
                row = agents.create_registration_draft(body, created_by=current_user.id)
                AuditEventRepository(connection).insert(
                    _agent_registration_audit_event(
                        row=row,
                        actor_id=current_user.id,
                        event_type="agent.registration_draft.created",
                        correlation_id=context.correlation_id,
                    )
                )
                return agent_registration_draft_response(row)
        except DuplicateAgentNameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.patch(
        "/api/v1/agents/registration-drafts/{draft_id}",
        response_model=AgentRegistrationDraftResponse,
        tags=["agents"],
    )
    async def patch_agent_registration_draft(
        draft_id: str,
        body: AgentRegistrationDraftPatch,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentRegistrationDraftResponse:
        """Patch a tenant-scoped agent registration draft."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                row = AgentRegistryRepository(
                    connection, organization_id, environment_id
                ).update_registration_draft(draft_id, body)
                agents = AgentRegistryRepository(connection, organization_id, environment_id)
                if body.capabilities is not None:
                    agents.replace_capabilities(
                        draft_id,
                        body.capabilities,
                        requested_by=current_user.id,
                    )
                if body.policy_selections is not None:
                    agents.replace_policy_selections(draft_id, body.policy_selections)
                return agent_registration_draft_response(
                    row,
                    capabilities=agents.list_capabilities(draft_id),
                    policy_selections=agents.list_policy_selections(draft_id),
                )
        except DuplicateAgentNameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except AgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/agents/registration-drafts/{draft_id}/simulate",
        response_model=AgentRegistrationSimulationResponse,
        tags=["agents"],
    )
    async def simulate_agent_registration_draft(
        draft_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentRegistrationSimulationResponse:
        """Simulate the first requested draft capability against selected policies."""

        organization_id = _require_organization_id(current_user)
        agents = AgentRegistryRepository(_audit_database().connect(), organization_id, environment_id)
        draft = agents.get(draft_id)
        if draft is None or draft["status"] != "draft":
            raise HTTPException(status_code=404, detail="Registration draft not found.")
        capabilities = [
            row["capability_name"] for row in agents.list_capabilities(draft_id)
        ]
        policy_ids = [
            row["policy_id"] for row in agents.list_policy_selections(draft_id)
        ]
        return simulate_registration_action(
            agent_id=draft_id,
            capability_names=capabilities,
            policy_ids=policy_ids,
        )

    @app.get("/api/v1/agents", response_model=list[AgentInventorySummary], tags=["agents"])
    async def list_agents(
        status: str | None = None,
        owner_user_id: str | None = None,
        sponsor_user_id: str | None = None,
        framework: str | None = None,
        protocol: str | None = None,
        trust_tier: str | None = None,
        capability: str | None = None,
        environment_filter: str | None = Query(default=None, alias="environment_id"),
        sort: str = Query(default="name"),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[AgentInventorySummary]:
        """List tenant-scoped agent inventory summaries."""

        organization_id = _require_organization_id(current_user)
        if environment_filter is not None and environment_filter != environment_id:
            return []
        repository = AgentRegistryRepository(
            _audit_database().connect(), organization_id, environment_id
        )
        rows = repository.list_inventory(
            limit=limit,
            offset=offset,
            status=status,
            owner_user_id=owner_user_id,
            sponsor_user_id=sponsor_user_id,
            framework=framework,
            protocol=protocol,
            trust_tier=trust_tier,
            capability=capability,
            environment_filter=environment_filter,
            sort=sort,
        )
        return [agent_inventory_summary(row) for row in rows]

    @app.get("/api/v1/agents/{agent_id}", response_model=AgentDetailResponse, tags=["agents"])
    async def get_agent_detail(
        agent_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentDetailResponse:
        """Return aggregate detail for one accessible agent."""

        organization_id = _require_organization_id(current_user)
        repository = AgentRegistryRepository(
            _audit_database().connect(), organization_id, environment_id
        )
        row = repository.get_inventory_summary(agent_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Agent not found.")
        return agent_detail_response(repository, row)

    @app.get(
        "/api/v1/agents/{agent_id}/credentials",
        response_model=list[AgentCredentialResponse],
        tags=["agents"],
    )
    async def list_agent_credentials(
        agent_id: str,
        status: str | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[AgentCredentialResponse]:
        """List credential metadata for one accessible agent without token hashes."""

        organization_id = _require_organization_id(current_user)
        repository = AgentCredentialRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        try:
            rows = repository.list_for_agent(agent_id, status=status)
        except AgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [agent_credential_response(repository, row) for row in rows]

    @app.post(
        "/api/v1/agents/{agent_id}/credentials",
        response_model=AgentCredentialIssueResponse,
        status_code=201,
        tags=["agents"],
    )
    async def issue_agent_credential(
        agent_id: str,
        body: AgentCredentialIssueRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentCredentialIssueResponse:
        """Issue a one-time credential token for an accessible active agent."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = AgentCredentialRepository(
                    connection,
                    organization_id,
                    environment_id,
                )
                agent_did = repository.identity_did(agent_id)
                repository.validate_scopes(agent_id, body.scopes)
                issued = AgentCredentialIssuer(default_ttl_seconds=body.ttl_seconds).issue(
                    agent_did=agent_did,
                    scopes=body.scopes,
                    ttl_seconds=body.ttl_seconds,
                    issued_for=body.issued_for,
                )
                row = repository.create_metadata(
                    agent_id=agent_id,
                    credential_type=body.credential_type,
                    raw_token=issued.token,
                    issuer=body.issuer,
                    expires_at=issued.expires_at,
                    scopes=body.scopes,
                    metadata_json={
                        "agent_did": agent_did,
                        "agentmesh_credential_id": issued.agentmesh_credential_id,
                        "issued_for": body.issued_for,
                        "ttl_seconds": issued.ttl_seconds,
                    },
                    status=issued.status,
                    issued_at=issued.issued_at,
                )
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="agent.credential.issued",
                        source_component="agent-registry",
                        actor_type="user",
                        actor_id=current_user.id,
                        agent_id=agent_id,
                        resource_type="agent_credential",
                        resource_id=row["id"],
                        correlation_id=context.correlation_id,
                        payload_json={
                            "credential_type": body.credential_type,
                            "issuer": body.issuer,
                            "status": row["status"],
                            "expires_at": row["expires_at"],
                            "scope_count": len(body.scopes),
                        },
                    )
                )
                return AgentCredentialIssueResponse(
                    credential=agent_credential_response(repository, row),
                    token=issued.token,
                    bearer_token=issued.bearer_token,
                )
        except AgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _require_credential_reason(body: CredentialActionRequest | None, action: str) -> str:
        reason = body.reason if body else None
        if not reason:
            raise HTTPException(status_code=422, detail=f"Reason is required to {action}.")
        return reason

    def _credential_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        event_type: str,
        actor_id: str,
        agent_id: str,
        credential_id: str,
        correlation_id: str | None,
        payload_json: dict[str, Any],
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="agent-registry",
            actor_type="user",
            actor_id=actor_id,
            agent_id=agent_id,
            resource_type="agent_credential",
            resource_id=credential_id,
            correlation_id=correlation_id,
            payload_json=payload_json,
        )

    @app.post(
        "/api/v1/credentials/{credential_id}/rotate",
        response_model=AgentCredentialRotationResponse,
        tags=["agents"],
    )
    async def rotate_agent_credential(
        credential_id: str,
        request: Request,
        body: CredentialActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentCredentialRotationResponse:
        """Rotate an active credential and return replacement token material once."""

        reason = _require_credential_reason(body, "rotate a credential")
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = AgentCredentialRepository(
                    connection,
                    organization_id,
                    environment_id,
                )
                original = repository.get(credential_id)
                if original is None:
                    raise CredentialNotFoundError("Credential not found.")
                if original["status"] != "active":
                    raise ValueError("Only active credentials can be rotated.")
                agent_id = original["agent_id"]
                scopes = repository.scope_requests(credential_id)
                metadata = json.loads(original["metadata_json"])
                ttl_seconds = int(metadata.get("ttl_seconds") or 900)
                agent_did = repository.identity_did(agent_id)
                issued = AgentCredentialIssuer(default_ttl_seconds=ttl_seconds).issue(
                    agent_did=agent_did,
                    scopes=scopes,
                    ttl_seconds=ttl_seconds,
                    issued_for=metadata.get("issued_for"),
                )
                previous = repository.revoke(
                    credential_id,
                    reason=reason,
                    actor_id=current_user.id,
                    publication_type="rotation",
                )
                created = repository.create_metadata(
                    agent_id=agent_id,
                    credential_type=original["credential_type"],
                    raw_token=issued.token,
                    issuer=original["issuer"],
                    expires_at=issued.expires_at,
                    scopes=scopes,
                    metadata_json={
                        "agent_did": agent_did,
                        "agentmesh_credential_id": issued.agentmesh_credential_id,
                        "issued_for": metadata.get("issued_for"),
                        "rotated_from": credential_id,
                        "ttl_seconds": issued.ttl_seconds,
                    },
                    status=issued.status,
                    issued_at=issued.issued_at,
                )
                rotation = repository.record_rotation(
                    agent_id=agent_id,
                    previous_credential_id=credential_id,
                    new_credential_id=created["id"],
                    reason=reason,
                    requested_by=current_user.id,
                )
                repository.record_lifecycle_evidence(
                    agent_id=agent_id,
                    actor_id=current_user.id,
                    reason="credential rotated",
                    metadata_json={
                        "previous_credential_id": credential_id,
                        "new_credential_id": created["id"],
                        "rotation_id": rotation["id"],
                        "reason": reason,
                    },
                )
                audit = AuditEventRepository(connection)
                audit.insert(
                    _credential_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="agent.credential.rotated",
                        actor_id=current_user.id,
                        agent_id=agent_id,
                        credential_id=created["id"],
                        correlation_id=context.correlation_id,
                        payload_json={
                            "previous_credential_id": credential_id,
                            "new_credential_id": created["id"],
                            "rotation_id": rotation["id"],
                            "reason": reason,
                        },
                    )
                )
                audit.insert(
                    _credential_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="agent.credential.revocation_published",
                        actor_id=current_user.id,
                        agent_id=agent_id,
                        credential_id=credential_id,
                        correlation_id=context.correlation_id,
                        payload_json={
                            "credential_id": credential_id,
                            "publication_type": "rotation",
                            "reason": reason,
                            "targets": ["agent-gateways", "agent-runtime"],
                        },
                    )
                )
                return AgentCredentialRotationResponse(
                    rotation_id=rotation["id"],
                    previous_credential=agent_credential_response(repository, previous),
                    credential=agent_credential_response(repository, created),
                    token=issued.token,
                    bearer_token=issued.bearer_token,
                )
        except (CredentialNotFoundError, AgentNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/credentials/{credential_id}/revoke",
        response_model=AgentCredentialResponse,
        tags=["agents"],
    )
    async def revoke_agent_credential(
        credential_id: str,
        request: Request,
        body: CredentialActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentCredentialResponse:
        """Revoke an active credential and publish revocation metadata."""

        reason = _require_credential_reason(body, "revoke a credential")
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = AgentCredentialRepository(
                    connection,
                    organization_id,
                    environment_id,
                )
                row = repository.revoke(
                    credential_id,
                    reason=reason,
                    actor_id=current_user.id,
                    publication_type="revocation",
                )
                agent_id = row["agent_id"]
                repository.record_lifecycle_evidence(
                    agent_id=agent_id,
                    actor_id=current_user.id,
                    reason="credential revoked",
                    metadata_json={"credential_id": credential_id, "reason": reason},
                )
                audit = AuditEventRepository(connection)
                audit.insert(
                    _credential_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="agent.credential.revoked",
                        actor_id=current_user.id,
                        agent_id=agent_id,
                        credential_id=credential_id,
                        correlation_id=context.correlation_id,
                        payload_json={"credential_id": credential_id, "reason": reason},
                    )
                )
                audit.insert(
                    _credential_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="agent.credential.revocation_published",
                        actor_id=current_user.id,
                        agent_id=agent_id,
                        credential_id=credential_id,
                        correlation_id=context.correlation_id,
                        payload_json={
                            "credential_id": credential_id,
                            "publication_type": "revocation",
                            "reason": reason,
                            "targets": ["agent-gateways", "agent-runtime"],
                        },
                    )
                )
                return agent_credential_response(repository, row)
        except (CredentialNotFoundError, AgentNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/credentials/expiring",
        response_model=list[AgentCredentialResponse],
        tags=["agents"],
    )
    async def list_expiring_credentials(
        threshold_hours: int = Query(default=24, ge=1, le=720),
        now: str | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[AgentCredentialResponse]:
        """List credentials expiring within the threshold for the selected environment."""

        organization_id = _require_organization_id(current_user)
        repository = AgentCredentialRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        rows = repository.list_expiring(threshold_hours=threshold_hours, now=now)
        return [agent_credential_response(repository, row) for row in rows]

    @app.post(
        "/api/v1/credentials/{credential_id}/verify",
        response_model=CredentialVerifyResponse,
        tags=["agents"],
    )
    async def verify_agent_credential(
        credential_id: str,
        body: CredentialVerifyRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> CredentialVerifyResponse:
        """Verify a submitted token against credential metadata without exposing hashes."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                result = AgentCredentialRepository(
                    connection,
                    organization_id,
                    environment_id,
                ).verify_token(credential_id, raw_token=body.token)
                return CredentialVerifyResponse(**result)
        except CredentialNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/agents/{agent_id}/timeline",
        response_model=list[AgentTimelineEvent],
        tags=["agents"],
    )
    async def get_agent_timeline(
        agent_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[AgentTimelineEvent]:
        """Return combined lifecycle and audit timeline events for one agent."""

        organization_id = _require_organization_id(current_user)
        database_for_agents = _audit_database()
        repository = AgentRegistryRepository(database_for_agents.connect(), organization_id, environment_id)
        if repository.get(agent_id) is None:
            raise HTTPException(status_code=404, detail="Agent not found.")
        timeline = [
            lifecycle_timeline_event(row) for row in repository.lifecycle_events(agent_id)
        ]
        audit_events = AuditEventRepository(database_for_agents.connect()).query(
            AuditEventQuery(
                organization_id=organization_id,
                agent_id=agent_id,
                limit=100,
            )
        )
        for event in audit_events:
            timeline.append(
                AgentTimelineEvent(
                    id=event.id,
                    source="audit",
                    event_type=event.event_type,
                    created_at=event.created_at,
                    actor_id=event.actor_id,
                    payload_json=event.payload_json,
                )
            )
        return sorted(timeline, key=lambda event: (event.created_at, event.id))

    @app.get(
        "/api/v1/agents/{agent_id}/audit",
        response_model=list[AuditEventEnvelope],
        tags=["agents"],
    )
    async def get_agent_audit(
        agent_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[AuditEventEnvelope]:
        """Return audit events for one accessible agent."""

        organization_id = _require_organization_id(current_user)
        database_for_agents = _audit_database()
        repository = AgentRegistryRepository(database_for_agents.connect(), organization_id, environment_id)
        if repository.get(agent_id) is None:
            raise HTTPException(status_code=404, detail="Agent not found.")
        return AuditEventRepository(database_for_agents.connect()).query(
            AuditEventQuery(
                organization_id=organization_id,
                agent_id=agent_id,
                limit=100,
            )
        )

    @app.patch("/api/v1/agents/{agent_id}", response_model=AgentInventorySummary, tags=["agents"])
    async def patch_agent(
        agent_id: str,
        body: AgentPatchRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        """Patch editable fields on an accessible agent."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                row = AgentRegistryRepository(
                    connection, organization_id, environment_id
                ).patch_agent(agent_id, body)
                return agent_inventory_summary(row)
        except AgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/agents/registration-drafts/{draft_id}/identity",
        response_model=AgentIdentityCreateResponse,
        tags=["agents"],
    )
    async def create_agent_identity(
        draft_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentIdentityCreateResponse:
        """Create an AgentMesh identity for a draft and return bootstrap material once."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            agents = AgentRegistryRepository(connection, organization_id, environment_id)
            draft = agents.get(draft_id)
            if draft is None or draft["status"] != "draft":
                raise HTTPException(status_code=404, detail="Registration draft not found.")
            existing = agents.get_identity(draft_id)
            if existing is not None:
                return AgentIdentityCreateResponse(
                    identity=agent_identity_response(existing),
                    bootstrap=None,
                )
            created = AgentIdentityAdapter().create_identity(
                name=draft["name"],
                sponsor_email=_resolve_sponsor_email(draft, current_user, connection),
                organization=organization_id,
                description=draft["description"],
            )
            row = agents.create_identity(draft_id, created)
            return AgentIdentityCreateResponse(
                identity=agent_identity_response(row),
                bootstrap=created.bootstrap,
            )

    @app.post(
        "/api/v1/agents/registration-drafts/{draft_id}/submit",
        response_model=AgentRegistrationDraftResponse,
        tags=["agents"],
    )
    async def submit_agent_registration_draft(
        draft_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentRegistrationDraftResponse:
        """Submit a draft agent for approval."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                agents = AgentRegistryRepository(connection, organization_id, environment_id)
                if agents.get_identity(draft_id) is None:
                    raise HTTPException(status_code=400, detail="Agent identity is required before submit.")
                if not agents.list_capabilities(draft_id):
                    raise HTTPException(
                        status_code=400,
                        detail="At least one requested capability is required before submit.",
                    )
                row = agents.transition_status(
                    draft_id,
                    next_status="pending_approval",
                    actor_id=current_user.id,
                    reason="registration submitted",
                )
                AuditEventRepository(connection).insert(
                    _agent_registration_audit_event(
                        row=row,
                        actor_id=current_user.id,
                        event_type="agent.registration_submitted",
                        correlation_id=context.correlation_id,
                    )
                )
                return agent_registration_draft_response(
                    row,
                    capabilities=agents.list_capabilities(draft_id),
                    policy_selections=agents.list_policy_selections(draft_id),
                )
        except AgentLifecycleTransitionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/agents/{agent_id}/approve",
        response_model=AgentRegistrationDraftResponse,
        tags=["agents"],
    )
    async def approve_agent_registration(
        agent_id: str,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentRegistrationDraftResponse:
        """Approve a submitted agent and its pending capabilities."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                agents = AgentRegistryRepository(connection, organization_id, environment_id)
                row = agents.transition_status(
                    agent_id,
                    next_status="provisioned",
                    actor_id=current_user.id,
                    reason=body.reason if body else "registration approved",
                )
                agents.approve_pending_capabilities(agent_id, approved_by=current_user.id)
                AuditEventRepository(connection).insert(
                    agent_lifecycle_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        agent_id=agent_id,
                        lifecycle_state="provisioned",
                        actor_id=current_user.id,
                    )
                )
                return agent_registration_draft_response(
                    row,
                    capabilities=agents.list_capabilities(agent_id),
                    policy_selections=agents.list_policy_selections(agent_id),
                )
        except AgentLifecycleTransitionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/agents/{agent_id}/activate",
        response_model=AgentRegistrationDraftResponse,
        tags=["agents"],
    )
    async def activate_agent_registration(
        agent_id: str,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentRegistrationDraftResponse:
        """Activate an approved agent and queue initial credential issuance."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                agents = AgentRegistryRepository(connection, organization_id, environment_id)
                row = agents.transition_status(
                    agent_id,
                    next_status="active",
                    actor_id=current_user.id,
                    reason=body.reason if body else "registration activated",
                    metadata_json='{"credential_task":"pending"}',
                )
                credential_job = JobStateRepository(connection).create_job(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    job_type="agent.credential.issue",
                    payload={"agent_id": agent_id},
                    max_attempts=3,
                )
                audit = AuditEventRepository(connection)
                audit.insert(
                    agent_lifecycle_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        agent_id=agent_id,
                        lifecycle_state="active",
                        actor_id=current_user.id,
                    )
                )
                _insert_job_audit_event(
                    audit,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    job_id=credential_job["id"],
                    job_type=credential_job["job_type"],
                    status=credential_job["status"],
                )
                return agent_registration_draft_response(
                    row,
                    capabilities=agents.list_capabilities(agent_id),
                    policy_selections=agents.list_policy_selections(agent_id),
                )
        except AgentLifecycleTransitionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    def _require_reason(body: AgentLifecycleActionRequest | None, action: str) -> str:
        reason = body.reason if body else None
        if not reason:
            raise HTTPException(status_code=422, detail=f"Reason is required to {action}.")
        return reason

    @app.post(
        "/api/v1/agents/{agent_id}/reject",
        response_model=AgentInventorySummary,
        tags=["agents"],
    )
    async def reject_agent(
        agent_id: str,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                row = AgentRegistryRepository(connection, organization_id, environment_id).transition_status(
                    agent_id,
                    next_status="rejected",
                    actor_id=current_user.id,
                    reason=body.reason if body else "registration rejected",
                )
                AuditEventRepository(connection).insert(
                    agent_lifecycle_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        agent_id=agent_id,
                        lifecycle_state="rejected",
                        actor_id=current_user.id,
                    )
                )
                return agent_inventory_summary(
                    AgentRegistryRepository(connection, organization_id, environment_id).get_inventory_summary(agent_id)
                    or row
                )
        except (AgentLifecycleTransitionError, AgentNotFoundError) as exc:
            raise HTTPException(status_code=400 if isinstance(exc, AgentLifecycleTransitionError) else 404, detail=str(exc)) from exc

    @app.post("/api/v1/agents/{agent_id}/suspend", response_model=AgentInventorySummary, tags=["agents"])
    async def suspend_agent(
        agent_id: str,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        reason = _require_reason(body, "suspend an agent")
        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = AgentRegistryRepository(connection, organization_id, environment_id)
                row = repository.transition_status(
                    agent_id,
                    next_status="suspended",
                    actor_id=current_user.id,
                    reason=reason,
                )
                AuditEventRepository(connection).insert(
                    agent_lifecycle_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        agent_id=agent_id,
                        lifecycle_state="suspended",
                        actor_id=current_user.id,
                    )
                )
                return agent_inventory_summary(repository.get_inventory_summary(agent_id) or row)
        except (AgentLifecycleTransitionError, AgentNotFoundError) as exc:
            raise HTTPException(status_code=400 if isinstance(exc, AgentLifecycleTransitionError) else 404, detail=str(exc)) from exc

    @app.post("/api/v1/agents/{agent_id}/resume", response_model=AgentInventorySummary, tags=["agents"])
    async def resume_agent(
        agent_id: str,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = AgentRegistryRepository(connection, organization_id, environment_id)
                row = repository.transition_status(
                    agent_id,
                    next_status="active",
                    actor_id=current_user.id,
                    reason=body.reason if body else "agent resumed",
                )
                AuditEventRepository(connection).insert(
                    agent_lifecycle_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        agent_id=agent_id,
                        lifecycle_state="active",
                        actor_id=current_user.id,
                    )
                )
                return agent_inventory_summary(repository.get_inventory_summary(agent_id) or row)
        except (AgentLifecycleTransitionError, AgentNotFoundError) as exc:
            raise HTTPException(status_code=400 if isinstance(exc, AgentLifecycleTransitionError) else 404, detail=str(exc)) from exc

    @app.post("/api/v1/agents/{agent_id}/change-owner", response_model=AgentInventorySummary, tags=["agents"])
    async def change_agent_owner(
        agent_id: str,
        body: AgentOwnerChangeRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = AgentRegistryRepository(connection, organization_id, environment_id)
            row = repository.change_owner(
                agent_id,
                new_owner_user_id=body.new_owner_user_id,
                actor_id=current_user.id,
                reason=body.reason,
            )
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="agent.owner_changed",
                    source_component="agent-registry",
                    actor_type="user",
                    actor_id=current_user.id,
                    agent_id=agent_id,
                    resource_type="agent",
                    resource_id=agent_id,
                    payload_json={"new_owner_user_id": body.new_owner_user_id},
                )
            )
            return agent_inventory_summary(repository.get_inventory_summary(agent_id) or row)

    @app.post("/api/v1/agents/{agent_id}/decommission", response_model=AgentInventorySummary, tags=["agents"])
    async def decommission_agent(
        agent_id: str,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        reason = _require_reason(body, "decommission an agent")
        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = AgentRegistryRepository(connection, organization_id, environment_id)
                repository.transition_status(
                    agent_id,
                    next_status="decommissioning",
                    actor_id=current_user.id,
                    reason=reason,
                )
                row = repository.transition_status(
                    agent_id,
                    next_status="decommissioned",
                    actor_id=current_user.id,
                    reason=reason,
                )
                AuditEventRepository(connection).insert(
                    agent_lifecycle_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        agent_id=agent_id,
                        lifecycle_state="decommissioned",
                        actor_id=current_user.id,
                    )
                )
                return agent_inventory_summary(repository.get_inventory_summary(agent_id) or row)
        except (AgentLifecycleTransitionError, AgentNotFoundError) as exc:
            raise HTTPException(status_code=400 if isinstance(exc, AgentLifecycleTransitionError) else 404, detail=str(exc)) from exc

    @app.post("/api/v1/agents/{agent_id}/heartbeat", response_model=AgentInventorySummary, tags=["agents"])
    async def record_agent_heartbeat(
        agent_id: str,
        body: AgentHeartbeatRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = AgentRegistryRepository(connection, organization_id, environment_id)
            row = repository.record_heartbeat(
                agent_id,
                status=body.status,
                metadata_json=body.metadata_json,
            )
            return agent_inventory_summary(repository.get_inventory_summary(agent_id) or row)

    @app.post(
        "/api/v1/agents/orphan-detection/run",
        response_model=OrphanDetectionRunResponse,
        tags=["agents"],
    )
    async def run_orphan_detection(
        body: OrphanDetectionRunRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> OrphanDetectionRunResponse:
        organization_id = _require_organization_id(current_user)
        orphaned_ids: list[str] = []
        with _audit_database().transaction() as connection:
            repository = AgentRegistryRepository(connection, organization_id, environment_id)
            candidates = repository.orphan_candidates(threshold_hours=body.threshold_hours)
            audit = AuditEventRepository(connection)
            for candidate in candidates:
                try:
                    repository.transition_status(
                        candidate["id"],
                        next_status="orphaned",
                        actor_id=current_user.id,
                        reason="orphan detection",
                    )
                except AgentLifecycleTransitionError:
                    continue
                orphaned_ids.append(candidate["id"])
                audit.insert(
                    agent_lifecycle_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        agent_id=candidate["id"],
                        lifecycle_state="orphaned",
                        actor_id=current_user.id,
                    )
                )
        return OrphanDetectionRunResponse(
            processed_count=len(orphaned_ids),
            orphaned_agent_ids=orphaned_ids,
        )

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
