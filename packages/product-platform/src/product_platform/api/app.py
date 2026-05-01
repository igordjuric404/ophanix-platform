"""FastAPI application factory for the Ophanix product control plane."""

from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Any
from uuid import uuid4
from urllib.parse import parse_qs, urlparse

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
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
from product_platform.api.rbac import Permission, has_permission, require_permission
from product_platform.api.settings import Settings, load_settings
from product_platform.api.tenancy import (
    Environment,
    EnvironmentCreateRequest,
    Organization,
    TenantStore,
    require_environment_context,
)
from product_platform.artifacts.models import (
    ArtifactAttestationCreateRequest,
    ArtifactAttestationResponse,
    ArtifactCreateRequest,
    ArtifactDownloadResponse,
    ArtifactLinkCreateRequest,
    ArtifactLinkResponse,
    ArtifactResponse,
)
from product_platform.artifacts.repository import (
    ArtifactNotFoundError,
    ArtifactRepository,
    ArtifactValidationError,
    artifact_attestation_response,
    artifact_link_response,
    artifact_response,
)
from product_platform.artifacts.storage import ArtifactStorageError, LocalArtifactProvider
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
from product_platform.compliance.models import (
    AuditExportRequest,
    AuditExportResponse,
    ComplianceControlResponse,
    ComplianceFrameworkCreateRequest,
    ComplianceFrameworkResponse,
    ComplianceReportAttestationRequest,
    ComplianceReportAttestationResponse,
    ComplianceReportCreateRequest,
    ComplianceReportResponse,
    ComplianceViolationPatchRequest,
    ComplianceViolationResponse,
    ControlMappingCreateRequest,
    ControlMappingResponse,
    EvidenceItemResponse,
    EvidenceRecomputeResponse,
)
from product_platform.compliance.repository import (
    AuditExportRepository,
    ComplianceRepository,
    ComplianceReportNotFoundError,
    ComplianceReportValidationError,
    ComplianceResourceNotFoundError,
    ComplianceViolationNotFoundError,
    ComplianceViolationStateError,
    DuplicateComplianceResourceError,
    audit_export_response,
    control_mapping_response,
    control_response,
    evidence_response,
    framework_response,
    report_attestation_response,
    report_response,
    violation_response,
)
from product_platform.demo.baseline import demo_baseline_status
from product_platform.demo.models import (
    DemoBaselineStatusResponse,
    DemoResetRequest,
    DemoResetRunResponse,
    DemoRunResponse,
    DemoScenarioDetailResponse,
    DemoScenarioSummaryResponse,
)
from product_platform.demo.repository import (
    DemoScenarioNotFoundError,
    DemoScenarioRepository,
    demo_run_response,
    demo_scenario_summary_response,
)
from product_platform.demo.reset import (
    DemoEnvironmentResetService,
    DemoResetRepository,
    demo_reset_run_response,
)
from product_platform.demo.runner import DemoScenarioRunner, demo_run_audit_event
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
from product_platform.integrations.models import (
    FrameworkAgentLinkRequest,
    FrameworkAgentResponse,
    FrameworkInstanceCreateRequest,
    FrameworkInstancePatchRequest,
    FrameworkInstanceResponse,
    FrameworkIntegrationResponse,
    IntegrationHealthCheckCreateRequest,
    IntegrationHealthCheckResponse,
    ProviderCredentialCreateRequest,
    ProviderCredentialResponse,
)
from product_platform.integrations.repository import (
    FrameworkAgentNotFoundError,
    FrameworkAgentValidationError,
    FrameworkInstanceConfigError,
    FrameworkInstanceNotFoundError,
    FrameworkIntegrationNotFoundError,
    IntegrationRegistryRepository,
    ProviderCredentialNotFoundError,
    framework_agent_response,
    framework_instance_response,
    framework_integration_response,
    integration_health_check_response,
    provider_credential_response,
)
from product_platform.integrations.health import run_provider_health_test
from product_platform.integrations.secrets import DEFAULT_SECRET_PROVIDER, SecretProvider
from product_platform.mesh.models import (
    MeshHandoffCreateRequest,
    MeshHandoffResponse,
    MeshMessageCreateRequest,
    MeshMessageResponse,
    MeshTopologyResponse,
    ProtocolBridgeCreateRequest,
    ProtocolBridgeHealthCheckResponse,
    ProtocolBridgePatchRequest,
    ProtocolBridgeResponse,
    ProtocolBridgeRouteCreateRequest,
    ProtocolBridgeRouteResponse,
)
from product_platform.mesh.bridges import ProtocolBridgeHealthAdapter
from product_platform.mesh.repository import (
    MeshAgentNotFoundError,
    MeshRepository,
    ProtocolBridgeNotFoundError,
    ProtocolBridgeReferenceNotFoundError,
    mesh_handoff_response,
    mesh_message_response,
    protocol_bridge_health_check_response,
    protocol_bridge_response,
    protocol_bridge_route_response,
)
from product_platform.mesh.topology import MeshTopologyService
from product_platform.mcp.discovery import DemoMCPToolDiscoveryAdapter, normalize_tool_definition
from product_platform.mcp.models import (
    MCPApprovalDecisionRequest,
    MCPApprovalResponse,
    MCPFindingActionRequest,
    MCPFindingResponse,
    MCPProxyCallRequest,
    MCPRateLimitCreateRequest,
    MCPRateLimitResponse,
    MCPScanRunResponse,
    MCPServerCreateRequest,
    MCPServerPatchRequest,
    MCPServerResponse,
    MCPToolDiscoveryResponse,
    MCPToolCallResponse,
    MCPToolResponse,
)
from product_platform.mcp.proxy import (
    MCPApprovalDecisionError,
    MCPApprovalNotFoundError,
    MCPProxyDecisionService,
    MCPProxyReferenceError,
    MCPProxyRepository,
    mcp_approval_response,
    mcp_rate_limit_response,
    mcp_tool_call_response,
)
from product_platform.mcp.repository import (
    DuplicateMCPServerNameError,
    MCPFindingLifecycleError,
    MCPFindingNotFoundError,
    MCPRegistryReferenceError,
    MCPRegistryRepository,
    MCPServerNotFoundError,
    MCPToolSchemaChange,
    mcp_finding_response,
    mcp_scan_run_response,
    mcp_tool_response,
    mcp_tool_version_response,
    mcp_server_response,
)
from product_platform.mcp.scans import MCPScannerAdapter
from product_platform.marketplace.models import (
    PluginInstallationCreateRequest,
    PluginInstallationResponse,
    PluginImportRequest,
    PluginPolicyCheckRequest,
    PluginPolicyResultResponse,
    PluginQualityAssessmentResponse,
    PluginResponse,
    PluginReviewDecisionRequest,
    PluginReviewResponse,
    PluginReviewSubmitRequest,
    PluginSigningKeyCreateRequest,
    PluginSigningKeyResponse,
    PluginTrustEventResponse,
    PluginTrustRecomputeRequest,
)
from product_platform.marketplace.repository import (
    MarketplaceCatalogRepository,
    MarketplaceManifestError,
    PluginInstallationBlockedError,
    PluginInstallationNotFoundError,
    PluginInstallationStateError,
    PluginNotFoundError,
    PluginReviewNotFoundError,
    PluginReviewStateError,
    PluginSigningKeyNotFoundError,
    plugin_installation_response,
    plugin_policy_result_response,
    plugin_quality_assessment_response,
    plugin_response,
    plugin_review_response,
    plugin_signing_key_response,
    plugin_trust_event_response,
)
from product_platform.observability.models import (
    ChaosExperimentCreateRequest,
    ChaosExperimentResponse,
    ChaosRunCreateRequest,
    ChaosRunResponse,
    CostBudgetCreateRequest,
    CostBudgetResponse,
    CostDashboardResponse,
    CostEventCreateRequest,
    CostEventResponse,
    IncidentCreateRequest,
    IncidentFromEventRequest,
    IncidentResolveRequest,
    IncidentResponse,
    RolloutAdvanceRequest,
    RolloutCreateRequest,
    RolloutRollbackRequest,
    RolloutResponse,
    SloMeasurementCreateRequest,
    SloMeasurementResponse,
    SloObjectiveCreateRequest,
    SloObjectiveResponse,
)
from product_platform.observability.repository import (
    ChaosExperimentValidationError,
    ChaosExperimentNotFoundError,
    ChaosRunNotFoundError,
    IncidentNotFoundError,
    IncidentStateError,
    ObservabilityRepository,
    RolloutNotFoundError,
    SloObjectiveNotFoundError,
    chaos_experiment_response,
    chaos_run_response,
    cost_budget_response,
    cost_dashboard_response,
    cost_event_response,
    incident_response,
    rollout_response,
    slo_measurement_response,
    slo_objective_response,
)
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
    PolicyEvaluationRequest,
    PolicyEvaluationResponse,
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
from product_platform.policies.evaluation_repository import (
    PolicyEvaluationQuery,
    PolicyEvaluationRepository,
    policy_evaluation_response,
)
from product_platform.policies.evaluations import PolicyEvaluationAdapter
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
from product_platform.runtime.models import (
    RuntimeActionCreateRequest,
    RuntimeActionResponse,
    RuntimeRingDecisionResponse,
    RuntimeRingRuleCreateRequest,
    RuntimeRingRuleResponse,
    RuntimeSessionCreateRequest,
    RuntimeSessionEndRequest,
    RuntimeSessionResponse,
    KillSwitchEventResponse,
    KillSwitchRequest,
    SandboxDecisionResponse,
    SandboxProfileCreateRequest,
    SandboxProfilePatchRequest,
    SandboxProfileResponse,
    SandboxProfileTestRequest,
    SagaCancelRequest,
    SagaCreateRequest,
    SagaExecuteRequest,
    SagaExecutionResponse,
    SagaResponse,
    SagaStepCreateRequest,
    SagaStepResponse,
)
from product_platform.runtime.repository import (
    RuntimeAgentNotActiveError,
    RuntimeRepository,
    RuntimeSessionNotFoundError,
    RuntimeSessionStateError,
    runtime_action_response,
    runtime_ring_decision_response,
    runtime_ring_rule_response,
    runtime_session_response,
)
from product_platform.runtime.kill_switch import (
    KillSwitchRepository,
    KillSwitchTargetNotFoundError,
    KillSwitchValidationError,
    kill_switch_event_response,
)
from product_platform.runtime.rings import RuntimeRingDecisionService
from product_platform.runtime.saga_executor import (
    DemoSafeActionRunner,
    SagaExecutionError,
    SagaExecutionService,
)
from product_platform.runtime.sandbox import (
    DuplicateSandboxProfileNameError,
    SandboxProfileNotFoundError,
    SandboxProfileRepository,
    SandboxTestAdapter,
    SandboxProfileValidationError,
    sandbox_profile_response,
)
from product_platform.runtime.sagas import (
    SagaNotFoundError,
    SagaRepository,
    SagaStepValidationError,
    saga_event_response,
    saga_response,
    saga_step_response,
)
from product_platform.trust.models import (
    AgentTrustCardResponse,
    TrustHandshakeRequest,
    TrustHandshakeResponse,
    TrustCardIssueRequest,
    TrustCardResponse,
    TrustCardRevokeRequest,
    TrustCardVerifyResponse,
    TrustEventResponse,
    TrustRecalculateRequest,
    TrustRecalculationRunResponse,
    TrustRulePatchRequest,
    TrustRuleResponse,
    TrustScoreResponse,
    TrustThresholdCreateRequest,
    TrustThresholdPatchRequest,
    TrustThresholdResponse,
)
from product_platform.trust.cards import (
    TrustCardIssuer,
    TrustCardNotFoundError,
    TrustCardRepository,
    trust_card_response,
)
from product_platform.trust.handshakes import TrustHandshakeService
from product_platform.trust.pipeline import TrustScoreRecalculator
from product_platform.trust.repository import (
    DuplicateTrustThresholdError,
    TrustAgentNotFoundError,
    TrustRepository,
    TrustRuleNotFoundError,
    TrustThresholdNotFoundError,
    trust_event_response,
    trust_recalculation_run_response,
    trust_handshake_response,
    trust_rule_response,
    trust_score_response,
    trust_threshold_response,
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
from product_platform.workflows.models import (
    WorkflowDefinitionResponse,
    WorkflowInputValidationError,
    WorkflowRunCreateRequest,
    WorkflowRunResponse,
)
from product_platform.workflows.repository import (
    WorkflowRepository,
    workflow_definition_response,
    workflow_run_response,
)
from product_platform.workflows.runner import WorkflowRunnerError, build_default_workflow_runner_registry


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
    registry = dependency_registry or create_default_dependency_registry(resolved_settings)
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

    def _secret_provider() -> SecretProvider:
        provider = getattr(app.state, "secret_provider", None)
        if provider is None:
            provider = DEFAULT_SECRET_PROVIDER
            app.state.secret_provider = provider
        return provider

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

    def _artifact_repository(
        connection: Any,
        organization_id: str,
        environment_id: str,
    ) -> ArtifactRepository:
        return ArtifactRepository(
            connection,
            organization_id,
            environment_id,
            LocalArtifactProvider(Path(resolved_settings.artifact_storage_path)),
        )

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

    @app.get("/api/v1/workflows", response_model=list[WorkflowDefinitionResponse], tags=["workflows"])
    async def list_workflows(
        enabled: bool | None = Query(default=None),
        workflow_type: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
    ) -> list[WorkflowDefinitionResponse]:
        """List registered product workflow definitions."""

        organization_id = _require_organization_id(current_user)
        repository = WorkflowRepository(_audit_database().connect(), organization_id)
        return [
            workflow_definition_response(row)
            for row in repository.list_definitions(enabled=enabled, workflow_type=workflow_type)
        ]

    @app.post(
        "/api/v1/workflows/{workflow_id}/runs",
        response_model=WorkflowRunResponse,
        status_code=201,
        tags=["workflows"],
    )
    async def create_workflow_run(
        workflow_id: str,
        body: WorkflowRunCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> WorkflowRunResponse:
        """Create and optionally execute a workflow run."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = WorkflowRepository(connection, organization_id)
            definition = repository.get_definition(workflow_id)
            if definition is None:
                raise HTTPException(status_code=404, detail="Workflow not found.")
            try:
                run = repository.create_run(
                    definition,
                    environment_id=environment_id,
                    inputs=body.inputs,
                    started_by=current_user.id,
                )
            except WorkflowInputValidationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            audit = AuditEventRepository(connection)
            _insert_job_audit_event(
                audit,
                organization_id=organization_id,
                environment_id=environment_id,
                job_id=run["id"],
                job_type=definition["workflow_type"],
                status=run["status"],
            )
            if body.run_immediately:
                started = repository.start_run(run["id"], environment_id=environment_id)
                _insert_job_audit_event(
                    audit,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    job_id=started["id"],
                    job_type=definition["workflow_type"],
                    status=started["status"],
                )
                try:
                    result = build_default_workflow_runner_registry().run(
                        definition["command_ref"],
                        body.inputs,
                    )
                except WorkflowRunnerError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                run = repository.complete_run(
                    run["id"],
                    environment_id=environment_id,
                    result=result,
                )
                _insert_job_audit_event(
                    audit,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    job_id=run["id"],
                    job_type=definition["workflow_type"],
                    status=run["status"],
                )
            return workflow_run_response(repository, run)

    @app.get(
        "/api/v1/workflow-runs",
        response_model=list[WorkflowRunResponse],
        tags=["workflows"],
    )
    async def list_workflow_runs(
        status: str | None = None,
        workflow_definition_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[WorkflowRunResponse]:
        """List workflow runs for the selected environment."""

        organization_id = _require_organization_id(current_user)
        repository = WorkflowRepository(_audit_database().connect(), organization_id)
        return [
            workflow_run_response(repository, row)
            for row in repository.list_runs(
                environment_id=environment_id,
                status=status,
                workflow_definition_id=workflow_definition_id,
                limit=limit,
                offset=offset,
            )
        ]

    @app.get(
        "/api/v1/workflow-runs/{run_id}",
        response_model=WorkflowRunResponse,
        tags=["workflows"],
    )
    async def get_workflow_run(
        run_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> WorkflowRunResponse:
        """Get one workflow run with logs."""

        organization_id = _require_organization_id(current_user)
        repository = WorkflowRepository(_audit_database().connect(), organization_id)
        row = repository.get_run(run_id, environment_id=environment_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Workflow run not found.")
        return workflow_run_response(repository, row)

    @app.post(
        "/api/v1/workflow-runs/{run_id}/cancel",
        response_model=WorkflowRunResponse,
        tags=["workflows"],
    )
    async def cancel_workflow_run(
        run_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_CANCEL)),
        environment_id: str = Depends(require_environment_context),
    ) -> WorkflowRunResponse:
        """Cancel a queued workflow run."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = WorkflowRepository(connection, organization_id)
                run = repository.cancel_run(run_id, environment_id=environment_id)
                _insert_job_audit_event(
                    AuditEventRepository(connection),
                    organization_id=organization_id,
                    environment_id=environment_id,
                    job_id=run["id"],
                    job_type=run["workflow_type"],
                    status=run["status"],
                )
                return workflow_run_response(repository, run)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/artifacts",
        response_model=ArtifactResponse,
        status_code=201,
        tags=["artifacts"],
    )
    async def create_artifact(
        body: ArtifactCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> ArtifactResponse:
        """Upload artifact content and persist metadata."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = _artifact_repository(connection, organization_id, environment_id)
                row = repository.create(body, actor_id=current_user.id)
                return artifact_response(repository, row)
        except (ArtifactStorageError, ArtifactValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/artifacts",
        response_model=list[ArtifactResponse],
        tags=["artifacts"],
    )
    async def list_artifacts(
        artifact_type: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ArtifactResponse]:
        """List artifacts for the selected environment."""

        organization_id = _require_organization_id(current_user)
        repository = _artifact_repository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        return [artifact_response(repository, row) for row in repository.list(artifact_type=artifact_type)]

    @app.get(
        "/api/v1/artifacts/{artifact_id}",
        response_model=ArtifactResponse,
        tags=["artifacts"],
    )
    async def get_artifact(
        artifact_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> ArtifactResponse:
        """Get one artifact and its target links."""

        organization_id = _require_organization_id(current_user)
        repository = _artifact_repository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        row = repository.get(artifact_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Artifact not found.")
        return artifact_response(repository, row)

    @app.get(
        "/api/v1/artifacts/{artifact_id}/download",
        response_model=ArtifactDownloadResponse,
        tags=["artifacts"],
    )
    async def download_artifact(
        artifact_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> ArtifactDownloadResponse:
        """Download artifact content as base64 with checksum verification metadata."""

        organization_id = _require_organization_id(current_user)
        repository = _artifact_repository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        try:
            return repository.download(artifact_id)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArtifactStorageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/artifacts/{artifact_id}/links",
        response_model=ArtifactLinkResponse,
        status_code=201,
        tags=["artifacts"],
    )
    async def create_artifact_link(
        artifact_id: str,
        body: ArtifactLinkCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> ArtifactLinkResponse:
        """Attach an artifact to a workflow, audit, compliance, evidence, or plugin target."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = _artifact_repository(connection, organization_id, environment_id)
                row = repository.create_link(artifact_id, body)
                return artifact_link_response(row)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ArtifactValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/artifacts/{artifact_id}/attest",
        response_model=ArtifactAttestationResponse,
        status_code=201,
        tags=["artifacts"],
    )
    async def attest_artifact(
        artifact_id: str,
        body: ArtifactAttestationCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ArtifactAttestationResponse:
        """Attest an artifact with a signer statement and optional signature reference."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = _artifact_repository(connection, organization_id, environment_id)
                artifact = repository.get(artifact_id)
                if artifact is None:
                    raise ArtifactNotFoundError("Artifact not found.")
                row = repository.create_attestation(artifact_id, body, actor_id=current_user.id)
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="artifact.attested",
                        source_component="artifact-store",
                        actor_type="user",
                        actor_id=current_user.id,
                        resource_type="artifact",
                        resource_id=artifact_id,
                        decision="attested",
                        severity="info",
                        payload_json={
                            "attestation_id": row["id"],
                            "artifact_type": artifact["artifact_type"],
                            "checksum": artifact["checksum"],
                            "signature_ref": row["signature_ref"],
                        },
                    )
                )
                return artifact_attestation_response(row)
        except ArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/demo/scenarios",
        response_model=list[DemoScenarioSummaryResponse],
        tags=["demo"],
    )
    async def list_demo_scenarios(
        status: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[DemoScenarioSummaryResponse]:
        """List Demo Lab scenarios available in the selected environment."""

        organization_id = _require_organization_id(current_user)
        repository = DemoScenarioRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        return [
            demo_scenario_summary_response(row)
            for row in repository.list_scenarios(status=status)
        ]

    @app.get(
        "/api/v1/demo/scenarios/{scenario_id}",
        response_model=DemoScenarioDetailResponse,
        tags=["demo"],
    )
    async def get_demo_scenario(
        scenario_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> DemoScenarioDetailResponse:
        """Return one Demo Lab scenario with ordered steps."""

        organization_id = _require_organization_id(current_user)
        repository = DemoScenarioRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        detail = repository.get_detail(scenario_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Scenario not found.")
        return detail

    @app.post(
        "/api/v1/demo/scenarios/{scenario_id}/runs",
        response_model=DemoRunResponse,
        status_code=201,
        tags=["demo"],
    )
    async def start_demo_run(
        scenario_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> DemoRunResponse:
        """Start a Demo Lab scenario run."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = DemoScenarioRepository(connection, organization_id, environment_id)
                run = repository.create_run(scenario_id, started_by=current_user.id)
                AuditEventRepository(connection).insert(
                    demo_run_audit_event(
                        event_type="demo.run.started",
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        run_id=run["id"],
                        scenario_id=run["scenario_id"],
                        status=run["status"],
                        summary_json=run["summary_json"],
                        correlation_id=context.correlation_id,
                    )
                )
                return demo_run_response(repository, run)
        except DemoScenarioNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/demo/runs/{run_id}",
        response_model=DemoRunResponse,
        tags=["demo"],
    )
    async def get_demo_run(
        run_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> DemoRunResponse:
        """Get one Demo Lab scenario run."""

        organization_id = _require_organization_id(current_user)
        repository = DemoScenarioRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        run = repository.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        return demo_run_response(repository, run)

    @app.post(
        "/api/v1/demo/runs/{run_id}/continue",
        response_model=DemoRunResponse,
        tags=["demo"],
    )
    async def continue_demo_run(
        run_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> DemoRunResponse:
        """Execute the next pending Demo Lab scenario step."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = DemoScenarioRepository(connection, organization_id, environment_id)
                audit_repository = AuditEventRepository(connection)
                run = DemoScenarioRunner(
                    repository,
                    audit_repository=audit_repository,
                    actor_id=current_user.id,
                ).continue_run(run_id, correlation_id=context.correlation_id)
                return demo_run_response(repository, run)
        except DemoScenarioNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/demo/runs/{run_id}/cancel",
        response_model=DemoRunResponse,
        tags=["demo"],
    )
    async def cancel_demo_run(
        run_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_CANCEL)),
        environment_id: str = Depends(require_environment_context),
    ) -> DemoRunResponse:
        """Cancel a non-terminal Demo Lab scenario run."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = DemoScenarioRepository(connection, organization_id, environment_id)
                run = repository.cancel_run(run_id, reason="Cancelled from Demo Lab.")
                AuditEventRepository(connection).insert(
                    demo_run_audit_event(
                        event_type="demo.run.canceled",
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        run_id=run["id"],
                        scenario_id=run["scenario_id"],
                        status=run["status"],
                        summary_json=run["summary_json"],
                        correlation_id=context.correlation_id,
                    )
                )
                return demo_run_response(repository, run)
        except DemoScenarioNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/demo/reset",
        response_model=DemoResetRunResponse,
        status_code=201,
        tags=["demo"],
    )
    async def reset_demo_environment(
        body: DemoResetRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_CANCEL)),
        environment_id: str = Depends(require_environment_context),
    ) -> DemoResetRunResponse:
        """Reset the selected local demo environment to a known baseline."""

        if body.confirmation != "RESET":
            raise HTTPException(status_code=400, detail="Type RESET to confirm demo reset.")
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            reset_run = DemoEnvironmentResetService(
                connection,
                organization_id,
                environment_id,
            ).reset(
                requested_by=current_user.id,
                correlation_id=context.correlation_id,
            )
            return demo_reset_run_response(reset_run)

    @app.get(
        "/api/v1/demo/reset-runs",
        response_model=list[DemoResetRunResponse],
        tags=["demo"],
    )
    async def list_demo_reset_runs(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[DemoResetRunResponse]:
        """List reset history for the selected demo environment."""

        organization_id = _require_organization_id(current_user)
        repository = DemoResetRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        return [
            demo_reset_run_response(row)
            for row in repository.list_runs(limit=limit, offset=offset)
        ]

    @app.get(
        "/api/v1/demo/reset-runs/{reset_id}",
        response_model=DemoResetRunResponse,
        tags=["demo"],
    )
    async def get_demo_reset_run(
        reset_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> DemoResetRunResponse:
        """Get one demo reset run."""

        organization_id = _require_organization_id(current_user)
        repository = DemoResetRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        row = repository.get_optional(reset_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Reset run not found.")
        return demo_reset_run_response(row)

    @app.get(
        "/api/v1/demo/baseline-status",
        response_model=DemoBaselineStatusResponse,
        tags=["demo"],
    )
    async def get_demo_baseline_status(
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> DemoBaselineStatusResponse:
        """Return Demo Lab baseline prerequisite health."""

        organization_id = _require_organization_id(current_user)
        return demo_baseline_status(
            _audit_database().connect(),
            organization_id=organization_id,
            environment_id=environment_id,
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

    def _policy_evaluation_audit_event(
        *,
        evaluation: PolicyEvaluationResponse,
        actor_id: str,
    ) -> AuditEventEnvelope:
        payload = {
            "evaluation_id": evaluation.id,
            "policy_id": evaluation.policy_id,
            "policy_version_id": evaluation.policy_version_id,
            "binding_id": evaluation.binding_id,
            "binding_mode": evaluation.binding_mode,
            "target_type": evaluation.target_type,
            "target_id": evaluation.target_id,
            "action": evaluation.action,
            "resource_type": evaluation.resource_type,
            "resource_id": evaluation.resource_id,
            "matched_rule": evaluation.matched_rule,
            "reason": evaluation.reason,
            "latency_ms": evaluation.latency_ms,
            "mode": evaluation.mode,
            "backend": evaluation.backend,
            "error": evaluation.error,
        }
        return AuditEventEnvelope(
            organization_id=evaluation.organization_id,
            environment_id=evaluation.environment_id,
            event_type="policy.decision",
            source_component="policy-engine",
            actor_type="user",
            actor_id=actor_id,
            agent_id=evaluation.agent_id,
            resource_type="policy_evaluation",
            resource_id=evaluation.id,
            decision=evaluation.decision,
            severity="warning" if evaluation.decision == "deny" or evaluation.error else "info",
            correlation_id=evaluation.correlation_id,
            policy_id=evaluation.policy_id,
            policy_version_id=evaluation.policy_version_id,
            payload_json=payload,
        )

    def _record_mcp_policy_evaluation(
        *,
        connection: Any,
        organization_id: str,
        environment_id: str,
        call: MCPToolCallResponse,
    ) -> None:
        try:
            matched_policy_ref = call.matched_policy_id
            policy_id = matched_policy_ref
            if policy_id and PolicyRepository(connection, organization_id).get_policy(policy_id) is None:
                policy_id = None
            PolicyEvaluationRepository(connection).create(
                PolicyEvaluationResponse(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    policy_id=policy_id,
                    policy_version_id=call.matched_policy_version_id if policy_id else None,
                    agent_id=call.source_agent_id,
                    target_type="mcp-tool",
                    target_id=call.tool_id,
                    action="mcp.tool_call",
                    resource_type="mcp-tool",
                    resource_id=call.tool_id,
                    context={
                        "tool_call_id": call.id,
                        "server_id": call.server_id,
                        "server_name": call.server_name,
                        "tool_id": call.tool_id,
                        "tool_name": call.tool_name,
                        "source_agent_id": call.source_agent_id,
                        "source_agent_name": call.source_agent_name,
                        "params_summary": call.params_summary,
                        "gateway_stage": call.gateway_stage,
                        "matched_policy_ref": matched_policy_ref,
                        "trust_threshold_id": call.trust_threshold_id,
                        "trust_score": call.trust_score,
                        "sanitizer_action": call.sanitizer_action,
                    },
                    decision=_policy_feed_decision(call.decision),
                    policy_action=call.decision,
                    matched_rule=call.gateway_stage,
                    reason=call.reason,
                    latency_ms=float(call.latency_ms),
                    mode="live",
                    correlation_id=call.correlation_id,
                    backend="mcp-proxy",
                    audit_preview={
                        "event_type": f"mcp.proxy.call.{call.decision}",
                        "resource_type": "mcp_tool_call",
                        "resource_id": call.id,
                    },
                )
            )
        except Exception:
            return

    def _record_runtime_policy_evaluation(
        *,
        connection: Any,
        organization_id: str,
        environment_id: str,
        action: RuntimeActionResponse,
    ) -> None:
        try:
            ring_decision = action.ring_decision
            context = {
                "runtime_action_id": action.id,
                "session_id": action.session_id,
                "action_name": action.action_name,
                "required_ring": action.required_ring,
            }
            agent_id = None
            matched_rule = None
            if ring_decision is not None:
                agent_id = ring_decision.agent_id
                matched_rule = f"ring:{ring_decision.required_ring}"
                context.update(
                    {
                        "agent_id": ring_decision.agent_id,
                        "agent_trust_score": ring_decision.agent_trust_score,
                        "assigned_ring": ring_decision.assigned_ring,
                        "required_ring": ring_decision.required_ring,
                    }
                )
            PolicyEvaluationRepository(connection).create(
                PolicyEvaluationResponse(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    agent_id=agent_id,
                    target_type="runtime-action",
                    target_id=action.action_name,
                    action=action.action_name,
                    resource_type=action.resource_type,
                    resource_id=action.id,
                    context=context,
                    decision=_policy_feed_decision(action.decision),
                    policy_action=action.decision,
                    matched_rule=matched_rule,
                    reason=action.reason,
                    latency_ms=float(action.latency_ms),
                    mode="live",
                    correlation_id=action.correlation_id,
                    backend="runtime-ring",
                    audit_preview={
                        "event_type": "runtime.action",
                        "resource_type": "runtime_action",
                        "resource_id": action.id,
                    },
                )
            )
        except Exception:
            return

    def _policy_feed_decision(decision: str) -> str:
        normalized = decision.strip().lower()
        if normalized in {"allowed", "allow", "audit"}:
            return "allow"
        if normalized in {"denied", "deny", "blocked", "block"}:
            return "deny"
        return normalized

    def _trust_card_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        event_type: str,
        actor_id: str,
        card: Any,
        correlation_id: str | None,
        payload_json: dict[str, Any] | None = None,
    ) -> AuditEventEnvelope:
        payload = {
            "trust_card_id": card["id"],
            "agent_id": card["agent_id"],
            "issuer": card["issuer"],
            "status": card["status"],
            "valid_until": card["valid_until"],
        }
        payload.update(payload_json or {})
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="trust-cards",
            actor_type="user",
            actor_id=actor_id,
            agent_id=card["agent_id"],
            resource_type="trust_card",
            resource_id=card["id"],
            correlation_id=correlation_id,
            payload_json=payload,
        )

    def _trust_handshake_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        handshake: TrustHandshakeResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        payload = handshake.model_dump()
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="trust.handshake",
            source_component="trust-handshakes",
            actor_type="user",
            actor_id=actor_id,
            agent_id=handshake.source_agent_id,
            resource_type="handshake",
            resource_id=handshake.id,
            decision="allow" if handshake.result == "allowed" else "deny",
            severity="warning" if handshake.result == "denied" else "info",
            correlation_id=correlation_id,
            payload_json=payload,
        )

    def _mesh_message_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        message: MeshMessageResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        decision = message.decision.lower()
        event_type = "mesh.message.escalated" if decision in {"escalate", "escalated"} else "mesh.message.blocked"
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="mesh-message-feed",
            actor_type="user",
            actor_id=actor_id,
            agent_id=message.source_agent_id,
            resource_type="mesh_message",
            resource_id=message.id,
            decision=message.decision,
            severity="warning",
            correlation_id=correlation_id,
            payload_json=message.model_dump(),
        )

    def _protocol_bridge_route_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        route: ProtocolBridgeRouteResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="protocol_bridge.route.changed",
            source_component="protocol-bridge-config",
            actor_type="user",
            actor_id=actor_id,
            agent_id=route.source_agent_id,
            resource_type="protocol_bridge_route",
            resource_id=route.id,
            correlation_id=correlation_id,
            payload_json=route.model_dump(),
        )

    def _mcp_server_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        server: MCPServerResponse,
        correlation_id: str | None,
        previous_status: str | None = None,
    ) -> AuditEventEnvelope:
        payload = server.model_dump()
        if previous_status is not None:
            payload["previous_status"] = previous_status
            payload["status_changed"] = previous_status != server.status
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="mcp-registry",
            actor_type="user",
            actor_id=actor_id,
            resource_type="mcp_server",
            resource_id=server.id,
            correlation_id=correlation_id,
            payload_json=payload,
        )

    def _mcp_tool_response(
        repository: MCPRegistryRepository,
        row: Any,
        *,
        include_versions: bool = False,
    ) -> MCPToolResponse:
        current_row = repository.current_tool_version(row)
        current = mcp_tool_version_response(current_row) if current_row is not None else None
        versions = (
            [mcp_tool_version_response(version) for version in repository.list_tool_versions(row["id"])]
            if include_versions
            else []
        )
        return mcp_tool_response(row, current_version=current, versions=versions)

    def _mcp_tool_schema_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        change: MCPToolSchemaChange,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="mcp.tool.schema.changed",
            source_component="mcp-registry",
            actor_type="user",
            actor_id=actor_id,
            resource_type="mcp_tool",
            resource_id=change.tool_id,
            severity="warning",
            correlation_id=correlation_id,
            payload_json={
                "tool_id": change.tool_id,
                "tool_name": change.tool_name,
                "server_id": change.server_id,
                "version_id": change.version_id,
                "previous_schema_hash": change.previous_schema_hash,
                "schema_hash": change.schema_hash,
            },
        )

    def _mcp_scan_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        scan: MCPScanRunResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        severity = "warning" if scan.status == "failed" else "info"
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="mcp-security-scans",
            actor_type="user",
            actor_id=actor_id,
            resource_type="mcp_scan_run",
            resource_id=scan.id,
            severity=severity,
            correlation_id=correlation_id,
            payload_json=scan.model_dump(),
        )

    def _mcp_finding_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        finding: MCPFindingResponse,
        correlation_id: str | None,
        previous_status: str,
        reason: str | None = None,
    ) -> AuditEventEnvelope:
        payload = finding.model_dump()
        payload["previous_status"] = previous_status
        if reason is not None:
            payload["reason"] = reason
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="mcp-security-scans",
            actor_type="user",
            actor_id=actor_id,
            resource_type="mcp_finding",
            resource_id=finding.id,
            severity="info",
            correlation_id=correlation_id,
            payload_json=payload,
        )

    def _mcp_proxy_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        call: MCPToolCallResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        event_type = {
            "allowed": "mcp.proxy.call.allowed",
            "denied": "mcp.proxy.call.denied",
            "escalated": "mcp.proxy.call.escalated",
        }.get(call.decision, "mcp.proxy.call.recorded")
        severity = "warning" if call.decision in {"denied", "escalated"} else "info"
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="mcp-proxy",
            actor_type="user",
            actor_id=actor_id,
            resource_type="mcp_tool_call",
            resource_id=call.id,
            decision=call.decision,
            severity=severity,
            correlation_id=call.correlation_id or correlation_id,
            payload_json=call.model_dump(),
        )

    def _mcp_approval_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        approval: MCPApprovalResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        decision = "allow" if approval.status == "approved" else "deny"
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="mcp-proxy",
            actor_type="user",
            actor_id=actor_id,
            resource_type="mcp_approval",
            resource_id=approval.id,
            decision=decision,
            severity="info" if approval.status == "approved" else "warning",
            correlation_id=correlation_id,
            payload_json=approval.model_dump(),
        )

    def _mcp_response_sanitizer_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        call: MCPToolCallResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="mcp.proxy.response.sanitized",
            source_component="mcp-proxy",
            actor_type="user",
            actor_id=actor_id,
            resource_type="mcp_tool_call",
            resource_id=call.id,
            decision=call.decision,
            severity="warning",
            correlation_id=call.correlation_id or correlation_id,
            payload_json=call.model_dump(),
        )

    def _require_mcp_approval_actor(current_user: UserPrincipal) -> None:
        if has_permission(current_user, Permission.SECURITY_MANAGE) or "Operator" in current_user.roles:
            return
        raise HTTPException(
            status_code=403,
            detail="MCP approval decisions require Security Admin or Operator.",
        )

    def _require_marketplace_reviewer(current_user: UserPrincipal) -> None:
        if has_permission(current_user, Permission.SECURITY_MANAGE) or has_permission(
            current_user, Permission.POLICY_WRITE
        ):
            return
        raise HTTPException(
            status_code=403,
            detail="Marketplace reviews require Security Admin or Policy Admin.",
        )

    def _runtime_session_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        session: RuntimeSessionResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="runtime-sessions",
            actor_type="user",
            actor_id=actor_id,
            agent_id=session.agent_id,
            resource_type="runtime_session",
            resource_id=session.id,
            severity="info",
            correlation_id=correlation_id,
            payload_json=session.model_dump(),
        )

    def _runtime_action_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        action: RuntimeActionResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="runtime.action",
            source_component="runtime-rings",
            actor_type="user",
            actor_id=actor_id,
            agent_id=action.ring_decision.agent_id if action.ring_decision else None,
            resource_type="runtime_action",
            resource_id=action.id,
            decision=action.decision,
            severity="warning" if action.decision == "denied" else "info",
            correlation_id=action.correlation_id or correlation_id,
            payload_json=action.model_dump(),
        )

    def _runtime_ring_rule_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        rule: RuntimeRingRuleResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="runtime.ring_rule.created",
            source_component="runtime-rings",
            actor_type="user",
            actor_id=actor_id,
            resource_type="runtime_ring_rule",
            resource_id=rule.id,
            severity="info",
            correlation_id=correlation_id,
            payload_json=rule.model_dump(),
        )

    def _saga_detail_response(repository: SagaRepository, saga_id: str) -> SagaResponse:
        row = repository.get_saga(saga_id)
        if row is None:
            raise SagaNotFoundError("Saga not found.")
        return saga_response(
            row,
            steps=[saga_step_response(step) for step in repository.list_steps(saga_id)],
            events=[saga_event_response(event) for event in repository.list_events(saga_id)],
        )

    def _saga_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        saga: SagaResponse,
        correlation_id: str | None,
        payload: dict[str, Any] | None = None,
        decision: str | None = None,
        severity: str = "info",
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="saga-runtime",
            actor_type="user",
            actor_id=actor_id,
            resource_type="saga",
            resource_id=saga.id,
            decision=decision,
            severity=severity,
            correlation_id=correlation_id or saga.correlation_id,
            payload_json={
                "saga_id": saga.id,
                "status": saga.status,
                "runtime_session_id": saga.runtime_session_id,
                **(payload or {}),
            },
        )

    def _saga_runtime_action_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        saga: SagaResponse,
        step: SagaStepResponse,
        status: str,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        denied = status in {"failed", "compensation_failed"}
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="runtime.action",
            source_component="saga-runtime",
            actor_type="user",
            actor_id=actor_id,
            agent_id=step.target_agent_id,
            resource_type="runtime_session",
            resource_id=saga.runtime_session_id,
            decision="deny" if denied else "allow",
            severity="warning" if denied else "info",
            correlation_id=correlation_id or saga.correlation_id,
            payload_json={
                "action": step.action_name,
                "status": status,
                "saga_id": saga.id,
                "step_id": step.id,
                "required_capability": step.required_capability,
            },
        )

    def _kill_switch_audit_event(
        *,
        event: KillSwitchEventResponse,
        agent_id: str | None,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=event.organization_id,
            environment_id=event.environment_id,
            event_type="runtime.kill_switch",
            source_component="kill-switch",
            actor_type="user",
            actor_id=event.actor_id,
            agent_id=agent_id,
            resource_type=event.target_type,
            resource_id=event.target_id,
            decision="deny",
            severity="critical",
            correlation_id=correlation_id,
            payload_json={
                "action": "kill_switch",
                "status": "kill_switch_triggered",
                "target_type": event.target_type,
                "target_id": event.target_id,
                "scope": event.scope,
                "reason": event.reason,
            },
        )

    def _plugin_installation_audit_event(
        *,
        organization_id: str,
        actor_id: str,
        event_type: str,
        installation: PluginInstallationResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=installation.environment_id,
            event_type=event_type,
            source_component="marketplace",
            actor_type="user",
            actor_id=actor_id,
            agent_id=installation.target_agent_id,
            resource_type="plugin_installation",
            resource_id=installation.id,
            severity="info",
            correlation_id=correlation_id,
            payload_json=installation.model_dump(),
        )

    def _plugin_signing_key_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        signing_key: PluginSigningKeyResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="marketplace-signing",
            actor_type="user",
            actor_id=actor_id,
            resource_type="plugin_signing_key",
            resource_id=signing_key.id,
            severity="warning" if signing_key.status == "revoked" else "info",
            correlation_id=correlation_id,
            payload_json=signing_key.model_dump(),
        )

    def _mcp_scan_run_response(
        repository: MCPRegistryRepository,
        row: Any,
        *,
        include_findings: bool = False,
    ) -> MCPScanRunResponse:
        findings = (
            [mcp_finding_response(finding) for finding in repository.list_findings(scan_run_id=row["id"])]
            if include_findings
            else []
        )
        return mcp_scan_run_response(row, findings=findings)

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
        source_component: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
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
                source_component=source_component,
                actor_type=actor_type,
                actor_id=actor_id,
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

    @app.post(
        "/api/v1/audit/export",
        response_model=AuditExportResponse,
        status_code=201,
        tags=["audit"],
    )
    async def export_audit_events(
        body: AuditExportRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_READ)),
    ) -> AuditExportResponse:
        """Persist audit export metadata for compliance evidence workflows."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            row = AuditExportRepository(connection, organization_id).create(
                body,
                actor_id=current_user.id,
            )
            return audit_export_response(row)

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
        "/api/v1/policy-evaluations/simulate",
        response_model=PolicyEvaluationResponse,
        status_code=201,
        tags=["policies"],
    )
    async def simulate_policy_evaluation(
        body: PolicyEvaluationRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> PolicyEvaluationResponse:
        """Evaluate policy behavior in simulator mode and persist the result."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        simulate_body = body.model_copy(update={"mode": "simulate"})
        with _audit_database().transaction() as connection:
            evaluation = PolicyEvaluationAdapter(
                connection,
                organization_id,
                environment_id,
            ).evaluate(simulate_body, correlation_id=context.correlation_id)
            row = PolicyEvaluationRepository(connection).create(evaluation)
            return policy_evaluation_response(row)

    @app.post(
        "/api/v1/policy-evaluations/evaluate",
        response_model=PolicyEvaluationResponse,
        status_code=201,
        tags=["policies"],
    )
    async def evaluate_policy_live(
        body: PolicyEvaluationRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> PolicyEvaluationResponse:
        """Evaluate policy behavior in live mode, persist it, and emit audit history."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        live_body = body.model_copy(update={"mode": "live"})
        with _audit_database().transaction() as connection:
            repository = PolicyEvaluationRepository(connection)
            audit_repository = AuditEventRepository(connection)
            evaluation = PolicyEvaluationAdapter(
                connection,
                organization_id,
                environment_id,
            ).evaluate(live_body, correlation_id=context.correlation_id)
            row = repository.create(evaluation)
            persisted = policy_evaluation_response(row)
            audit_repository.insert(
                _policy_evaluation_audit_event(
                    evaluation=persisted,
                    actor_id=current_user.id,
                )
            )
            return persisted

    @app.get(
        "/api/v1/policy-evaluations",
        response_model=list[PolicyEvaluationResponse],
        tags=["policies"],
    )
    async def list_policy_evaluations(
        decision: str | None = None,
        mode: str | None = None,
        agent_id: str | None = None,
        action: str | None = None,
        policy_id: str | None = None,
        correlation_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[PolicyEvaluationResponse]:
        """List policy evaluation feed rows for the selected environment."""

        organization_id = _require_organization_id(current_user)
        rows = PolicyEvaluationRepository(_audit_database().connect()).list(
            PolicyEvaluationQuery(
                organization_id=organization_id,
                environment_id=environment_id,
                decision=decision,
                mode=mode,
                agent_id=agent_id,
                action=action,
                policy_id=policy_id,
                correlation_id=correlation_id,
                limit=limit,
                offset=offset,
            )
        )
        return [policy_evaluation_response(row) for row in rows]

    @app.get(
        "/api/v1/policy-evaluations/{evaluation_id}",
        response_model=PolicyEvaluationResponse,
        tags=["policies"],
    )
    async def get_policy_evaluation(
        evaluation_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> PolicyEvaluationResponse:
        """Get one policy evaluation row in the selected environment."""

        organization_id = _require_organization_id(current_user)
        row = PolicyEvaluationRepository(_audit_database().connect()).get(
            evaluation_id,
            organization_id,
            environment_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Policy evaluation not found.")
        return policy_evaluation_response(row)

    @app.get(
        "/api/v1/compliance/frameworks",
        response_model=list[ComplianceFrameworkResponse],
        tags=["compliance"],
    )
    async def list_compliance_frameworks(
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ComplianceFrameworkResponse]:
        """List compliance frameworks for the current organization."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ComplianceRepository(connection, organization_id, environment_id)
            return [framework_response(row) for row in repository.list_frameworks()]

    @app.post(
        "/api/v1/compliance/frameworks",
        response_model=ComplianceFrameworkResponse,
        status_code=201,
        tags=["compliance"],
    )
    async def create_compliance_framework(
        body: ComplianceFrameworkCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ComplianceFrameworkResponse:
        """Create a custom compliance framework for the current organization."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = ComplianceRepository(connection, organization_id, environment_id)
                return framework_response(repository.create_framework(body))
        except DuplicateComplianceResourceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/v1/compliance/controls",
        response_model=list[ComplianceControlResponse],
        tags=["compliance"],
    )
    async def list_compliance_controls(
        framework_id: str | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ComplianceControlResponse]:
        """List compliance controls and required evidence types."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ComplianceRepository(connection, organization_id, environment_id)
            return [
                control_response(row)
                for row in repository.list_controls(framework_id=framework_id)
            ]

    @app.post(
        "/api/v1/compliance/control-mappings",
        response_model=ControlMappingResponse,
        status_code=201,
        tags=["compliance"],
    )
    async def create_compliance_control_mapping(
        body: ControlMappingCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ControlMappingResponse:
        """Create an audit-event-to-control mapping."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = ComplianceRepository(connection, organization_id, environment_id)
                return control_mapping_response(repository.create_mapping(body))
        except ComplianceResourceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DuplicateComplianceResourceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/v1/compliance/evidence",
        response_model=list[EvidenceItemResponse],
        tags=["compliance"],
    )
    async def list_compliance_evidence(
        control_id: str | None = None,
        status: str | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[EvidenceItemResponse]:
        """List evidence items for the selected environment."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ComplianceRepository(connection, organization_id, environment_id)
            return [
                evidence_response(row)
                for row in repository.list_evidence(control_id=control_id, status=status)
            ]

    @app.post(
        "/api/v1/compliance/evidence/recompute",
        response_model=EvidenceRecomputeResponse,
        status_code=201,
        tags=["compliance"],
    )
    async def recompute_compliance_evidence(
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> EvidenceRecomputeResponse:
        """Refresh mapped compliance evidence from current audit history."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ComplianceRepository(connection, organization_id, environment_id)
            return repository.recompute_evidence()

    @app.get(
        "/api/v1/compliance/violations",
        response_model=list[ComplianceViolationResponse],
        tags=["compliance"],
    )
    async def list_compliance_violations(
        status: str | None = None,
        severity: str | None = None,
        control_id: str | None = None,
        agent_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ComplianceViolationResponse]:
        """List compliance violations in the selected environment."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ComplianceRepository(connection, organization_id, environment_id)
            return [
                violation_response(row)
                for row in repository.list_violations(
                    status=status,
                    severity=severity,
                    control_id=control_id,
                    agent_id=agent_id,
                    limit=limit,
                    offset=offset,
                )
            ]

    @app.patch(
        "/api/v1/compliance/violations/{violation_id}",
        response_model=ComplianceViolationResponse,
        tags=["compliance"],
    )
    async def patch_compliance_violation(
        violation_id: str,
        body: ComplianceViolationPatchRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ComplianceViolationResponse:
        """Acknowledge or resolve a compliance violation."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = ComplianceRepository(connection, organization_id, environment_id)
                row = repository.update_violation(violation_id, body, actor_id=current_user.id)
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type=f"compliance.violation.{row['status']}",
                        source_component="compliance",
                        actor_type="user",
                        actor_id=current_user.id,
                        agent_id=row["agent_id"],
                        resource_type="compliance_violation",
                        resource_id=row["id"],
                        decision=row["status"],
                        severity=row["severity"],
                        payload_json={
                            "control_id": row["control_id"],
                            "source_type": row["source_type"],
                            "source_id": row["source_id"],
                            "reason": body.reason,
                        },
                    )
                )
                return violation_response(row)
        except ComplianceViolationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ComplianceViolationStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/compliance/reports",
        response_model=ComplianceReportResponse,
        status_code=201,
        tags=["compliance"],
    )
    async def create_compliance_report(
        body: ComplianceReportCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ComplianceReportResponse:
        """Create a draft compliance report."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = ComplianceRepository(connection, organization_id, environment_id)
                return report_response(
                    repository,
                    repository.create_report(body, actor_id=current_user.id),
                )
        except ComplianceResourceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/compliance/reports",
        response_model=list[ComplianceReportResponse],
        tags=["compliance"],
    )
    async def list_compliance_reports(
        status: str | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ComplianceReportResponse]:
        """List compliance reports."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ComplianceRepository(connection, organization_id, environment_id)
            return [report_response(repository, row) for row in repository.list_reports(status=status)]

    @app.get(
        "/api/v1/compliance/reports/{report_id}",
        response_model=ComplianceReportResponse,
        tags=["compliance"],
    )
    async def get_compliance_report(
        report_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> ComplianceReportResponse:
        """Get a compliance report."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ComplianceRepository(connection, organization_id, environment_id)
            row = repository.get_report(report_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Compliance report not found.")
            return report_response(repository, row)

    @app.post(
        "/api/v1/compliance/reports/{report_id}/generate",
        response_model=ComplianceReportResponse,
        tags=["compliance"],
    )
    async def generate_compliance_report(
        report_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> ComplianceReportResponse:
        """Generate report content from current evidence and violations."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = ComplianceRepository(connection, organization_id, environment_id)
                row = repository.generate_report(report_id, actor_id=current_user.id)
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="compliance.report.generated",
                        source_component="compliance",
                        actor_type="user",
                        actor_id=current_user.id,
                        resource_type="compliance_report",
                        resource_id=row["id"],
                        decision="generated",
                        severity="info",
                        payload_json={
                            "framework_id": row["framework_id"],
                            "artifact_uri": row["artifact_uri"],
                        },
                    )
                )
                return report_response(repository, row)
        except ComplianceReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/compliance/reports/{report_id}/download",
        tags=["compliance"],
    )
    async def download_compliance_report(
        report_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> Response:
        """Download generated Markdown report content."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                markdown = ComplianceRepository(
                    connection,
                    organization_id,
                    environment_id,
                ).report_markdown(report_id)
                return Response(content=markdown, media_type="text/markdown")
        except ComplianceReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ComplianceReportValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/compliance/reports/{report_id}/attest",
        response_model=ComplianceReportAttestationResponse,
        status_code=201,
        tags=["compliance"],
    )
    async def attest_compliance_report(
        report_id: str,
        body: ComplianceReportAttestationRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ComplianceReportAttestationResponse:
        """Attest a generated compliance report."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = ComplianceRepository(connection, organization_id, environment_id)
                row = repository.attest_report(report_id, body, actor_id=current_user.id)
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="compliance.report.attested",
                        source_component="compliance",
                        actor_type="user",
                        actor_id=current_user.id,
                        resource_type="compliance_report",
                        resource_id=report_id,
                        decision="attested",
                        severity="info",
                        payload_json={
                            "attestation_id": row["id"],
                            "signature_ref": row["signature_ref"],
                        },
                    )
                )
                return report_attestation_response(row)
        except ComplianceReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ComplianceReportValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/v1/trust/scores",
        response_model=list[TrustScoreResponse],
        tags=["trust"],
    )
    async def list_trust_scores(
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[TrustScoreResponse]:
        """List current trust scores for the selected environment."""

        organization_id = _require_organization_id(current_user)
        repository = TrustRepository(_audit_database().connect(), organization_id, environment_id)
        return [trust_score_response(row) for row in repository.list_scores()]

    @app.get(
        "/api/v1/trust/scores/{agent_id}",
        response_model=TrustScoreResponse,
        tags=["trust"],
    )
    async def get_trust_score(
        agent_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustScoreResponse:
        """Get one agent trust score."""

        organization_id = _require_organization_id(current_user)
        row = TrustRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        ).get_score(agent_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Trust score not found.")
        return trust_score_response(row)

    @app.get(
        "/api/v1/trust/events",
        response_model=list[TrustEventResponse],
        tags=["trust"],
    )
    async def list_trust_events(
        agent_id: str | None = None,
        dimension: str | None = None,
        source_event_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[TrustEventResponse]:
        """List explainable trust events."""

        organization_id = _require_organization_id(current_user)
        repository = TrustRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            trust_event_response(row)
            for row in repository.list_events(
                agent_id=agent_id,
                dimension=dimension,
                source_event_id=source_event_id,
                limit=limit,
                offset=offset,
            )
        ]

    @app.post(
        "/api/v1/trust/recalculate",
        response_model=TrustRecalculationRunResponse,
        status_code=201,
        tags=["trust"],
    )
    async def recalculate_trust(
        body: TrustRecalculateRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustRecalculationRunResponse:
        """Recalculate trust scores from current audit and trust events."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = TrustRepository(connection, organization_id, environment_id)
                run = TrustScoreRecalculator(repository).recalculate(
                    agent_id=body.agent_id if body is not None else None
                )
                return trust_recalculation_run_response(run)
        except TrustAgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/trust/rules",
        response_model=list[TrustRuleResponse],
        tags=["trust"],
    )
    async def list_trust_rules(
        enabled: bool | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[TrustRuleResponse]:
        """List trust signal mapping rules."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = TrustRepository(connection, organization_id, environment_id)
            repository.seed_default_rules()
            rows = repository.list_rules(enabled=enabled)
            return [trust_rule_response(row) for row in rows]

    @app.patch(
        "/api/v1/trust/rules/{rule_id}",
        response_model=TrustRuleResponse,
        tags=["trust"],
    )
    async def patch_trust_rule(
        rule_id: str,
        body: TrustRulePatchRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustRuleResponse:
        """Patch trust rule controls."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = TrustRepository(connection, organization_id, environment_id)
                return trust_rule_response(repository.update_rule(rule_id, body))
        except TrustRuleNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/trust/thresholds",
        response_model=list[TrustThresholdResponse],
        tags=["trust"],
    )
    async def list_trust_thresholds(
        threshold_type: str | None = None,
        enabled: bool | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[TrustThresholdResponse]:
        """List protected-action trust thresholds."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = TrustRepository(connection, organization_id, environment_id)
            repository.seed_default_thresholds()
            return [
                trust_threshold_response(row)
                for row in repository.list_thresholds(
                    threshold_type=threshold_type,
                    enabled=enabled,
                )
            ]

    @app.post(
        "/api/v1/trust/thresholds",
        response_model=TrustThresholdResponse,
        status_code=201,
        tags=["trust"],
    )
    async def create_trust_threshold(
        body: TrustThresholdCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustThresholdResponse:
        """Create a protected-action trust threshold."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                row = TrustRepository(connection, organization_id, environment_id).create_threshold(body)
                return trust_threshold_response(row)
        except DuplicateTrustThresholdError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.patch(
        "/api/v1/trust/thresholds/{threshold_id}",
        response_model=TrustThresholdResponse,
        tags=["trust"],
    )
    async def patch_trust_threshold(
        threshold_id: str,
        body: TrustThresholdPatchRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustThresholdResponse:
        """Patch a protected-action trust threshold."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                row = TrustRepository(connection, organization_id, environment_id).update_threshold(
                    threshold_id,
                    body,
                )
                return trust_threshold_response(row)
        except TrustThresholdNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DuplicateTrustThresholdError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/trust/handshakes/simulate",
        response_model=TrustHandshakeResponse,
        status_code=201,
        tags=["trust"],
    )
    async def simulate_trust_handshake(
        body: TrustHandshakeRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustHandshakeResponse:
        """Simulate and persist an explainable trust handshake."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = TrustRepository(connection, organization_id, environment_id)
                handshake = TrustHandshakeService(repository).evaluate_and_record(
                    body,
                    correlation_id=context.correlation_id,
                    mode="simulate",
                )
                AuditEventRepository(connection).insert(
                    _trust_handshake_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        handshake=handshake,
                        correlation_id=context.correlation_id,
                    )
                )
                return handshake
        except TrustAgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/trust/handshakes/record",
        response_model=TrustHandshakeResponse,
        status_code=201,
        tags=["trust"],
    )
    async def record_trust_handshake(
        body: TrustHandshakeRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustHandshakeResponse:
        """Record a real mesh/framework trust handshake attempt."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = TrustRepository(connection, organization_id, environment_id)
                handshake = TrustHandshakeService(repository).evaluate_and_record(
                    body,
                    correlation_id=context.correlation_id,
                    mode="record",
                )
                AuditEventRepository(connection).insert(
                    _trust_handshake_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        handshake=handshake,
                        correlation_id=context.correlation_id,
                    )
                )
                return handshake
        except TrustAgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/trust/handshakes",
        response_model=list[TrustHandshakeResponse],
        tags=["trust"],
    )
    async def list_trust_handshakes(
        source_agent_id: str | None = None,
        target_agent_id: str | None = None,
        result: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[TrustHandshakeResponse]:
        """List persisted trust handshakes."""

        organization_id = _require_organization_id(current_user)
        repository = TrustRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            trust_handshake_response(row)
            for row in repository.list_handshake_events(
                source_agent_id=source_agent_id,
                target_agent_id=target_agent_id,
                result=result,
                limit=limit,
                offset=offset,
            )
        ]

    @app.post(
        "/api/v1/mesh/messages",
        response_model=MeshMessageResponse,
        status_code=201,
        tags=["mesh"],
    )
    async def ingest_mesh_message(
        body: MeshMessageCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MeshMessageResponse:
        """Ingest an inter-agent mesh message from an SDK or adapter."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                message = mesh_message_response(
                    MeshRepository(connection, organization_id, environment_id).create_message(body)
                )
                if message.decision.lower() in {"deny", "denied", "blocked", "escalate", "escalated"}:
                    AuditEventRepository(connection).insert(
                        _mesh_message_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            message=message,
                            correlation_id=context.correlation_id,
                        )
                    )
                return message
        except MeshAgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/mesh/handoffs",
        response_model=MeshHandoffResponse,
        status_code=201,
        tags=["mesh"],
    )
    async def ingest_mesh_handoff(
        body: MeshHandoffCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MeshHandoffResponse:
        """Ingest a mesh handoff attempt from an SDK or adapter."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                return mesh_handoff_response(
                    MeshRepository(connection, organization_id, environment_id).create_handoff(body)
                )
        except MeshAgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/mesh/messages",
        response_model=list[MeshMessageResponse],
        tags=["mesh"],
    )
    async def list_mesh_messages(
        source_agent_id: str | None = None,
        target_agent_id: str | None = None,
        protocol: str | None = None,
        decision: str | None = None,
        action: str | None = None,
        correlation_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[MeshMessageResponse]:
        """List mesh messages with feed filters."""

        organization_id = _require_organization_id(current_user)
        repository = MeshRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            mesh_message_response(row)
            for row in repository.list_messages(
                source_agent_id=source_agent_id,
                target_agent_id=target_agent_id,
                protocol=protocol,
                decision=decision,
                action=action,
                correlation_id=correlation_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                offset=offset,
            )
        ]

    @app.get(
        "/api/v1/mesh/handoffs",
        response_model=list[MeshHandoffResponse],
        tags=["mesh"],
    )
    async def list_mesh_handoffs(
        source_agent_id: str | None = None,
        target_agent_id: str | None = None,
        status: str | None = None,
        correlation_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[MeshHandoffResponse]:
        """List mesh handoffs."""

        organization_id = _require_organization_id(current_user)
        repository = MeshRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            mesh_handoff_response(row)
            for row in repository.list_handoffs(
                source_agent_id=source_agent_id,
                target_agent_id=target_agent_id,
                status=status,
                correlation_id=correlation_id,
                limit=limit,
                offset=offset,
            )
        ]

    @app.get(
        "/api/v1/mesh/topology",
        response_model=MeshTopologyResponse,
        tags=["mesh"],
    )
    async def get_mesh_topology(
        start_time: str | None = None,
        end_time: str | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> MeshTopologyResponse:
        """Return aggregated mesh topology for the selected time range."""

        organization_id = _require_organization_id(current_user)
        repository = MeshRepository(_audit_database().connect(), organization_id, environment_id)
        return MeshTopologyService(repository).get_topology(
            start_time=start_time,
            end_time=end_time,
        )

    @app.post(
        "/api/v1/mesh/protocol-bridges",
        response_model=ProtocolBridgeResponse,
        status_code=201,
        tags=["mesh"],
    )
    async def create_protocol_bridge(
        body: ProtocolBridgeCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ProtocolBridgeResponse:
        """Register a protocol bridge configuration."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            return protocol_bridge_response(
                MeshRepository(connection, organization_id, environment_id).create_protocol_bridge(body)
            )

    @app.get(
        "/api/v1/mesh/protocol-bridges",
        response_model=list[ProtocolBridgeResponse],
        tags=["mesh"],
    )
    async def list_protocol_bridges(
        bridge_type: str | None = None,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ProtocolBridgeResponse]:
        """List protocol bridge configurations."""

        organization_id = _require_organization_id(current_user)
        repository = MeshRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            protocol_bridge_response(
                row,
                current_health=protocol_bridge_health_check_response(latest)
                if (latest := repository.latest_protocol_bridge_health_check(row["id"])) is not None
                else None,
            )
            for row in repository.list_protocol_bridges(
                bridge_type=bridge_type,
                status=status,
                limit=limit,
                offset=offset,
            )
        ]

    @app.get(
        "/api/v1/mesh/protocol-bridges/{bridge_id}",
        response_model=ProtocolBridgeResponse,
        tags=["mesh"],
    )
    async def get_protocol_bridge(
        bridge_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> ProtocolBridgeResponse:
        """Get one protocol bridge configuration."""

        organization_id = _require_organization_id(current_user)
        repository = MeshRepository(_audit_database().connect(), organization_id, environment_id)
        row = repository.get_protocol_bridge(bridge_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Protocol bridge not found.")
        latest = repository.latest_protocol_bridge_health_check(bridge_id)
        routes = [
            protocol_bridge_route_response(route)
            for route in repository.list_protocol_bridge_routes(bridge_id)
        ]
        return protocol_bridge_response(
            row,
            current_health=protocol_bridge_health_check_response(latest) if latest is not None else None,
            routes=routes,
        )

    @app.patch(
        "/api/v1/mesh/protocol-bridges/{bridge_id}",
        response_model=ProtocolBridgeResponse,
        tags=["mesh"],
    )
    async def patch_protocol_bridge(
        bridge_id: str,
        body: ProtocolBridgePatchRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ProtocolBridgeResponse:
        """Patch a protocol bridge configuration."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                return protocol_bridge_response(
                    MeshRepository(connection, organization_id, environment_id).update_protocol_bridge(
                        bridge_id,
                        body,
                    )
                )
        except ProtocolBridgeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/mesh/protocol-bridges/{bridge_id}/routes",
        response_model=ProtocolBridgeRouteResponse,
        status_code=201,
        tags=["mesh"],
    )
    async def create_protocol_bridge_route(
        bridge_id: str,
        body: ProtocolBridgeRouteCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ProtocolBridgeRouteResponse:
        """Create a route through a configured protocol bridge."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = MeshRepository(connection, organization_id, environment_id)
                route = protocol_bridge_route_response(
                    repository.create_protocol_bridge_route(bridge_id, body)
                )
                AuditEventRepository(connection).insert(
                    _protocol_bridge_route_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        route=route,
                        correlation_id=context.correlation_id,
                    )
                )
                return route
        except (
            MeshAgentNotFoundError,
            ProtocolBridgeNotFoundError,
            ProtocolBridgeReferenceNotFoundError,
        ) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/mesh/protocol-bridges/{bridge_id}/health-check",
        response_model=ProtocolBridgeHealthCheckResponse,
        status_code=201,
        tags=["mesh"],
    )
    async def run_protocol_bridge_health_check(
        bridge_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> ProtocolBridgeHealthCheckResponse:
        """Run and persist an honest health check for a configured protocol bridge."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = MeshRepository(connection, organization_id, environment_id)
                bridge = repository.get_protocol_bridge(bridge_id)
                if bridge is None:
                    raise ProtocolBridgeNotFoundError("Protocol bridge not found.")
                result = ProtocolBridgeHealthAdapter().check(bridge)
                return protocol_bridge_health_check_response(
                    repository.create_protocol_bridge_health_check(
                        bridge_id,
                        status=result.status,
                        latency_ms=result.latency_ms,
                        message=result.message,
                    )
                )
        except ProtocolBridgeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/mcp/servers",
        response_model=MCPServerResponse,
        status_code=201,
        tags=["mcp"],
    )
    async def create_mcp_server(
        body: MCPServerCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPServerResponse:
        """Register an MCP server as a product resource."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                server = mcp_server_response(
                    MCPRegistryRepository(connection, organization_id, environment_id).create_server(
                        body
                    )
                )
                AuditEventRepository(connection).insert(
                    _mcp_server_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="mcp.server.created",
                        server=server,
                        correlation_id=context.correlation_id,
                    )
                )
                return server
        except MCPRegistryReferenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except DuplicateMCPServerNameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/v1/mcp/servers",
        response_model=list[MCPServerResponse],
        tags=["mcp"],
    )
    async def list_mcp_servers(
        status: str | None = None,
        owner_user_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[MCPServerResponse]:
        """List MCP servers in the selected environment."""

        organization_id = _require_organization_id(current_user)
        repository = MCPRegistryRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            mcp_server_response(row)
            for row in repository.list_servers(
                status=status,
                owner_user_id=owner_user_id,
                limit=limit,
                offset=offset,
            )
        ]

    @app.get(
        "/api/v1/mcp/servers/{server_id}",
        response_model=MCPServerResponse,
        tags=["mcp"],
    )
    async def get_mcp_server(
        server_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPServerResponse:
        """Get one MCP server in the selected environment."""

        organization_id = _require_organization_id(current_user)
        row = MCPRegistryRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        ).get_server(server_id)
        if row is None:
            raise HTTPException(status_code=404, detail="MCP server not found.")
        return mcp_server_response(row)

    @app.patch(
        "/api/v1/mcp/servers/{server_id}",
        response_model=MCPServerResponse,
        tags=["mcp"],
    )
    async def patch_mcp_server(
        server_id: str,
        body: MCPServerPatchRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPServerResponse:
        """Patch an MCP server registry record."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = MCPRegistryRepository(connection, organization_id, environment_id)
                existing = repository.get_server(server_id)
                if existing is None:
                    raise MCPServerNotFoundError("MCP server not found.")
                previous_status = existing["status"]
                server = mcp_server_response(repository.update_server(server_id, body))
                AuditEventRepository(connection).insert(
                    _mcp_server_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="mcp.server.updated",
                        server=server,
                        correlation_id=context.correlation_id,
                        previous_status=previous_status,
                    )
                )
                return server
        except MCPServerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MCPRegistryReferenceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except DuplicateMCPServerNameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/mcp/servers/{server_id}/discover-tools",
        response_model=MCPToolDiscoveryResponse,
        status_code=201,
        tags=["mcp"],
    )
    async def discover_mcp_server_tools(
        server_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPToolDiscoveryResponse:
        """Discover and persist tool definitions for one MCP server."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = MCPRegistryRepository(connection, organization_id, environment_id)
                server = repository.get_server(server_id)
                if server is None:
                    raise MCPServerNotFoundError("MCP server not found.")
                raw_tools = DemoMCPToolDiscoveryAdapter().discover_tools(server)
                normalized_tools = [normalize_tool_definition(tool) for tool in raw_tools]
                result = repository.persist_discovered_tools(server_id, normalized_tools)
                for change in result.schema_changes:
                    if change.previous_schema_hash is None:
                        continue
                    AuditEventRepository(connection).insert(
                        _mcp_tool_schema_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            change=change,
                            correlation_id=context.correlation_id,
                        )
                    )
                tools = [
                    _mcp_tool_response(repository, row, include_versions=True)
                    for row in result.rows
                ]
                return MCPToolDiscoveryResponse(
                    server_id=server_id,
                    discovered_count=len(tools),
                    tools=tools,
                )
        except MCPServerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/mcp/tools",
        response_model=list[MCPToolResponse],
        tags=["mcp"],
    )
    async def list_mcp_tools(
        server_id: str | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[MCPToolResponse]:
        """List discovered MCP tools in the selected environment."""

        organization_id = _require_organization_id(current_user)
        repository = MCPRegistryRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            _mcp_tool_response(repository, row)
            for row in repository.list_tools(
                server_id=server_id,
                status=status,
                risk_level=risk_level,
                limit=limit,
                offset=offset,
            )
        ]

    @app.get(
        "/api/v1/mcp/tools/{tool_id}",
        response_model=MCPToolResponse,
        tags=["mcp"],
    )
    async def get_mcp_tool(
        tool_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPToolResponse:
        """Get one discovered MCP tool with version history."""

        organization_id = _require_organization_id(current_user)
        repository = MCPRegistryRepository(_audit_database().connect(), organization_id, environment_id)
        row = repository.get_tool(tool_id)
        if row is None:
            raise HTTPException(status_code=404, detail="MCP tool not found.")
        return _mcp_tool_response(repository, row, include_versions=True)

    @app.post(
        "/api/v1/mcp/servers/{server_id}/scan",
        response_model=MCPScanRunResponse,
        status_code=201,
        tags=["mcp"],
    )
    async def run_mcp_security_scan(
        server_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPScanRunResponse:
        """Run a demo-safe MCP security scan and persist results synchronously."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = MCPRegistryRepository(connection, organization_id, environment_id)
                server = repository.get_server(server_id)
                if server is None:
                    raise MCPServerNotFoundError("MCP server not found.")
                run = _mcp_scan_run_response(repository, repository.create_scan_run(server_id))
                audit = AuditEventRepository(connection)
                audit.insert(
                    _mcp_scan_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="mcp.scan.started",
                        scan=run,
                        correlation_id=context.correlation_id,
                    )
                )
                try:
                    query = parse_qs(urlparse(server["endpoint_url"]).query)
                    if query.get("scan", [""])[0] == "error":
                        raise RuntimeError("Demo scanner failure fixture requested.")
                    tool_rows = repository.list_tools(server_id=server_id, limit=500)
                    tools = [
                        _mcp_tool_response(repository, row, include_versions=False).model_dump(
                            by_alias=True
                        )
                        for row in tool_rows
                    ]
                    scan_result = MCPScannerAdapter().scan_tools(tools)
                    for finding in scan_result.findings:
                        repository.create_finding(run.id, finding)
                    summary = {
                        "tools_scanned": scan_result.tools_scanned,
                        "tools_flagged": scan_result.tools_flagged,
                        "finding_count": len(scan_result.findings),
                    }
                    completed = _mcp_scan_run_response(
                        repository,
                        repository.finish_scan_run(run.id, status="completed", summary=summary),
                        include_findings=True,
                    )
                    audit.insert(
                        _mcp_scan_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            event_type="mcp.scan.completed",
                            scan=completed,
                            correlation_id=context.correlation_id,
                        )
                    )
                    return completed
                except Exception as exc:
                    failed = _mcp_scan_run_response(
                        repository,
                        repository.finish_scan_run(
                            run.id,
                            status="failed",
                            summary={"tools_scanned": 0, "tools_flagged": 0, "finding_count": 0},
                            error_message=str(exc),
                        ),
                    )
                    audit.insert(
                        _mcp_scan_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            event_type="mcp.scan.failed",
                            scan=failed,
                            correlation_id=context.correlation_id,
                        )
                    )
                    return failed
        except MCPServerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/mcp/scans",
        response_model=list[MCPScanRunResponse],
        tags=["mcp"],
    )
    async def list_mcp_scan_runs(
        server_id: str | None = None,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[MCPScanRunResponse]:
        """List MCP security scan runs."""

        organization_id = _require_organization_id(current_user)
        repository = MCPRegistryRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            _mcp_scan_run_response(repository, row)
            for row in repository.list_scan_runs(
                server_id=server_id,
                status=status,
                limit=limit,
                offset=offset,
            )
        ]

    @app.get(
        "/api/v1/mcp/scans/{scan_run_id}",
        response_model=MCPScanRunResponse,
        tags=["mcp"],
    )
    async def get_mcp_scan_run(
        scan_run_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPScanRunResponse:
        """Get one MCP security scan run with findings."""

        organization_id = _require_organization_id(current_user)
        repository = MCPRegistryRepository(_audit_database().connect(), organization_id, environment_id)
        row = repository.get_scan_run(scan_run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="MCP scan run not found.")
        return _mcp_scan_run_response(repository, row, include_findings=True)

    @app.get(
        "/api/v1/mcp/findings",
        response_model=list[MCPFindingResponse],
        tags=["mcp"],
    )
    async def list_mcp_findings(
        scan_run_id: str | None = None,
        server_id: str | None = None,
        tool_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[MCPFindingResponse]:
        """List MCP security findings."""

        organization_id = _require_organization_id(current_user)
        repository = MCPRegistryRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            mcp_finding_response(row)
            for row in repository.list_findings(
                scan_run_id=scan_run_id,
                server_id=server_id,
                tool_id=tool_id,
                status=status,
                severity=severity,
                limit=limit,
                offset=offset,
            )
        ]

    @app.post(
        "/api/v1/mcp/findings/{finding_id}/accept-risk",
        response_model=MCPFindingResponse,
        tags=["mcp"],
    )
    async def accept_mcp_finding_risk(
        finding_id: str,
        body: MCPFindingActionRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPFindingResponse:
        """Accept an MCP finding risk for the current tool schema version."""

        if not body.reason:
            raise HTTPException(status_code=400, detail="reason is required.")
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = MCPRegistryRepository(connection, organization_id, environment_id)
                previous = repository.get_finding(finding_id)
                if previous is None:
                    raise MCPFindingNotFoundError("MCP finding not found.")
                updated = mcp_finding_response(
                    repository.update_finding_status(
                        finding_id,
                        status="accepted_risk",
                        reason=body.reason,
                        actor_id=current_user.id,
                    )
                )
                AuditEventRepository(connection).insert(
                    _mcp_finding_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="mcp.finding.accepted_risk",
                        finding=updated,
                        correlation_id=context.correlation_id,
                        previous_status=previous["status"],
                        reason=body.reason,
                    )
                )
                return updated
        except MCPFindingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MCPFindingLifecycleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/mcp/findings/{finding_id}/resolve",
        response_model=MCPFindingResponse,
        tags=["mcp"],
    )
    async def resolve_mcp_finding(
        finding_id: str,
        body: MCPFindingActionRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPFindingResponse:
        """Mark an MCP finding as resolved."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = MCPRegistryRepository(connection, organization_id, environment_id)
                previous = repository.get_finding(finding_id)
                if previous is None:
                    raise MCPFindingNotFoundError("MCP finding not found.")
                updated = mcp_finding_response(
                    repository.update_finding_status(
                        finding_id,
                        status="resolved",
                        reason=body.reason,
                        actor_id=current_user.id,
                    )
                )
                AuditEventRepository(connection).insert(
                    _mcp_finding_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="mcp.finding.resolved",
                        finding=updated,
                        correlation_id=context.correlation_id,
                        previous_status=previous["status"],
                        reason=body.reason,
                    )
                )
                return updated
        except MCPFindingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MCPFindingLifecycleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/mcp/findings/{finding_id}/false-positive",
        response_model=MCPFindingResponse,
        tags=["mcp"],
    )
    async def mark_mcp_finding_false_positive(
        finding_id: str,
        body: MCPFindingActionRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPFindingResponse:
        """Mark an MCP finding as a false positive with a required reason."""

        if not body.reason:
            raise HTTPException(status_code=400, detail="reason is required.")
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = MCPRegistryRepository(connection, organization_id, environment_id)
                previous = repository.get_finding(finding_id)
                if previous is None:
                    raise MCPFindingNotFoundError("MCP finding not found.")
                updated = mcp_finding_response(
                    repository.update_finding_status(
                        finding_id,
                        status="false_positive",
                        reason=body.reason,
                        actor_id=current_user.id,
                    )
                )
                AuditEventRepository(connection).insert(
                    _mcp_finding_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="mcp.finding.false_positive",
                        finding=updated,
                        correlation_id=context.correlation_id,
                        previous_status=previous["status"],
                        reason=body.reason,
                    )
                )
                return updated
        except MCPFindingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MCPFindingLifecycleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/mcp/proxy/call",
        response_model=MCPToolCallResponse,
        status_code=201,
        tags=["mcp"],
    )
    async def create_mcp_proxy_call(
        body: MCPProxyCallRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPToolCallResponse:
        """Evaluate and persist a governed MCP proxy tool call."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = MCPProxyRepository(connection, organization_id, environment_id)
                row = MCPProxyDecisionService(repository).evaluate_and_record(
                    body,
                    request_correlation_id=context.correlation_id,
                )
                response = mcp_tool_call_response(row)
                AuditEventRepository(connection).insert(
                    _mcp_proxy_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        call=response,
                        correlation_id=context.correlation_id,
                    )
                )
                if response.sanitizer_action:
                    AuditEventRepository(connection).insert(
                        _mcp_response_sanitizer_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            call=response,
                            correlation_id=context.correlation_id,
                        )
                    )
                _record_mcp_policy_evaluation(
                    connection=connection,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    call=response,
                )
                return response
        except MCPProxyReferenceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/mcp/traffic",
        response_model=list[MCPToolCallResponse],
        tags=["mcp"],
    )
    async def list_mcp_proxy_traffic(
        decision: str | None = None,
        server_id: str | None = None,
        tool_id: str | None = None,
        source_agent_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[MCPToolCallResponse]:
        """List product-visible MCP proxy traffic."""

        organization_id = _require_organization_id(current_user)
        repository = MCPProxyRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            mcp_tool_call_response(row)
            for row in repository.list_tool_calls(
                decision=decision,
                server_id=server_id,
                tool_id=tool_id,
                source_agent_id=source_agent_id,
                limit=limit,
                offset=offset,
            )
        ]

    @app.get(
        "/api/v1/mcp/approvals",
        response_model=list[MCPApprovalResponse],
        tags=["mcp"],
    )
    async def list_mcp_approvals(
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[MCPApprovalResponse]:
        """List MCP approval records with their queued tool-call context."""

        organization_id = _require_organization_id(current_user)
        repository = MCPProxyRepository(_audit_database().connect(), organization_id, environment_id)
        responses: list[MCPApprovalResponse] = []
        for row in repository.list_approvals(status=status, limit=limit, offset=offset):
            call_row = repository.get_tool_call(row["tool_call_id"])
            responses.append(
                mcp_approval_response(
                    row,
                    tool_call=mcp_tool_call_response(call_row) if call_row is not None else None,
                )
            )
        return responses

    @app.post(
        "/api/v1/mcp/approvals/{approval_id}/approve",
        response_model=MCPApprovalResponse,
        tags=["mcp"],
    )
    async def approve_mcp_approval(
        approval_id: str,
        body: MCPApprovalDecisionRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPApprovalResponse:
        """Approve and release a queued MCP tool call."""

        _require_mcp_approval_actor(current_user)
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = MCPProxyRepository(connection, organization_id, environment_id)
                row = repository.decide_approval(
                    approval_id,
                    status="approved",
                    actor_id=current_user.id,
                    reason=body.reason,
                )
                call_row = repository.get_tool_call(row["tool_call_id"])
                response = mcp_approval_response(
                    row,
                    tool_call=mcp_tool_call_response(call_row) if call_row is not None else None,
                )
                AuditEventRepository(connection).insert(
                    _mcp_approval_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="mcp.approval.approved",
                        approval=response,
                        correlation_id=context.correlation_id,
                    )
                )
                if response.tool_call is not None and response.tool_call.sanitizer_action:
                    AuditEventRepository(connection).insert(
                        _mcp_response_sanitizer_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            call=response.tool_call,
                            correlation_id=context.correlation_id,
                        )
                    )
                return response
        except MCPApprovalNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (MCPApprovalDecisionError, MCPProxyReferenceError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/mcp/approvals/{approval_id}/deny",
        response_model=MCPApprovalResponse,
        tags=["mcp"],
    )
    async def deny_mcp_approval(
        approval_id: str,
        body: MCPApprovalDecisionRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPApprovalResponse:
        """Deny a queued MCP tool call."""

        _require_mcp_approval_actor(current_user)
        if not body.reason:
            raise HTTPException(status_code=400, detail="reason is required.")
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = MCPProxyRepository(connection, organization_id, environment_id)
                row = repository.decide_approval(
                    approval_id,
                    status="denied",
                    actor_id=current_user.id,
                    reason=body.reason,
                )
                call_row = repository.get_tool_call(row["tool_call_id"])
                response = mcp_approval_response(
                    row,
                    tool_call=mcp_tool_call_response(call_row) if call_row is not None else None,
                )
                AuditEventRepository(connection).insert(
                    _mcp_approval_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="mcp.approval.denied",
                        approval=response,
                        correlation_id=context.correlation_id,
                    )
                )
                return response
        except MCPApprovalNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (MCPApprovalDecisionError, MCPProxyReferenceError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/mcp/rate-limits",
        response_model=list[MCPRateLimitResponse],
        tags=["mcp"],
    )
    async def list_mcp_rate_limits(
        target_type: str | None = None,
        target_id: str | None = None,
        enabled: bool | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[MCPRateLimitResponse]:
        """List MCP proxy rate-limit configuration."""

        organization_id = _require_organization_id(current_user)
        repository = MCPProxyRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            mcp_rate_limit_response(row)
            for row in repository.list_rate_limits(
                target_type=target_type,
                target_id=target_id,
                enabled=enabled,
                limit=limit,
                offset=offset,
            )
        ]

    @app.post(
        "/api/v1/mcp/rate-limits",
        response_model=MCPRateLimitResponse,
        status_code=201,
        tags=["mcp"],
    )
    async def create_mcp_rate_limit(
        body: MCPRateLimitCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MCPRateLimitResponse:
        """Create an MCP proxy rate-limit configuration row."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MCPProxyRepository(connection, organization_id, environment_id)
            return mcp_rate_limit_response(repository.create_rate_limit(body))

    @app.post(
        "/api/v1/trust/cards",
        response_model=TrustCardResponse,
        status_code=201,
        tags=["trust"],
    )
    async def issue_trust_card(
        body: TrustCardIssueRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustCardResponse:
        """Issue a signed trust card for an agent."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                card = TrustCardIssuer(connection, organization_id, environment_id).issue(body)
                AuditEventRepository(connection).insert(
                    _trust_card_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="trust.card.issued",
                        actor_id=current_user.id,
                        card=card,
                        correlation_id=context.correlation_id,
                    )
                )
                return trust_card_response(card)
        except AgentNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/trust/cards",
        response_model=list[TrustCardResponse],
        tags=["trust"],
    )
    async def list_trust_cards(
        agent_id: str | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[TrustCardResponse]:
        """List persisted trust cards."""

        organization_id = _require_organization_id(current_user)
        repository = TrustCardRepository(_audit_database().connect(), organization_id, environment_id)
        return [trust_card_response(row) for row in repository.list_cards(agent_id=agent_id)]

    @app.get(
        "/api/v1/trust/cards/{card_id}",
        response_model=TrustCardResponse,
        tags=["trust"],
    )
    async def get_trust_card(
        card_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustCardResponse:
        """Get a single trust card."""

        organization_id = _require_organization_id(current_user)
        row = TrustCardRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        ).get_card(card_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Trust card not found.")
        return trust_card_response(row)

    @app.post(
        "/api/v1/trust/cards/{card_id}/verify",
        response_model=TrustCardVerifyResponse,
        tags=["trust"],
    )
    async def verify_trust_card(
        card_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustCardVerifyResponse:
        """Verify a trust card signature and revocation status."""

        organization_id = _require_organization_id(current_user)
        try:
            return TrustCardRepository(
                _audit_database().connect(),
                organization_id,
                environment_id,
            ).verify_card(card_id)
        except TrustCardNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/trust/cards/{card_id}/revoke",
        response_model=TrustCardResponse,
        tags=["trust"],
    )
    async def revoke_trust_card(
        card_id: str,
        body: TrustCardRevokeRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustCardResponse:
        """Revoke a trust card."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = TrustCardRepository(connection, organization_id, environment_id)
                card = repository.revoke_card(card_id, reason=body.reason, revoked_by=current_user.id)
                AuditEventRepository(connection).insert(
                    _trust_card_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="trust.card.revoked",
                        actor_id=current_user.id,
                        card=card,
                        correlation_id=context.correlation_id,
                        payload_json={"reason": body.reason},
                    )
                )
                return trust_card_response(card)
        except TrustCardNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/agents/{agent_id}/trust-card",
        response_model=AgentTrustCardResponse,
        tags=["trust"],
    )
    async def get_agent_current_trust_card(
        agent_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentTrustCardResponse:
        """Return the latest valid non-revoked trust card for an agent."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            agent = AgentRegistryRepository(connection, organization_id, environment_id).get(agent_id)
            if agent is None:
                raise HTTPException(status_code=404, detail="Agent not found.")
            row = TrustCardRepository(connection, organization_id, environment_id).current_card(agent_id)
            if row is None:
                return AgentTrustCardResponse(
                    agent_id=agent_id,
                    card=None,
                    warning="No valid trust card exists for this agent.",
                )
            return AgentTrustCardResponse(agent_id=agent_id, card=trust_card_response(row))

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

    @app.post(
        "/api/v1/runtime/sessions",
        response_model=RuntimeSessionResponse,
        status_code=201,
        tags=["runtime"],
    )
    async def create_runtime_session(
        body: RuntimeSessionCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> RuntimeSessionResponse:
        """Start a runtime session for an active agent."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = RuntimeRepository(connection, organization_id, environment_id)
                session = runtime_session_response(repository.create_session(body))
                AuditEventRepository(connection).insert(
                    _runtime_session_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="runtime.session.started",
                        session=session,
                        correlation_id=context.correlation_id,
                    )
                )
                return session
        except RuntimeAgentNotActiveError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/runtime/sessions",
        response_model=list[RuntimeSessionResponse],
        tags=["runtime"],
    )
    async def list_runtime_sessions(
        state: str | None = None,
        agent_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[RuntimeSessionResponse]:
        """List runtime sessions in the selected environment."""

        organization_id = _require_organization_id(current_user)
        repository = RuntimeRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            runtime_session_response(row)
            for row in repository.list_sessions(state=state, agent_id=agent_id, limit=limit, offset=offset)
        ]

    @app.get(
        "/api/v1/runtime/sessions/{session_id}",
        response_model=RuntimeSessionResponse,
        tags=["runtime"],
    )
    async def get_runtime_session(
        session_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> RuntimeSessionResponse:
        """Get one runtime session and its action timeline."""

        organization_id = _require_organization_id(current_user)
        repository = RuntimeRepository(_audit_database().connect(), organization_id, environment_id)
        row = repository.get_session(session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Runtime session not found.")
        actions = []
        for action_row in repository.list_actions_for_session(session_id):
            decision_row = repository.get_ring_decision_for_action(action_row["id"])
            actions.append(
                runtime_action_response(
                    action_row,
                    ring_decision=runtime_ring_decision_response(decision_row)
                    if decision_row is not None
                    else None,
                )
            )
        return runtime_session_response(row, actions=actions)

    @app.post(
        "/api/v1/runtime/sessions/{session_id}/end",
        response_model=RuntimeSessionResponse,
        tags=["runtime"],
    )
    async def end_runtime_session(
        session_id: str,
        body: RuntimeSessionEndRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> RuntimeSessionResponse:
        """End and archive an active runtime session."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = RuntimeRepository(connection, organization_id, environment_id)
                session = runtime_session_response(repository.end_session(session_id, reason=body.reason))
                AuditEventRepository(connection).insert(
                    _runtime_session_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="runtime.session.ended",
                        session=session,
                        correlation_id=context.correlation_id,
                    )
                )
                return session
        except RuntimeSessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeSessionStateError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/runtime/sessions/{session_id}/actions",
        response_model=RuntimeActionResponse,
        status_code=201,
        tags=["runtime"],
    )
    async def create_runtime_action(
        session_id: str,
        body: RuntimeActionCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> RuntimeActionResponse:
        """Evaluate a runtime action through ring enforcement and persist the decision."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = RuntimeRepository(connection, organization_id, environment_id)
                action_row, decision_row = RuntimeRingDecisionService(repository).evaluate_and_record(
                    session_id,
                    body,
                    correlation_id=context.correlation_id,
                )
                decision = runtime_ring_decision_response(decision_row)
                action = runtime_action_response(action_row, ring_decision=decision)
                AuditEventRepository(connection).insert(
                    _runtime_action_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        action=action,
                        correlation_id=context.correlation_id,
                    )
                )
                _record_runtime_policy_evaluation(
                    connection=connection,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    action=action,
                )
                return action
        except RuntimeSessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeSessionStateError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/runtime/ring-decisions",
        response_model=list[RuntimeRingDecisionResponse],
        tags=["runtime"],
    )
    async def list_runtime_ring_decisions(
        result: str | None = None,
        session_id: str | None = None,
        agent_id: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[RuntimeRingDecisionResponse]:
        """List persisted runtime ring decisions."""

        organization_id = _require_organization_id(current_user)
        repository = RuntimeRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            runtime_ring_decision_response(row)
            for row in repository.list_ring_decisions(
                result=result,
                session_id=session_id,
                agent_id=agent_id,
                limit=limit,
                offset=offset,
            )
        ]

    @app.get(
        "/api/v1/runtime/ring-rules",
        response_model=list[RuntimeRingRuleResponse],
        tags=["runtime"],
    )
    async def list_runtime_ring_rules(
        enabled: bool | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[RuntimeRingRuleResponse]:
        """List runtime ring override rules."""

        organization_id = _require_organization_id(current_user)
        repository = RuntimeRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            runtime_ring_rule_response(row)
            for row in repository.list_ring_rules(enabled=enabled, limit=limit, offset=offset)
        ]

    @app.post(
        "/api/v1/runtime/ring-rules",
        response_model=RuntimeRingRuleResponse,
        status_code=201,
        tags=["runtime"],
    )
    async def create_runtime_ring_rule(
        body: RuntimeRingRuleCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> RuntimeRingRuleResponse:
        """Create a runtime ring override rule."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = RuntimeRepository(connection, organization_id, environment_id)
            rule = runtime_ring_rule_response(repository.create_ring_rule(body))
            AuditEventRepository(connection).insert(
                _runtime_ring_rule_audit_event(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    actor_id=current_user.id,
                    rule=rule,
                    correlation_id=context.correlation_id,
                )
            )
            return rule

    @app.post(
        "/api/v1/runtime/sandbox-profiles",
        response_model=SandboxProfileResponse,
        status_code=201,
        tags=["runtime"],
    )
    async def create_runtime_sandbox_profile(
        body: SandboxProfileCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> SandboxProfileResponse:
        """Create a sandbox profile for runtime actions."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = SandboxProfileRepository(connection, organization_id, environment_id)
                return sandbox_profile_response(repository.create_profile(body))
        except DuplicateSandboxProfileNameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except SandboxProfileValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/runtime/sandbox-profiles",
        response_model=list[SandboxProfileResponse],
        tags=["runtime"],
    )
    async def list_runtime_sandbox_profiles(
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[SandboxProfileResponse]:
        """List sandbox profiles."""

        organization_id = _require_organization_id(current_user)
        try:
            repository = SandboxProfileRepository(_audit_database().connect(), organization_id, environment_id)
            return [
                sandbox_profile_response(row)
                for row in repository.list_profiles(status=status, limit=limit, offset=offset)
            ]
        except SandboxProfileValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch(
        "/api/v1/runtime/sandbox-profiles/{profile_id}",
        response_model=SandboxProfileResponse,
        tags=["runtime"],
    )
    async def patch_runtime_sandbox_profile(
        profile_id: str,
        body: SandboxProfilePatchRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> SandboxProfileResponse:
        """Patch a sandbox profile."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = SandboxProfileRepository(connection, organization_id, environment_id)
                return sandbox_profile_response(repository.patch_profile(profile_id, body))
        except SandboxProfileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DuplicateSandboxProfileNameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except SandboxProfileValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/runtime/sandbox-profiles/{profile_id}/test",
        response_model=SandboxDecisionResponse,
        tags=["runtime"],
    )
    async def test_runtime_sandbox_profile(
        profile_id: str,
        body: SandboxProfileTestRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> SandboxDecisionResponse:
        """Test sample code against a sandbox profile without executing the code."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = SandboxProfileRepository(connection, organization_id, environment_id)
                return SandboxTestAdapter(repository).test_profile(profile_id, body)
        except SandboxProfileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SandboxProfileValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/runtime/kill-switch",
        response_model=KillSwitchEventResponse,
        status_code=201,
        tags=["runtime"],
    )
    async def trigger_runtime_kill_switch(
        body: KillSwitchRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> KillSwitchEventResponse:
        """Trigger an auditable emergency stop for a supported runtime target."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = KillSwitchRepository(connection, organization_id, environment_id)
                row = repository.trigger(body, actor_id=current_user.id)
                event = kill_switch_event_response(row)
                AuditEventRepository(connection).insert(
                    _kill_switch_audit_event(
                        event=event,
                        agent_id=repository.agent_id_for_event(row),
                        correlation_id=context.correlation_id,
                    )
                )
                return event
        except KillSwitchTargetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KillSwitchValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/runtime/kill-switch/events",
        response_model=list[KillSwitchEventResponse],
        tags=["runtime"],
    )
    async def list_runtime_kill_switch_events(
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[KillSwitchEventResponse]:
        """List kill-switch events."""

        organization_id = _require_organization_id(current_user)
        repository = KillSwitchRepository(_audit_database().connect(), organization_id, environment_id)
        return [kill_switch_event_response(row) for row in repository.list_events(limit=limit, offset=offset)]

    @app.post(
        "/api/v1/runtime/sagas",
        response_model=SagaResponse,
        status_code=201,
        tags=["runtime"],
    )
    async def create_runtime_saga(
        body: SagaCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> SagaResponse:
        """Create a draft saga definition."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = SagaRepository(connection, organization_id, environment_id)
                row = repository.create_saga(body, created_by=current_user.id)
                return saga_response(row)
        except SagaStepValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/runtime/sagas",
        response_model=list[SagaResponse],
        tags=["runtime"],
    )
    async def list_runtime_sagas(
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[SagaResponse]:
        """List saga definitions."""

        organization_id = _require_organization_id(current_user)
        repository = SagaRepository(_audit_database().connect(), organization_id, environment_id)
        return [
            saga_response(row)
            for row in repository.list_sagas(status=status, limit=limit, offset=offset)
        ]

    @app.get(
        "/api/v1/runtime/sagas/{saga_id}",
        response_model=SagaResponse,
        tags=["runtime"],
    )
    async def get_runtime_saga(
        saga_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> SagaResponse:
        """Get one saga with steps and events."""

        organization_id = _require_organization_id(current_user)
        repository = SagaRepository(_audit_database().connect(), organization_id, environment_id)
        row = repository.get_saga(saga_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Saga not found.")
        return saga_response(
            row,
            steps=[saga_step_response(step) for step in repository.list_steps(saga_id)],
            events=[saga_event_response(event) for event in repository.list_events(saga_id)],
        )

    @app.post(
        "/api/v1/runtime/sagas/{saga_id}/steps",
        response_model=SagaStepResponse,
        status_code=201,
        tags=["runtime"],
    )
    async def add_runtime_saga_step(
        saga_id: str,
        body: SagaStepCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> SagaStepResponse:
        """Add an ordered step to a draft saga."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = SagaRepository(connection, organization_id, environment_id)
                return saga_step_response(repository.add_step(saga_id, body))
        except SagaNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SagaStepValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/runtime/sagas/{saga_id}/execute",
        response_model=SagaExecutionResponse,
        tags=["runtime"],
    )
    async def execute_runtime_saga(
        saga_id: str,
        body: SagaExecuteRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> SagaExecutionResponse:
        """Execute a saga using demo-safe actions and persist runtime/audit visibility."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                saga_repository = SagaRepository(connection, organization_id, environment_id)
                runtime_repository = RuntimeRepository(connection, organization_id, environment_id)
                audit_repository = AuditEventRepository(connection)
                saga_row = saga_repository.get_saga(saga_id)
                if saga_row is None:
                    raise SagaNotFoundError("Saga not found.")
                steps = saga_repository.list_steps(saga_id)
                if not steps:
                    raise SagaExecutionError("Saga must have at least one step before execution.")

                runtime_session_id = body.runtime_session_id or saga_row["runtime_session_id"]
                if runtime_session_id:
                    if runtime_repository.get_session(runtime_session_id) is None:
                        raise RuntimeSessionNotFoundError("Runtime session not found.")
                    saga_repository.link_runtime_session(saga_id, runtime_session_id)
                else:
                    session_row = runtime_repository.create_session(
                        RuntimeSessionCreateRequest(
                            agent_id=steps[0]["target_agent_id"],
                            ring=2,
                            sponsor_user_id=current_user.id,
                            metadata={"source": "saga.execute", "saga_id": saga_id},
                        )
                    )
                    session = runtime_session_response(session_row)
                    saga_repository.link_runtime_session(saga_id, session.id)
                    audit_repository.insert(
                        _runtime_session_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            event_type="runtime.session.started",
                            session=session,
                            correlation_id=context.correlation_id,
                        )
                    )

                linked_saga = _saga_detail_response(saga_repository, saga_id)
                audit_repository.insert(
                    _saga_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="saga.started",
                        saga=linked_saga,
                        correlation_id=context.correlation_id,
                        payload={"failure_actions": body.failure_actions},
                    )
                )
                result = await SagaExecutionService(
                    saga_repository,
                    action_runner=DemoSafeActionRunner(failure_actions=body.failure_actions),
                ).execute(saga_id)
                final_saga = _saga_detail_response(saga_repository, saga_id)

                step_event_by_status = {
                    "committed": "saga.step.committed",
                    "failed": "saga.step.failed",
                    "compensated": "saga.step.compensated",
                    "compensation_failed": "saga.step.compensation_failed",
                }
                for step in final_saga.steps:
                    event_type = step_event_by_status.get(step.status)
                    if event_type is None:
                        continue
                    denied = step.status in {"failed", "compensation_failed"}
                    audit_repository.insert(
                        _saga_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            event_type=event_type,
                            saga=final_saga,
                            correlation_id=context.correlation_id,
                            payload={
                                "step_id": step.id,
                                "step_order": step.step_order,
                                "action_name": step.action_name,
                                "result": step.result,
                            },
                            decision="deny" if denied else "allow",
                            severity="warning" if denied else "info",
                        )
                    )
                    audit_repository.insert(
                        _saga_runtime_action_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            saga=final_saga,
                            step=step,
                            status=step.status,
                            correlation_id=context.correlation_id,
                        )
                    )

                final_event = f"saga.{result.status}"
                audit_repository.insert(
                    _saga_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type=final_event,
                        saga=final_saga,
                        correlation_id=context.correlation_id,
                        payload={
                            "executed_step_ids": result.executed_step_ids,
                            "compensated_step_ids": result.compensated_step_ids,
                            "failed_step_id": result.failed_step_id,
                        },
                        decision="allow" if result.status == "completed" else "deny",
                        severity="info" if result.status == "completed" else "warning",
                    )
                )
                return SagaExecutionResponse(
                    saga_id=saga_id,
                    runtime_session_id=final_saga.runtime_session_id,
                    status=result.status,
                    message=result.message,
                    executed_step_ids=result.executed_step_ids,
                    compensated_step_ids=result.compensated_step_ids,
                    failed_step_id=result.failed_step_id,
                    saga=final_saga,
                )
        except SagaNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeSessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeAgentNotActiveError, SagaExecutionError, SagaStepValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/runtime/sagas/{saga_id}/cancel",
        response_model=SagaResponse,
        tags=["runtime"],
    )
    async def cancel_runtime_saga(
        saga_id: str,
        body: SagaCancelRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> SagaResponse:
        """Cancel a non-terminal saga."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        terminal_statuses = {"completed", "compensated", "failed", "compensation_failed", "cancelled"}
        try:
            with _audit_database().transaction() as connection:
                saga_repository = SagaRepository(connection, organization_id, environment_id)
                runtime_repository = RuntimeRepository(connection, organization_id, environment_id)
                audit_repository = AuditEventRepository(connection)
                saga_row = saga_repository.get_saga(saga_id)
                if saga_row is None:
                    raise SagaNotFoundError("Saga not found.")
                if saga_row["status"] in terminal_statuses:
                    raise SagaExecutionError("Terminal saga cannot be cancelled.")
                saga_repository.update_saga_status(saga_id, "cancelled", mark_finished=True)
                saga_repository.create_event(
                    saga_id,
                    event_type="saga.cancelled",
                    message="Saga cancelled.",
                    payload={"reason": body.reason},
                )
                runtime_session_id = saga_row["runtime_session_id"]
                if runtime_session_id:
                    session_row = runtime_repository.get_session(runtime_session_id)
                    if session_row is not None and session_row["state"] == "active":
                        session = runtime_session_response(
                            runtime_repository.end_session(
                                runtime_session_id,
                                reason=body.reason or "Saga cancelled.",
                            )
                        )
                        audit_repository.insert(
                            _runtime_session_audit_event(
                                organization_id=organization_id,
                                environment_id=environment_id,
                                actor_id=current_user.id,
                                event_type="runtime.session.ended",
                                session=session,
                                correlation_id=context.correlation_id,
                            )
                        )
                saga = _saga_detail_response(saga_repository, saga_id)
                audit_repository.insert(
                    _saga_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="saga.cancelled",
                        saga=saga,
                        correlation_id=context.correlation_id,
                        payload={"reason": body.reason},
                        decision="deny",
                        severity="warning",
                    )
                )
                return saga
        except SagaNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeSessionStateError, SagaExecutionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    @app.post(
        "/api/v1/marketplace/plugins/import",
        response_model=PluginResponse,
        status_code=201,
        tags=["marketplace"],
    )
    async def import_marketplace_plugin(
        body: PluginImportRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
    ) -> PluginResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.import_plugin(body)
            except MarketplaceManifestError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return plugin_response(repository, row)

    @app.get(
        "/api/v1/marketplace/plugins",
        response_model=list[PluginResponse],
        tags=["marketplace"],
    )
    async def list_marketplace_plugins(
        plugin_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
    ) -> list[PluginResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            return [
                plugin_response(repository, row)
                for row in repository.list_plugins(plugin_type=plugin_type, status=status)
            ]

    @app.get(
        "/api/v1/marketplace/plugins/{plugin_id}",
        response_model=PluginResponse,
        tags=["marketplace"],
    )
    async def get_marketplace_plugin(
        plugin_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
    ) -> PluginResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            row = repository.get_plugin(plugin_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Plugin not found.")
            return plugin_response(repository, row)

    @app.post(
        "/api/v1/marketplace/plugins/{version_id}/check-policy",
        response_model=PluginPolicyResultResponse,
        status_code=201,
        tags=["marketplace"],
    )
    async def check_marketplace_plugin_policy(
        version_id: str,
        body: PluginPolicyCheckRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
    ) -> PluginPolicyResultResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.check_policy(version_id, body)
            except PluginNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return plugin_policy_result_response(row)

    @app.post(
        "/api/v1/marketplace/plugins/{version_id}/submit-review",
        response_model=PluginReviewResponse,
        status_code=201,
        tags=["marketplace"],
    )
    async def submit_marketplace_plugin_review(
        version_id: str,
        body: PluginReviewSubmitRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
    ) -> PluginReviewResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.submit_review(version_id, body)
            except PluginNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return plugin_review_response(row)

    @app.get(
        "/api/v1/marketplace/reviews",
        response_model=list[PluginReviewResponse],
        tags=["marketplace"],
    )
    async def list_marketplace_plugin_reviews(
        status: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
    ) -> list[PluginReviewResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            return [plugin_review_response(row) for row in repository.list_reviews(status=status)]

    @app.post(
        "/api/v1/marketplace/reviews/{review_id}/approve",
        response_model=PluginReviewResponse,
        tags=["marketplace"],
    )
    async def approve_marketplace_plugin_review(
        review_id: str,
        body: PluginReviewDecisionRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
    ) -> PluginReviewResponse:
        _require_marketplace_reviewer(current_user)
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.decide_review(
                    review_id,
                    status="approved",
                    reviewer_id=current_user.id,
                    body=body,
                )
            except PluginReviewNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except PluginReviewStateError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return plugin_review_response(row)

    @app.post(
        "/api/v1/marketplace/reviews/{review_id}/reject",
        response_model=PluginReviewResponse,
        tags=["marketplace"],
    )
    async def reject_marketplace_plugin_review(
        review_id: str,
        body: PluginReviewDecisionRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
    ) -> PluginReviewResponse:
        _require_marketplace_reviewer(current_user)
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.decide_review(
                    review_id,
                    status="rejected",
                    reviewer_id=current_user.id,
                    body=body,
                )
            except PluginReviewNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except PluginReviewStateError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return plugin_review_response(row)

    @app.post(
        "/api/v1/marketplace/signing-keys",
        response_model=PluginSigningKeyResponse,
        status_code=201,
        tags=["marketplace"],
    )
    async def create_marketplace_signing_key(
        body: PluginSigningKeyCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
    ) -> PluginSigningKeyResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            row = repository.create_signing_key(body, created_by=current_user.id)
            response = plugin_signing_key_response(row)
            AuditEventRepository(connection).insert(
                _plugin_signing_key_audit_event(
                    organization_id=organization_id,
                    environment_id=context.environment_id or _default_environment_id_for_org(organization_id),
                    actor_id=current_user.id,
                    event_type="marketplace.signing_key.created",
                    signing_key=response,
                    correlation_id=context.correlation_id,
                )
            )
            return response

    @app.get(
        "/api/v1/marketplace/signing-keys",
        response_model=list[PluginSigningKeyResponse],
        tags=["marketplace"],
    )
    async def list_marketplace_signing_keys(
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
    ) -> list[PluginSigningKeyResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            return [plugin_signing_key_response(row) for row in repository.list_signing_keys()]

    @app.post(
        "/api/v1/marketplace/signing-keys/{key_id}/revoke",
        response_model=PluginSigningKeyResponse,
        tags=["marketplace"],
    )
    async def revoke_marketplace_signing_key(
        key_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
    ) -> PluginSigningKeyResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.revoke_signing_key(key_id)
            except PluginSigningKeyNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            response = plugin_signing_key_response(row)
            AuditEventRepository(connection).insert(
                _plugin_signing_key_audit_event(
                    organization_id=organization_id,
                    environment_id=context.environment_id or _default_environment_id_for_org(organization_id),
                    actor_id=current_user.id,
                    event_type="marketplace.signing_key.revoked",
                    signing_key=response,
                    correlation_id=context.correlation_id,
                )
            )
            return response

    @app.post(
        "/api/v1/marketplace/plugins/{version_id}/assess-quality",
        response_model=PluginQualityAssessmentResponse,
        status_code=201,
        tags=["marketplace"],
    )
    async def assess_marketplace_plugin_quality(
        version_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
    ) -> PluginQualityAssessmentResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.assess_quality(version_id)
            except PluginNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return plugin_quality_assessment_response(row)

    @app.post(
        "/api/v1/marketplace/plugins/{version_id}/recompute-trust",
        response_model=PluginTrustEventResponse,
        status_code=201,
        tags=["marketplace"],
    )
    async def recompute_marketplace_plugin_trust(
        version_id: str,
        body: PluginTrustRecomputeRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
    ) -> PluginTrustEventResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.recompute_trust(version_id, body)
            except PluginNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return plugin_trust_event_response(row)

    @app.post(
        "/api/v1/marketplace/installations",
        response_model=PluginInstallationResponse,
        status_code=201,
        tags=["marketplace"],
    )
    async def create_marketplace_installation(
        body: PluginInstallationCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> PluginInstallationResponse:
        organization_id = _require_organization_id(current_user)
        if body.environment_id != environment_id:
            raise HTTPException(status_code=400, detail="Installation environment must match request context.")
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.create_installation(body, installed_by=current_user.id)
            except PluginInstallationBlockedError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except PluginNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            response = plugin_installation_response(row)
            AuditEventRepository(connection).insert(
                _plugin_installation_audit_event(
                    organization_id=organization_id,
                    actor_id=current_user.id,
                    event_type="marketplace.plugin.installed",
                    installation=response,
                    correlation_id=context.correlation_id,
                )
            )
            return response

    @app.get(
        "/api/v1/marketplace/installations",
        response_model=list[PluginInstallationResponse],
        tags=["marketplace"],
    )
    async def list_marketplace_installations(
        status: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[PluginInstallationResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            return [
                plugin_installation_response(row)
                for row in repository.list_installations(environment_id=environment_id, status=status)
            ]

    @app.post(
        "/api/v1/marketplace/installations/{installation_id}/uninstall",
        response_model=PluginInstallationResponse,
        tags=["marketplace"],
    )
    async def uninstall_marketplace_plugin(
        installation_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> PluginInstallationResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.uninstall(installation_id)
            except PluginInstallationNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except PluginInstallationStateError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            response = plugin_installation_response(row)
            if response.environment_id != environment_id:
                raise HTTPException(status_code=404, detail="Plugin installation not found.")
            AuditEventRepository(connection).insert(
                _plugin_installation_audit_event(
                    organization_id=organization_id,
                    actor_id=current_user.id,
                    event_type="marketplace.plugin.uninstalled",
                    installation=response,
                    correlation_id=context.correlation_id,
                )
            )
            return response

    @app.get(
        "/api/v1/integrations/frameworks",
        response_model=list[FrameworkIntegrationResponse],
        tags=["integrations"],
    )
    async def list_integration_frameworks(
        status: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[FrameworkIntegrationResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            return [
                framework_integration_response(row)
                for row in repository.list_frameworks(status=status)
            ]

    @app.post(
        "/api/v1/integrations/provider-credentials",
        response_model=ProviderCredentialResponse,
        status_code=201,
        tags=["integrations"],
    )
    async def create_integration_provider_credential(
        body: ProviderCredentialCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ProviderCredentialResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            row = repository.create_provider_credential(
                body,
                created_by=current_user.id,
                secret_provider=_secret_provider(),
            )
            return provider_credential_response(row)

    @app.get(
        "/api/v1/integrations/provider-credentials",
        response_model=list[ProviderCredentialResponse],
        tags=["integrations"],
    )
    async def list_integration_provider_credentials(
        provider_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ProviderCredentialResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            return [
                provider_credential_response(row)
                for row in repository.list_provider_credentials(provider_type=provider_type, status=status)
            ]

    @app.post(
        "/api/v1/integrations/provider-credentials/{credential_id}/test",
        response_model=IntegrationHealthCheckResponse,
        status_code=201,
        tags=["integrations"],
    )
    async def test_integration_provider_credential(
        credential_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> IntegrationHealthCheckResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            credential = repository.get_provider_credential(credential_id)
            if credential is None:
                raise HTTPException(status_code=404, detail="Provider credential not found.")
            secret_value = _secret_provider().retrieve(credential["secret_ref"])
            result = run_provider_health_test(credential["provider_type"], secret_value)
            row = repository.create_provider_credential_health_check(credential, result)
            return integration_health_check_response(row)

    @app.post(
        "/api/v1/integrations/health-checks",
        response_model=IntegrationHealthCheckResponse,
        status_code=201,
        tags=["integrations"],
    )
    async def create_integration_health_check(
        body: IntegrationHealthCheckCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> IntegrationHealthCheckResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            row = repository.create_health_check(body)
            return integration_health_check_response(row)

    @app.get(
        "/api/v1/integrations/health-checks",
        response_model=list[IntegrationHealthCheckResponse],
        tags=["integrations"],
    )
    async def list_integration_health_checks(
        target_type: str | None = Query(default=None),
        target_id: str | None = Query(default=None),
        status: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[IntegrationHealthCheckResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            return [
                integration_health_check_response(row)
                for row in repository.list_health_checks(
                    target_type=target_type,
                    target_id=target_id,
                    status=status,
                )
            ]

    @app.get(
        "/api/v1/integrations/health-checks/latest",
        response_model=list[IntegrationHealthCheckResponse],
        tags=["integrations"],
    )
    async def list_latest_integration_health_checks(
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[IntegrationHealthCheckResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            return [integration_health_check_response(row) for row in repository.latest_health_checks()]

    @app.post(
        "/api/v1/integrations/framework-instances",
        response_model=FrameworkInstanceResponse,
        status_code=201,
        tags=["integrations"],
    )
    async def create_integration_framework_instance(
        body: FrameworkInstanceCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> FrameworkInstanceResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            try:
                row = repository.create_instance(body, created_by=current_user.id)
            except FrameworkIntegrationNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except FrameworkInstanceConfigError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            response = framework_instance_response(row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="integration.instance.created",
                    source_component="framework-integrations",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="integration_instance",
                    resource_id=response.id,
                    correlation_id=context.correlation_id,
                    payload_json=response.model_dump(),
                )
            )
            return response

    @app.get(
        "/api/v1/integrations/framework-instances",
        response_model=list[FrameworkInstanceResponse],
        tags=["integrations"],
    )
    async def list_integration_framework_instances(
        status: str | None = Query(default=None),
        integration_id: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[FrameworkInstanceResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            return [
                framework_instance_response(row)
                for row in repository.list_instances(status=status, integration_id=integration_id)
            ]

    @app.patch(
        "/api/v1/integrations/framework-instances/{instance_id}",
        response_model=FrameworkInstanceResponse,
        tags=["integrations"],
    )
    async def patch_integration_framework_instance(
        instance_id: str,
        body: FrameworkInstancePatchRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> FrameworkInstanceResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            try:
                row = repository.patch_instance(instance_id, body)
            except FrameworkInstanceNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except FrameworkInstanceConfigError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            response = framework_instance_response(row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="integration.instance.updated",
                    source_component="framework-integrations",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="integration_instance",
                    resource_id=response.id,
                    correlation_id=context.correlation_id,
                    payload_json=response.model_dump(),
                )
            )
            return response

    @app.post(
        "/api/v1/integrations/framework-instances/{instance_id}/link-agent",
        response_model=FrameworkAgentResponse,
        status_code=201,
        tags=["integrations"],
    )
    async def link_integration_framework_agent(
        instance_id: str,
        body: FrameworkAgentLinkRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> FrameworkAgentResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            try:
                row = repository.link_agent(instance_id, body)
            except FrameworkInstanceNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except FrameworkAgentValidationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            response = framework_agent_response(row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="integration.framework_agent.linked",
                    source_component="framework-integrations",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="framework_agent",
                    resource_id=response.id,
                    agent_id=response.agent_id,
                    correlation_id=context.correlation_id,
                    payload_json=response.model_dump(),
                )
            )
            return response

    @app.get(
        "/api/v1/integrations/framework-agents",
        response_model=list[FrameworkAgentResponse],
        tags=["integrations"],
    )
    async def list_integration_framework_agents(
        integration_instance_id: str | None = Query(default=None),
        agent_id: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[FrameworkAgentResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            return [
                framework_agent_response(row)
                for row in repository.list_framework_agents(
                    integration_instance_id=integration_instance_id,
                    agent_id=agent_id,
                )
            ]

    @app.delete(
        "/api/v1/integrations/framework-agents/{link_id}",
        status_code=204,
        tags=["integrations"],
    )
    async def unlink_integration_framework_agent(
        link_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> None:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            try:
                row = repository.unlink_framework_agent(link_id)
            except FrameworkAgentNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            response = framework_agent_response(row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="integration.framework_agent.unlinked",
                    source_component="framework-integrations",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="framework_agent",
                    resource_id=response.id,
                    agent_id=response.agent_id,
                    correlation_id=context.correlation_id,
                    payload_json=response.model_dump(),
                )
            )

    @app.post(
        "/api/v1/observability/slo",
        response_model=SloObjectiveResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_slo(
        body: SloObjectiveCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> SloObjectiveResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            row = repository.create_slo(body, created_by=current_user.id)
            return slo_objective_response(repository, row)

    @app.get(
        "/api/v1/observability/slo",
        response_model=list[SloObjectiveResponse],
        tags=["observability"],
    )
    async def list_observability_slos(
        target_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[SloObjectiveResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            return [
                slo_objective_response(repository, row)
                for row in repository.list_slos(target_type=target_type, status=status)
            ]

    @app.post(
        "/api/v1/observability/slo/{slo_id}/measurements",
        response_model=SloMeasurementResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_slo_measurement(
        slo_id: str,
        body: SloMeasurementCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> SloMeasurementResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            try:
                row = repository.create_slo_measurement(slo_id, body)
            except SloObjectiveNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return slo_measurement_response(row)

    @app.post(
        "/api/v1/observability/chaos/experiments",
        response_model=ChaosExperimentResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_chaos_experiment(
        body: ChaosExperimentCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> ChaosExperimentResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            try:
                row = repository.create_chaos_experiment(
                    body,
                    created_by=current_user.id,
                    allow_production_targets=resolved_settings.enable_production_chaos,
                )
            except ChaosExperimentValidationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return chaos_experiment_response(row)

    @app.get(
        "/api/v1/observability/chaos/experiments",
        response_model=list[ChaosExperimentResponse],
        tags=["observability"],
    )
    async def list_observability_chaos_experiments(
        status: str | None = Query(default=None),
        target_type: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ChaosExperimentResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            return [
                chaos_experiment_response(row)
                for row in repository.list_chaos_experiments(status=status, target_type=target_type)
            ]

    @app.post(
        "/api/v1/observability/chaos/experiments/{experiment_id}/run",
        response_model=ChaosRunResponse,
        status_code=201,
        tags=["observability"],
    )
    async def run_observability_chaos_experiment(
        experiment_id: str,
        body: ChaosRunCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> ChaosRunResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            try:
                row = repository.create_chaos_run(experiment_id, body)
            except ChaosExperimentNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            response = chaos_run_response(row)
            experiment = repository.get_chaos_experiment(experiment_id)
            event = AuditEventEnvelope(
                organization_id=organization_id,
                environment_id=environment_id,
                event_type=f"chaos.run.{response.status}",
                source_component="chaos-operations",
                actor_type="user",
                actor_id=current_user.id,
                resource_type="chaos_run",
                resource_id=response.id,
                severity="warning" if response.result.get("guardrail_breached") else "info",
                correlation_id=context.correlation_id,
                payload_json=response.model_dump(),
            )
            AuditEventRepository(connection).insert(event)
            if experiment is not None and response.result.get("guardrail_breached"):
                for slo in repository.list_slos(target_type=experiment["target_type"]):
                    if slo["target_id"] == experiment["target_id"]:
                        repository.create_slo_measurement(
                            slo["id"],
                            SloMeasurementCreateRequest(
                                value=0.0,
                                good_events=0,
                                total_events=1,
                                metadata={"source": "chaos_run", "chaos_run_id": response.id},
                            ),
                        )
                repository.create_incident(
                    IncidentCreateRequest(
                        severity="critical",
                        title=f"Chaos guardrail tripped: {experiment['name']}",
                        summary="A chaos experiment stopped because one or more guardrails were breached.",
                        correlation_id=context.correlation_id,
                        source_event_id=event.id,
                    )
                )
            return response

    @app.post(
        "/api/v1/observability/chaos/runs/{run_id}/stop",
        response_model=ChaosRunResponse,
        tags=["observability"],
    )
    async def stop_observability_chaos_run(
        run_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> ChaosRunResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            try:
                row = repository.stop_chaos_run(run_id)
            except ChaosRunNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            response = chaos_run_response(row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="chaos.run.stopped",
                    source_component="chaos-operations",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="chaos_run",
                    resource_id=response.id,
                    severity="warning",
                    correlation_id=context.correlation_id,
                    payload_json=response.model_dump(),
                )
            )
            return response

    @app.post(
        "/api/v1/observability/rollouts",
        response_model=RolloutResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_rollout(
        body: RolloutCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> RolloutResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            row = repository.create_rollout(body, created_by=current_user.id)
            return rollout_response(repository, row)

    @app.get(
        "/api/v1/observability/rollouts",
        response_model=list[RolloutResponse],
        tags=["observability"],
    )
    async def list_observability_rollouts(
        status: str | None = Query(default=None),
        target_type: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[RolloutResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            return [
                rollout_response(repository, row)
                for row in repository.list_rollouts(status=status, target_type=target_type)
            ]

    @app.post(
        "/api/v1/observability/rollouts/{rollout_id}/advance",
        response_model=RolloutResponse,
        tags=["observability"],
    )
    async def advance_observability_rollout(
        rollout_id: str,
        body: RolloutAdvanceRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> RolloutResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            try:
                row = repository.advance_rollout(rollout_id, body)
            except RolloutNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            response = rollout_response(repository, row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type=f"rollout.{response.status}",
                    source_component="rollout-operations",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="rollout",
                    resource_id=response.id,
                    severity="warning" if response.status == "blocked" else "info",
                    correlation_id=context.correlation_id,
                    payload_json=response.model_dump(),
                )
            )
            return response

    @app.post(
        "/api/v1/observability/rollouts/{rollout_id}/rollback",
        response_model=RolloutResponse,
        tags=["observability"],
    )
    async def rollback_observability_rollout(
        rollout_id: str,
        body: RolloutRollbackRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> RolloutResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            try:
                row = repository.rollback_rollout(rollout_id, body)
            except RolloutNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            response = rollout_response(repository, row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="rollout.rolled_back",
                    source_component="rollout-operations",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="rollout",
                    resource_id=response.id,
                    severity="warning",
                    correlation_id=context.correlation_id,
                    payload_json=response.model_dump(),
                )
            )
            return response

    @app.post(
        "/api/v1/observability/cost-budgets",
        response_model=CostBudgetResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_cost_budget(
        body: CostBudgetCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> CostBudgetResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            row = repository.create_cost_budget(body, created_by=current_user.id)
            return cost_budget_response(row)

    @app.get(
        "/api/v1/observability/cost-budgets",
        response_model=list[CostBudgetResponse],
        tags=["observability"],
    )
    async def list_observability_cost_budgets(
        target_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[CostBudgetResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            return [
                cost_budget_response(row)
                for row in repository.list_cost_budgets(target_type=target_type, status=status)
            ]

    @app.post(
        "/api/v1/observability/cost-events",
        response_model=CostEventResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_cost_event(
        body: CostEventCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> CostEventResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            row = repository.create_cost_event(body)
            return cost_event_response(row)

    @app.get(
        "/api/v1/observability/costs",
        response_model=CostDashboardResponse,
        tags=["observability"],
    )
    async def get_observability_costs(
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> CostDashboardResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            return cost_dashboard_response(repository)

    @app.post(
        "/api/v1/observability/incidents",
        response_model=IncidentResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_incident(
        body: IncidentCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> IncidentResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            row = repository.create_incident(body)
            return incident_response(repository, row)

    @app.post(
        "/api/v1/observability/incidents/from-event",
        response_model=IncidentResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_incident_from_event(
        body: IncidentFromEventRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> IncidentResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            try:
                row = repository.create_incident_from_event(body)
            except IncidentNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            return incident_response(repository, row)

    @app.get(
        "/api/v1/observability/incidents",
        response_model=list[IncidentResponse],
        tags=["observability"],
    )
    async def list_observability_incidents(
        status: str | None = Query(default=None),
        severity: str | None = Query(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[IncidentResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            return [
                incident_response(repository, row)
                for row in repository.list_incidents(status=status, severity=severity)
            ]

    @app.post(
        "/api/v1/observability/incidents/{incident_id}/ack",
        response_model=IncidentResponse,
        tags=["observability"],
    )
    async def acknowledge_observability_incident(
        incident_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> IncidentResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            try:
                row = repository.acknowledge_incident(incident_id, actor_id=current_user.id)
            except IncidentNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except IncidentStateError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            return incident_response(repository, row)

    @app.post(
        "/api/v1/observability/incidents/{incident_id}/resolve",
        response_model=IncidentResponse,
        tags=["observability"],
    )
    async def resolve_observability_incident(
        incident_id: str,
        body: IncidentResolveRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> IncidentResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            try:
                row = repository.resolve_incident(incident_id, body)
            except IncidentNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except IncidentStateError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            return incident_response(repository, row)

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
