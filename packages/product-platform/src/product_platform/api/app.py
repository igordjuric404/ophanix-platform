"""FastAPI application factory for the Ophanix product control plane."""

from __future__ import annotations

import base64
import hashlib
import hmac
import inspect
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from product_platform import __version__
from product_platform.api.api_keys import (
    ApiKeyAuthenticationResult,
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyRevokeRequest,
    ApiKeyResponse,
    ApiKeyRotateRequest,
    ApiKeyRotationResponse,
    ApiKeyStore,
    DatabaseApiKeyStore,
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
from product_platform.api.rbac import (
    Permission,
    has_permission,
    require_permission,
    validate_delegated_api_key_scopes,
)
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
    AgentIdentityProofRequest,
    AgentIdentityRotationRequest,
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
    AgentLifecycleCredentialCascadeResult,
    AgentCredentialIssuer,
    AgentCredentialRepository,
    CredentialNotFoundError,
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
from product_platform.agents.lifecycle import AgentLifecycleTransitionError, is_agent_operational
from product_platform.agents.simulation import simulate_registration_action
from product_platform.db.connection import Database
from product_platform.db.migrator import is_supported_database_url
from product_platform.db.seed import seed_demo_data
from product_platform.db.time import utc_now_iso
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
    AuditExportValidationError,
    ComplianceRepository,
    ComplianceReportNotFoundError,
    ComplianceReportValidationError,
    ComplianceResourceNotFoundError,
    ComplianceViolationNotFoundError,
    ComplianceViolationStateError,
    DuplicateComplianceResourceError,
    audit_export_content,
    audit_export_linked_artifacts,
    audit_export_runtime_links,
    audit_export_response,
    collect_audit_export_events,
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
    record_demo_reset_failure,
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
    ProviderCredentialSelectionError,
    ProviderCredentialSecretError,
    framework_agent_response,
    framework_instance_response,
    framework_integration_response,
    integration_health_check_response,
    provider_credential_response,
)
from product_platform.integrations.health import run_provider_health_test
from product_platform.integrations.secrets import (
    SecretProvider,
    build_secret_provider,
    is_supported_secret_manager_ref,
)
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
    MeshAgentNotOperationalError,
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
from product_platform.mcp.discovery import normalize_tool_definition, select_mcp_tool_discovery_adapter
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
from product_platform.observability.trace_context import build_request_trace_context
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
    PluginArtifactEvidenceResponse,
    PluginArtifactEvidenceSubmitRequest,
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
    plugin_artifact_evidence_response,
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
    ObservabilityEvalResultCreateRequest,
    ObservabilityEvalResultResponse,
    ObservabilitySpanCreateRequest,
    ObservabilitySpanResponse,
    ObservabilityTraceAnnotationCreateRequest,
    ObservabilityTraceAnnotationResponse,
    ObservabilityTraceCreateRequest,
    ObservabilityTraceDetailResponse,
    ObservabilityTraceFeedbackCreateRequest,
    ObservabilityTraceFeedbackResponse,
    ObservabilityTraceResponse,
    RolloutAdvanceRequest,
    RolloutCreateRequest,
    RolloutRollbackRequest,
    RolloutResponse,
    SloMeasurementCreateRequest,
    SloMeasurementResponse,
    SloObjectiveCreateRequest,
    SloObjectiveResponse,
    TelemetryDerivationRequest,
    TelemetryDerivationResponse,
)
from product_platform.observability.repository import (
    ChaosExperimentValidationError,
    ChaosExperimentNotFoundError,
    ChaosRunNotFoundError,
    IncidentNotFoundError,
    IncidentStateError,
    ObservabilityTraceNotFoundError,
    ObservabilityRepository,
    RolloutNotFoundError,
    SloObjectiveNotFoundError,
    chaos_experiment_response,
    chaos_run_response,
    cost_budget_response,
    cost_dashboard_response,
    cost_event_response,
    incident_response,
    observability_eval_result_response,
    observability_span_response,
    observability_trace_annotation_response,
    observability_trace_feedback_response,
    observability_trace_response,
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
    PolicyEvaluationSummaryResponse,
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
    RuntimeRunResponse,
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
    runtime_run_response,
    runtime_run_step_response,
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
    SagaExecutionError,
    SagaExecutionService,
    WorkerBackedSagaActionRunner,
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
    SAGA_EXECUTABLE_STATUSES,
    SAGA_RECOVERABLE_STATUSES,
    SAGA_TERMINAL_STATUSES,
    SagaNotFoundError,
    SagaRepository,
    SagaStateTransitionError,
    SagaStepValidationError,
    saga_event_response,
    saga_response,
    saga_step_response,
)
from product_platform.trust.models import (
    AgentTrustCardResponse,
    TrustHandshakeChallengeRequest,
    TrustHandshakeChallengeResponse,
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
    TrustThresholdResolveRequest,
    TrustThresholdResponse,
)
from product_platform.trust.cards import (
    TrustCardAgentNotOperationalError,
    TrustCardIssuer,
    TrustCardNotFoundError,
    TrustCardRepository,
    trust_card_response,
)
from product_platform.trust.handshakes import TRUST_TIER_RANK, TrustHandshakeService, TrustThresholdResolver
from product_platform.trust.pipeline import TrustScoreRecalculator
from product_platform.trust.repository import (
    DuplicateTrustThresholdError,
    TrustAgentNotFoundError,
    TrustAgentNotOperationalError,
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
from product_platform.tool_gateway.models import (
    AgentToolPermissionActionRequest,
    AgentToolPermissionGrantRequest,
    AgentToolPermissionPatchRequest,
    AgentToolPermissionResponse,
    GatewayCapabilitiesResponse,
    GatewayToolDefinitionResponse,
    GatewayToolListPageResponse,
    ToolDefinitionCreateRequest,
    ToolDefinitionPatchRequest,
    ToolDefinitionResponse,
    ToolDefinitionVersionResponse,
    ToolLifecycleActionRequest,
    ToolUpstreamHealthResponse,
    ToolUpstreamTargetCreateRequest,
    ToolUpstreamTargetPatchRequest,
    ToolUpstreamTargetResponse,
    ToolResponsePolicyPatchRequest,
    ToolResponsePolicyResponse,
    validate_upstream_host_allowed,
)
from product_platform.tool_gateway.repository import (
    AgentToolPermissionNotFoundError,
    AgentToolPermissionValidationError,
    DuplicateAgentToolPermissionError,
    DuplicateToolNameError,
    DuplicateToolUpstreamTargetError,
    ToolDefinitionNotFoundError,
    ToolLifecycleError,
    ToolRegistryRepository,
    ToolUpstreamTargetNotFoundError,
    ToolUpstreamTargetValidationError,
    agent_tool_permission_response,
    gateway_tool_definition_response,
    tool_definition_response,
    tool_definition_version_response,
    tool_response_policy_response,
    tool_upstream_health_response,
    tool_upstream_target_response,
)
from product_platform.tool_gateway.auth import (
    GatewayAuthenticationError,
    GatewayPrincipal,
    GatewayTokenVerifier,
    parse_bearer_authorization,
)
from product_platform.tool_gateway.decision import ToolPolicyDecisionService
from product_platform.tool_gateway.delegation import (
    AuthorizationStatusResponse,
    DelegatedAuthorizationResponse,
    OAuthAuthorizationSessionCompleteRequest,
    OAuthAuthorizationSessionStartRequest,
    OAuthDelegatedAuthorizationRefreshRequest,
    OAuthDelegatedAuthorizationRevokeRequest,
    OAuthProviderAppCreateRequest,
    OAuthProviderAppResponse,
    ToolDelegationRepository,
    authorization_session_response,
    delegated_authorization_response,
    oauth_provider_app_response,
)
from product_platform.tool_gateway.health import ToolUpstreamHealthChecker
from product_platform.tool_gateway.invocation import (
    AsyncHttpToolInvocationExecutor,
    ToolExecutionError,
    ToolExecutionResult,
    ToolInvocationDecisionSummary,
    ToolInvocationRequest,
    ToolInvocationResponse,
    invocation_request_hash,
    safe_agent_error_message,
    validate_idempotency_key,
)
from product_platform.tool_gateway.operational_state import (
    DatabaseToolGatewayCircuitBreaker,
    tool_gateway_rate_limit_result,
)
from product_platform.tool_gateway.pagination import (
    GatewayToolCursor,
    decode_gateway_tool_cursor,
    encode_gateway_tool_cursor,
)
from product_platform.tool_gateway.schemas import ToolSchemaValidationError, validate_payload
from product_platform.tool_gateway.response import process_tool_execution_response
from product_platform.tool_gateway.runtime_audit import (
    ToolInvocationIdempotencyConflictError,
    ToolInvocationIdempotencyInProgressError,
    ToolInvocationIdempotencyRepository,
    ToolInvocationIdempotencyStaleError,
    ToolRuntimeActionCreate,
    ToolRuntimeActionDetailResponse,
    ToolRuntimeActionEventCreate,
    ToolRuntimeActionQuery,
    ToolRuntimeActionRepository,
    ToolRuntimeActionResponse,
    ToolRuntimeActionUpdate,
    idempotency_response_body,
    tool_runtime_action_detail_response,
    tool_runtime_action_response,
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
from product_platform.worker.store import (
    JobIdempotencyConflictError,
    JobStateConflictError,
    JobStateRepository,
    JobStatus,
)
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
from product_platform.workflows.worker import WORKFLOW_JOB_TYPE

MAX_TRACE_ID_LENGTH = 128
TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:/@+-]+$")
LOGGER = logging.getLogger(__name__)
SAFE_PRODUCTION_HTTP_DETAIL_PREFIXES = (
    "Disabling Tool Gateway response policy is blocked",
)


def _request_context_from_request(request: Request) -> RequestContext:
    existing = getattr(request.state, "request_context", None)
    if isinstance(existing, RequestContext):
        return existing
    server_request_id = str(uuid4())
    fallback_id = _trusted_trace_id(request.headers.get("X-Request-ID")) or server_request_id
    trace_context = build_request_trace_context(
        traceparent=request.headers.get("traceparent"),
        tracestate=request.headers.get("tracestate"),
        baggage=request.headers.get("baggage"),
    )
    return RequestContext(
        request_id=fallback_id,
        correlation_id=_trusted_trace_id(request.headers.get("X-Correlation-ID")) or fallback_id,
        server_request_id=server_request_id,
        trace_id=trace_context.trace_id,
        span_id=trace_context.span_id,
        parent_span_id=trace_context.parent_span_id,
        traceparent=trace_context.traceparent,
        tracestate=trace_context.tracestate,
        baggage=trace_context.baggage,
        organization_id=request.headers.get("X-Organization-ID"),
        environment_id=request.headers.get("X-Environment-ID"),
        user_id=request.headers.get("X-User-ID"),
        actor_type=request.headers.get("X-Actor-Type"),
    )


def _trusted_trace_id(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or len(stripped) > MAX_TRACE_ID_LENGTH:
        return None
    if not TRACE_ID_PATTERN.fullmatch(stripped):
        return None
    return stripped


def _trace_context_fields(context: RequestContext) -> dict[str, str | None]:
    return {
        "trace_id": context.trace_id,
        "span_id": context.span_id,
        "parent_span_id": context.parent_span_id,
        "traceparent": context.traceparent,
        "tracestate": context.tracestate,
        "baggage": context.baggage,
    }


def _tool_gateway_idempotency_key(request: Request, body: ToolInvocationRequest) -> str | None:
    header_value = request.headers.get("Idempotency-Key")
    body_value = body.idempotency_key
    normalized_header: str | None = None
    if header_value is not None:
        try:
            normalized_header = validate_idempotency_key(header_value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if normalized_header is not None and body_value is not None and normalized_header != body_value:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header and body idempotency_key must match.",
        )
    return normalized_header or body_value


def _tool_invocation_decision_summary(decision: Any) -> ToolInvocationDecisionSummary:
    return ToolInvocationDecisionSummary(
        decision=str(decision.decision),
        reason_code=decision.reason_code,
    )


def _tool_execution_error_body(error: dict[str, Any] | None) -> dict[str, str]:
    error = error if isinstance(error, dict) else {}
    code = str(error.get("code") or "upstream_error")
    return {
        "code": code,
        "message": safe_agent_error_message(error.get("message") or "Tool execution failed."),
    }


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    context = _request_context_from_request(request)
    response_headers = {
        "X-Request-ID": context.request_id,
        "X-Correlation-ID": context.correlation_id,
    }
    if headers:
        response_headers.update(headers)
    return JSONResponse(
        status_code=status_code,
        content=ApiError(
            code=code,
            message=message,
            request_id=context.request_id,
            details=details or {},
        ).model_dump(),
        headers=response_headers,
    )


def _validation_error_details(exc: RequestValidationError, environment: str) -> dict[str, Any]:
    if _is_local_environment(environment):
        return {"errors": jsonable_encoder(exc.errors())}
    return {
        "errors": [
            {
                "loc": jsonable_encoder(error.get("loc", [])),
                "msg": "Invalid request value.",
                "type": str(error.get("type") or "value_error"),
            }
            for error in exc.errors()
        ]
    }


def _safe_http_error_message(exc: StarletteHTTPException, environment: str) -> str:
    detail = exc.detail if isinstance(exc.detail, str) else ""
    if _is_local_environment(environment):
        return detail or "HTTP error."
    if detail and any(detail.startswith(prefix) for prefix in SAFE_PRODUCTION_HTTP_DETAIL_PREFIXES):
        return detail
    return {
        400: "Invalid request.",
        401: "Authentication is required.",
        403: "Access is denied.",
        404: "Resource not found.",
        409: "Request conflicts with current resource state.",
        413: "Request body too large.",
        422: "Request validation failed.",
        429: "Rate limit exceeded.",
    }.get(exc.status_code, "HTTP error.")


def _public_dependency_statuses(
    dependencies: list[DependencyStatus],
    *,
    expose_messages: bool,
) -> list[DependencyStatus]:
    if expose_messages:
        return dependencies
    return [
        DependencyStatus(
            name=dependency.name,
            status=dependency.status,
            required=dependency.required,
            message=None,
        )
        for dependency in dependencies
    ]


def _is_local_environment(environment: str) -> bool:
    return environment.strip().lower() in {"development", "dev", "local", "local-demo", "test"}


def _validate_production_settings(settings: Settings) -> None:
    if not is_supported_database_url(settings.database_url):
        raise ValueError("OPHANIX_DATABASE_URL must be a postgresql:// URL.")
    if _is_local_environment(settings.environment):
        return
    is_production = settings.environment.strip().lower() == "production"
    if settings.session_secret == "dev-secret-change-me":
        raise ValueError("OPHANIX_SESSION_SECRET must be set to a non-default value in production.")
    enable_dev_login = (
        settings.enable_dev_login
        if settings.enable_dev_login is not None
        else _is_local_environment(settings.environment)
    )
    if enable_dev_login:
        raise ValueError("Development login must be disabled outside local/test environments.")
    if is_production:
        missing_idp_settings: list[str] = []
        if not settings.idp_issuer_url:
            missing_idp_settings.append("OPHANIX_IDP_ISSUER_URL")
        if not settings.idp_audience:
            missing_idp_settings.append("OPHANIX_IDP_AUDIENCE")
        if not (settings.idp_jwks_url or settings.idp_jwks_json):
            missing_idp_settings.append("OPHANIX_IDP_JWKS_URL")
        if missing_idp_settings:
            raise ValueError(
                ", ".join(missing_idp_settings)
                + " must be configured for production enterprise IdP authentication."
            )
        if not is_supported_secret_manager_ref(settings.secret_manager_ref):
            raise ValueError(
                "OPHANIX_SECRET_MANAGER_REF must be set to 'env' or 'env:<ENV_VAR_PREFIX>' in production."
            )
        if _bool_env("OPHANIX_GATEWAY_TOKEN_HASH_ACCEPT_LEGACY", False):
            raise ValueError("Legacy gateway token hash acceptance is not allowed in production.")
        if _bool_env("OPHANIX_ALLOW_UNRESOLVED_UPSTREAM_HOSTS", False):
            raise ValueError("Unresolved upstream hosts are not allowed in production.")
    if not settings.tool_gateway_upstream_host_allowlist:
        raise ValueError(
            "OPHANIX_TOOL_GATEWAY_UPSTREAM_HOST_ALLOWLIST must be configured in non-local environments."
        )
    if not settings.gateway_token_hash_pepper:
        raise ValueError("OPHANIX_GATEWAY_TOKEN_HASH_PEPPER must be set in production.")
    if not settings.api_key_hash_pepper:
        raise ValueError("OPHANIX_API_KEY_HASH_PEPPER must be set in non-local environments.")
    if settings.api_key_hash_pepper == settings.session_secret:
        raise ValueError("OPHANIX_API_KEY_HASH_PEPPER must be distinct from OPHANIX_SESSION_SECRET.")
    positive_gateway_limits = {
        "OPHANIX_DATABASE_MAX_POOL_SIZE": settings.database_max_pool_size,
        "OPHANIX_API_MAX_BODY_BYTES": settings.api_max_body_bytes,
        "OPHANIX_ARTIFACT_MAX_BYTES": settings.artifact_max_bytes,
        "OPHANIX_TOOL_GATEWAY_MAX_BODY_BYTES": settings.tool_gateway_max_body_bytes,
        "OPHANIX_TOOL_GATEWAY_RATE_LIMIT_WINDOW_SECONDS": (
            settings.tool_gateway_rate_limit_window_seconds
        ),
        "OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_REQUESTS": settings.tool_gateway_rate_limit_max_requests,
        "OPHANIX_TOOL_GATEWAY_RATE_LIMIT_MAX_KEYS": settings.tool_gateway_rate_limit_max_keys,
        "OPHANIX_TOOL_GATEWAY_MAX_UPSTREAM_RESPONSE_BYTES": (
            settings.tool_gateway_max_upstream_response_bytes
        ),
        "OPHANIX_TOOL_GATEWAY_CIRCUIT_BREAKER_FAILURE_THRESHOLD": (
            settings.tool_gateway_circuit_breaker_failure_threshold
        ),
        "OPHANIX_TOOL_GATEWAY_CIRCUIT_BREAKER_COOLDOWN_SECONDS": (
            settings.tool_gateway_circuit_breaker_cooldown_seconds
        ),
        "OPHANIX_TOOL_GATEWAY_IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS": (
            settings.tool_gateway_idempotency_in_progress_ttl_seconds
        ),
        "OPHANIX_TOOL_GATEWAY_IDEMPOTENCY_REPLAY_RETENTION_SECONDS": (
            settings.tool_gateway_idempotency_replay_retention_seconds
        ),
    }
    unsafe_limits = [name for name, value in positive_gateway_limits.items() if int(value) <= 0]
    if unsafe_limits:
        raise ValueError(
            "Tool Gateway production safety limits must be positive: "
            + ", ".join(sorted(unsafe_limits))
        )


def _is_tool_gateway_runtime_path(path: str) -> bool:
    return (
        path in {"/api/v1/gateway/tools", "/api/v1/gateway/capabilities"}
        or path.startswith("/api/v1/gateway/authorizations/")
    ) or (
        len(path.split("/")) == 6
        and path.startswith("/api/v1/tools/")
        and path.endswith("/invoke")
    )


def _is_api_body_limited_path(path: str) -> bool:
    return path.startswith("/api/v1/")


def _gateway_rate_limit_key(request: Request, *, secret: str) -> str:
    authorization = request.headers.get("Authorization", "")
    client_host = request.client.host if request.client else "unknown"
    if authorization:
        try:
            token = parse_bearer_authorization(authorization)
        except GatewayAuthenticationError:
            return f"client:{client_host}:invalid_authorization"
        digest = hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"authorization_hmac:{digest}"
    return f"client:{client_host}"


def _tool_gateway_rate_limit_result(
    app: FastAPI,
    request: Request,
    database_factory: Any | None = None,
) -> tuple[bool, int]:
    settings = app.state.settings
    max_requests = int(settings.tool_gateway_rate_limit_max_requests)
    window_seconds = int(settings.tool_gateway_rate_limit_window_seconds)
    if max_requests <= 0 or window_seconds <= 0:
        return False, 0
    key = _gateway_rate_limit_key(
        request,
        secret=settings.gateway_token_hash_pepper or settings.session_secret,
    )
    client_host = request.client.host if request.client else "unknown"
    overflow_key = f"client:{client_host}:overflow"
    max_keys = int(getattr(settings, "tool_gateway_rate_limit_max_keys", 10_000))
    database = (
        database_factory()
        if callable(database_factory)
        else getattr(app.state, "database", None)
    )
    if not isinstance(database, Database):
        raise RuntimeError("Database is required for Tool Gateway rate limiting.")
    with database.transaction() as connection:
        result = tool_gateway_rate_limit_result(
            connection,
            key=key,
            overflow_key=overflow_key,
            max_requests=max_requests,
            window_seconds=window_seconds,
            max_keys=max_keys,
        )
    return result.limited, result.retry_after_seconds


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _validate_upstream_target_host_allowed(base_url: str, settings: Settings) -> None:
    try:
        validate_upstream_host_allowed(
            base_url,
            allowed_hosts=settings.tool_gateway_upstream_host_allowlist,
            field="base_url",
        )
    except ValueError as exc:
        raise ToolUpstreamTargetValidationError(str(exc)) from exc


class ToolGatewayBodyLimitMiddleware:
    """ASGI receive wrapper that enforces body caps without private Request mutation."""

    def __init__(
        self,
        app: Any,
        *,
        max_body_bytes: int,
        path_predicate: Any = _is_tool_gateway_runtime_path,
        message: str = "Tool Gateway request body exceeds the configured size limit.",
    ) -> None:
        self.app = app
        self.max_body_bytes = int(max_body_bytes)
        self.path_predicate = path_predicate
        self.message = message

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if (
            scope.get("type") != "http"
            or self.max_body_bytes <= 0
            or str(scope.get("method") or "").upper() not in {"POST", "PUT", "PATCH"}
            or not self.path_predicate(str(scope.get("path") or ""))
        ):
            await self.app(scope, receive, send)
            return
        headers = _scope_headers(scope)
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                body_bytes = int(content_length)
            except ValueError:
                await _send_asgi_error_response(
                    scope,
                    send,
                    status_code=400,
                    code="INVALID_CONTENT_LENGTH",
                    message="Content-Length must be an integer.",
                )
                return
            if body_bytes > self.max_body_bytes:
                await _send_asgi_error_response(
                    scope,
                    send,
                    status_code=413,
                    code="REQUEST_BODY_TOO_LARGE",
                    message=self.message,
                )
                return
        received_bytes = 0
        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message.get("type") != "http.request":
                await self.app(scope, receive, send)
                return
            body = message.get("body", b"")
            if isinstance(body, bytes):
                received_bytes += len(body)
                if received_bytes > self.max_body_bytes:
                    await _send_asgi_error_response(
                        scope,
                        send,
                        status_code=413,
                        code="REQUEST_BODY_TOO_LARGE",
                        message=self.message,
                    )
                    return
                chunks.append(body)
            if not bool(message.get("more_body", False)):
                break
        replayed = False

        async def replay_receive() -> dict[str, Any]:
            nonlocal replayed
            if replayed:
                return {"type": "http.request", "body": b"", "more_body": False}
            replayed = True
            return {
                "type": "http.request",
                "body": b"".join(chunks),
                "more_body": False,
            }

        await self.app(scope, replay_receive, send)


async def _send_asgi_error_response(
    scope: dict[str, Any],
    send: Any,
    *,
    status_code: int,
    code: str,
    message: str,
) -> None:
    headers = _scope_headers(scope)
    request_id = _trusted_trace_id(headers.get("x-request-id")) or str(uuid4())
    correlation_id = _trusted_trace_id(headers.get("x-correlation-id")) or request_id
    trace_context = build_request_trace_context(
        traceparent=headers.get("traceparent"),
        tracestate=headers.get("tracestate"),
        baggage=headers.get("baggage"),
    )
    body = json.dumps(
        {
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": {},
        },
        separators=(",", ":"),
    ).encode("utf-8")
    response_headers = [
        (b"content-type", b"application/json"),
        (b"x-request-id", request_id.encode("utf-8")),
        (b"x-correlation-id", correlation_id.encode("utf-8")),
        (b"traceparent", trace_context.traceparent.encode("utf-8")),
    ]
    if trace_context.tracestate is not None:
        response_headers.append((b"tracestate", trace_context.tracestate.encode("utf-8")))
    if trace_context.baggage is not None:
        response_headers.append((b"baggage", trace_context.baggage.encode("utf-8")))
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": response_headers,
        }
    )
    await send({"type": "http.response.body", "body": body})


def _scope_headers(scope: dict[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for raw_key, raw_value in scope.get("headers", []) or []:
        try:
            key = raw_key.decode("latin-1").lower()
            value = raw_value.decode("latin-1")
        except Exception:
            continue
        output[key] = value
    return output


class _PreloadedToolUpstreamTargetRepository:
    """Repository adapter that lets invocation avoid DB work during upstream I/O."""

    def __init__(self, target: Any | None) -> None:
        self._target = target

    def get_upstream_target_for_tool(self, _tool_id: str) -> Any | None:
        return self._target


def create_app(
    settings: Settings | None = None,
    dependency_registry: DependencyRegistry | None = None,
    tenant_store: TenantStore | None = None,
    api_key_store: ApiKeyStore | None = None,
    database: Database | None = None,
) -> FastAPI:
    """Create and configure the FastAPI product API."""

    resolved_settings = settings or load_settings()
    _validate_production_settings(resolved_settings)
    if (
        database is None
        and not _is_local_environment(resolved_settings.environment)
        and not is_supported_database_url(resolved_settings.database_url)
    ):
        raise ValueError("A configured database is required outside local/test environments.")
    registry = dependency_registry or create_default_dependency_registry(resolved_settings)
    auth_service = AuthService(resolved_settings)
    tenants = tenant_store or TenantStore()
    api_key_hash_pepper = resolved_settings.api_key_hash_pepper or resolved_settings.session_secret
    api_keys = api_key_store or ApiKeyStore(api_key_hash_pepper)
    use_persistent_api_keys = api_key_store is None
    started_at = time.monotonic()

    enable_api_docs = (
        resolved_settings.enable_api_docs
        if resolved_settings.enable_api_docs is not None
        else _is_local_environment(resolved_settings.environment)
    )
    enable_dev_login = (
        resolved_settings.enable_dev_login
        if resolved_settings.enable_dev_login is not None
        else _is_local_environment(resolved_settings.environment)
    )

    app = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        description="Control plane API for the Ophanix product platform.",
        docs_url="/docs" if enable_api_docs else None,
        openapi_url="/openapi.json" if enable_api_docs else None,
    )
    app.state.settings = resolved_settings
    app.state.dependency_registry = registry
    app.state.auth_service = auth_service
    app.state.api_key_store = api_keys
    app.state.tenant_store = tenants
    app.state.database = database
    app.state.denied_audit_events = []
    app.state.started_at = started_at
    app.state.tool_gateway_http_client = httpx.AsyncClient(follow_redirects=False, trust_env=False)
    app.state.tool_gateway_circuit_breaker = None

    async def _close_tool_gateway_http_client() -> None:
        client = app.state.tool_gateway_http_client
        aclose = getattr(client, "aclose", None)
        if callable(aclose):
            await aclose()
            return
        close = getattr(client, "close", None)
        if callable(close):
            close()

    app.router.add_event_handler("shutdown", _close_tool_gateway_http_client)

    if (
        resolved_settings.environment.lower() not in {"development", "dev", "local", "test"}
        and "*" in resolved_settings.cors_origins
    ):
        raise ValueError("CORS wildcard origins are not allowed when credentials are enabled.")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"],
        allow_headers=[
            "Accept",
            "Authorization",
            "Content-Type",
            "baggage",
            "traceparent",
            "tracestate",
            "X-Actor-Type",
            "X-Break-Glass-Reason",
            "X-Correlation-ID",
            "X-Delegated-Provider-Account-ID",
            "X-Delegated-User-ID",
            "X-Environment-ID",
            "X-Organization-ID",
            "X-Request-ID",
            "X-User-ID",
        ],
    )
    app.add_middleware(
        ToolGatewayBodyLimitMiddleware,
        max_body_bytes=int(resolved_settings.api_max_body_bytes),
        path_predicate=_is_api_body_limited_path,
        message="API request body exceeds the configured size limit.",
    )
    app.add_middleware(
        ToolGatewayBodyLimitMiddleware,
        max_body_bytes=int(resolved_settings.tool_gateway_max_body_bytes),
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next: Any) -> Any:
        server_request_id = str(uuid4())
        request_id = _trusted_trace_id(request.headers.get("X-Request-ID")) or server_request_id
        correlation_id = _trusted_trace_id(request.headers.get("X-Correlation-ID")) or request_id
        trace_context = build_request_trace_context(
            traceparent=request.headers.get("traceparent"),
            tracestate=request.headers.get("tracestate"),
            baggage=request.headers.get("baggage"),
        )
        principal = getattr(request.state, "principal", None)
        request.state.request_context = RequestContext(
            request_id=request_id,
            correlation_id=correlation_id,
            server_request_id=server_request_id,
            trace_id=trace_context.trace_id,
            span_id=trace_context.span_id,
            parent_span_id=trace_context.parent_span_id,
            traceparent=trace_context.traceparent,
            tracestate=trace_context.tracestate,
            baggage=trace_context.baggage,
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
        response.headers["traceparent"] = trace_context.traceparent
        if trace_context.tracestate is not None:
            response.headers["tracestate"] = trace_context.tracestate
        if trace_context.baggage is not None:
            response.headers["baggage"] = trace_context.baggage
        return response

    public_api_paths = {"/api/v1/auth/dev-login"}

    def _environment_access_denied_response(request: Request) -> JSONResponse:
        return _error_response(
            request,
            status_code=403,
            code="FORBIDDEN",
            message="Environment access is denied.",
        )

    def _break_glass_reason(request: Request) -> str | None:
        reason = str(request.headers.get("X-Break-Glass-Reason") or "").strip()
        if not reason or len(reason) > 240:
            return None
        return reason

    def _can_use_environment_break_glass(principal: UserPrincipal) -> bool:
        return principal.actor_type == "user" and "Platform Admin" in set(principal.roles)

    def _allow_environment_break_glass(
        *,
        request: Request,
        principal: UserPrincipal,
        organization_id: str,
        environment_id: str,
    ) -> bool:
        reason = _break_glass_reason(request)
        if not reason or not _can_use_environment_break_glass(principal):
            return False
        request.state.selected_organization_id = organization_id
        request.state.selected_environment_id = environment_id
        request.state.environment_break_glass_reason = reason
        _record_environment_break_glass_audit_event(
            request=request,
            principal=principal,
            environment_id=environment_id,
            reason=reason,
        )
        return True

    def _uses_gateway_auth_path(path: str) -> bool:
        return _is_tool_gateway_runtime_path(path)

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next: Any) -> Any:
        if _uses_gateway_auth_path(request.url.path):
            max_body_bytes = int(resolved_settings.tool_gateway_max_body_bytes)
            content_length = request.headers.get("Content-Length")
            if content_length is not None:
                try:
                    body_bytes = int(content_length)
                except ValueError:
                    return _error_response(
                        request,
                        status_code=400,
                        code="INVALID_CONTENT_LENGTH",
                        message="Content-Length must be an integer.",
                    )
                if max_body_bytes > 0 and body_bytes > max_body_bytes:
                    return _error_response(
                        request,
                        status_code=413,
                        code="REQUEST_BODY_TOO_LARGE",
                        message="Tool Gateway request body exceeds the configured size limit.",
                    )
            rate_limited, retry_after_seconds = _tool_gateway_rate_limit_result(
                app,
                request,
                _audit_database,
            )
            if rate_limited:
                return _error_response(
                    request,
                    status_code=429,
                    code="TOOL_GATEWAY_RATE_LIMITED",
                    message="Tool Gateway rate limit exceeded.",
                    headers={"Retry-After": str(retry_after_seconds)},
                )
        if (
            request.url.path.startswith("/api/v1")
            and request.url.path not in public_api_paths
            and not _uses_gateway_auth_path(request.url.path)
        ):
            principal = auth_service.authenticate_request(request)
            if principal is None:
                authorization = request.headers.get("Authorization", "")
                scheme, _, token = authorization.partition(" ")
                if scheme.lower() == "bearer" and token:
                    if use_persistent_api_keys:
                        with _audit_database().transaction() as connection:
                            api_key_result = _api_key_store(connection).authenticate_with_result(
                                token
                            )
                            principal = api_key_result.principal
                            if principal is None:
                                _record_api_key_auth_failure_audit_event(
                                    request=request,
                                    result=api_key_result,
                                    token=token,
                                    connection=connection,
                                )
                    else:
                        api_key_result = api_keys.authenticate_with_result(token)
                        principal = api_key_result.principal
                        if principal is None:
                            _record_api_key_auth_failure_audit_event(
                                request=request,
                                result=api_key_result,
                                token=token,
                            )
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
            organization_id = str(selected_organization_id)
            if tenants.get_organization(organization_id) is None:
                return _error_response(
                    request,
                    status_code=403,
                    code="FORBIDDEN",
                    message="Organization access is denied.",
                )
            selected_environment_id = request.headers.get("X-Environment-ID")
            if selected_environment_id:
                environment = tenants.get_environment(selected_environment_id)
                if environment is None or environment.organization_id != organization_id:
                    return _error_response(
                        request,
                        status_code=403,
                        code="FORBIDDEN",
                        message="Environment access is denied.",
                    )
                allowed_environment_ids = list(getattr(principal, "environment_ids", []))
                if selected_environment_id not in allowed_environment_ids:
                    if not _allow_environment_break_glass(
                        request=request,
                        principal=principal,
                        organization_id=organization_id,
                        environment_id=selected_environment_id,
                    ):
                        if principal.actor_type == "api_key":
                            _record_api_key_scope_violation_audit_event(
                                request=request,
                                principal=principal,
                                requested_environment_id=selected_environment_id,
                            )
                        return _environment_access_denied_response(request)
            request.state.selected_organization_id = organization_id
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
            details=_validation_error_details(exc, resolved_settings.environment),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(
            request,
            status_code=exc.status_code,
            code="HTTP_ERROR",
            message=_safe_http_error_message(exc, resolved_settings.environment),
            details={},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        details = (
            {"error_type": exc.__class__.__name__}
            if _is_local_environment(resolved_settings.environment)
            else {}
        )
        return _error_response(
            request,
            status_code=500,
            code="INTERNAL_ERROR",
            message="Internal server error.",
            details=details,
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
        if (
            not _is_local_environment(resolved_settings.environment)
            and not is_supported_database_url(resolved_settings.database_url)
        ):
            raise RuntimeError("A configured database is required outside local/test environments.")
        if resolved_settings.environment.strip().lower() == "test":
            from product_platform.db.testing import create_migrated_test_database

            created = create_migrated_test_database()
        else:
            created = Database(
                resolved_settings.database_url,
                max_pool_size=int(resolved_settings.database_max_pool_size),
            )
            created.migrate()
        if _is_local_environment(resolved_settings.environment):
            with created.transaction() as connection:
                seed_demo_data(connection)
        app.state.database = created
        return created

    def _secret_provider() -> SecretProvider:
        provider = getattr(app.state, "secret_provider", None)
        if provider is None:
            provider = build_secret_provider(
                resolved_settings.secret_manager_ref,
                environment=resolved_settings.environment,
            )
            app.state.secret_provider = provider
        return provider

    def _require_organization_id(current_user: UserPrincipal) -> str:
        if current_user.organization_id is None:
            raise HTTPException(status_code=400, detail="Organization context is required.")
        return current_user.organization_id

    def _default_environment_id_for_org(organization_id: str) -> str:
        environments = tenants.list_environments(organization_id)
        return environments[0].id if environments else "env_default"

    def _existing_audit_environment_id(
        connection: Any,
        organization_id: str,
        preferred_environment_id: str | None,
    ) -> str | None:
        if preferred_environment_id:
            row = connection.execute(
                """
                SELECT id
                FROM environments
                WHERE id = ? AND organization_id = ?
                """,
                (preferred_environment_id, organization_id),
            ).fetchone()
            if row is not None:
                return str(row["id"])
        row = connection.execute(
            """
            SELECT id
            FROM environments
            WHERE organization_id = ?
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (organization_id,),
        ).fetchone()
        return str(row["id"]) if row is not None else None

    def _record_permission_denied_audit_event(
        request: Request,
        principal: UserPrincipal,
        event: dict[str, Any],
    ) -> None:
        organization_id = principal.organization_id
        if not organization_id:
            return
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            environment_id = _existing_audit_environment_id(
                connection,
                organization_id,
                getattr(request.state, "selected_environment_id", None)
                or context.environment_id
                or _default_environment_id_for_org(organization_id),
            )
            if environment_id is None:
                return
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="auth.permission_denied",
                    source_component="authz",
                    actor_type=principal.actor_type,
                    actor_id=principal.id,
                    resource_type="api_route",
                    resource_id=str(event.get("path") or request.url.path),
                    decision="deny",
                    severity="warning",
                    correlation_id=context.correlation_id,
                    trace_id=context.request_id,
                    payload_json={
                        "permission": str(event.get("permission") or ""),
                        "method": str(event.get("method") or request.method),
                        "path": str(event.get("path") or request.url.path),
                        "roles": list(getattr(principal, "roles", [])),
                    },
                )
            )

    app.state.permission_denied_audit_recorder = _record_permission_denied_audit_event

    def _record_environment_break_glass_audit_event(
        *,
        request: Request,
        principal: UserPrincipal,
        environment_id: str,
        reason: str,
    ) -> None:
        organization_id = principal.organization_id
        if not organization_id:
            return
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            existing_environment_id = _existing_audit_environment_id(
                connection,
                organization_id,
                environment_id,
            )
            if existing_environment_id is None:
                return
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=existing_environment_id,
                    event_type="auth.environment_break_glass",
                    source_component="authz",
                    actor_type=principal.actor_type,
                    actor_id=principal.id,
                    resource_type="environment",
                    resource_id=existing_environment_id,
                    decision="allow",
                    severity="warning",
                    correlation_id=context.correlation_id,
                    trace_id=context.request_id,
                    payload_json={
                        "reason": reason,
                        "roles": list(principal.roles),
                        "path": request.url.path,
                        "method": request.method,
                    },
                )
            )

    def _record_admin_settings_audit_event(
        *,
        request: Request,
        principal: UserPrincipal,
        event_type: str,
        resource_type: str,
        resource_id: str,
        payload_json: dict[str, Any],
        connection: Any | None = None,
    ) -> None:
        organization_id = principal.organization_id
        if not organization_id:
            return
        context = _request_context_from_request(request)

        def insert_event(target_connection: Any) -> None:
            environment_id = _existing_audit_environment_id(
                target_connection,
                organization_id,
                getattr(request.state, "selected_environment_id", None)
                or context.environment_id
                or _default_environment_id_for_org(organization_id),
            )
            if environment_id is None:
                return
            AuditEventRepository(target_connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type=event_type,
                    source_component="admin-settings",
                    actor_type=principal.actor_type,
                    actor_id=principal.id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    decision="allow",
                    correlation_id=context.correlation_id,
                    trace_id=context.request_id,
                    payload_json=payload_json,
                )
            )

        if connection is not None:
            insert_event(connection)
            return
        with _audit_database().transaction() as audit_connection:
            insert_event(audit_connection)

    def _should_audit_api_key_auth_failure(
        result: ApiKeyAuthenticationResult,
        token: str,
    ) -> bool:
        return result.reason_code is not None and (
            result.record is not None or token.startswith("opx_")
        )

    def _record_api_key_auth_failure_audit_event(
        *,
        request: Request,
        result: ApiKeyAuthenticationResult,
        token: str,
        connection: Any | None = None,
    ) -> None:
        if not _should_audit_api_key_auth_failure(result, token):
            return
        record = result.record
        organization_id = (
            record.organization_id
            if record is not None
            else request.headers.get("X-Organization-ID")
            or resolved_settings.default_organization_id
        )
        key_id = record.id if record is not None else None
        environment_ids = list(record.environment_ids) if record is not None else []
        environment_id = (
            request.headers.get("X-Environment-ID")
            or (environment_ids[0] if environment_ids else None)
            or _default_environment_id_for_org(organization_id)
        )
        context = _request_context_from_request(request)

        def insert_event(target_connection: Any) -> None:
            existing_environment_id = _existing_audit_environment_id(
                target_connection,
                organization_id,
                environment_id,
            )
            if existing_environment_id is None:
                return
            payload: dict[str, Any] = {
                "reason_code": result.reason_code,
                "path": request.url.path,
                "method": request.method,
                "requested_environment_id": request.headers.get("X-Environment-ID"),
            }
            if key_id is not None:
                payload["key_id"] = key_id
            if environment_ids:
                payload["environment_ids"] = environment_ids
            if record is not None:
                payload["expires_at"] = record.expires_at
                payload["revoked_at"] = record.revoked_at
                payload["revoked_reason"] = record.revoked_reason
            AuditEventRepository(target_connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=existing_environment_id,
                    event_type="auth.api_key.authentication_failed",
                    source_component="api-key-auth",
                    actor_type="api_key" if key_id else "system",
                    actor_id=key_id,
                    resource_type="api_key" if key_id else "api_key_authentication",
                    resource_id=key_id,
                    decision="deny",
                    severity="warning",
                    correlation_id=context.correlation_id,
                    trace_id=context.request_id,
                    payload_json=payload,
                )
            )

        if connection is not None:
            insert_event(connection)
            return
        with _audit_database().transaction() as audit_connection:
            insert_event(audit_connection)

    def _record_api_key_scope_violation_audit_event(
        *,
        request: Request,
        principal: UserPrincipal,
        requested_environment_id: str,
    ) -> None:
        organization_id = principal.organization_id
        if not organization_id:
            return
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            environment_id = _existing_audit_environment_id(
                connection,
                organization_id,
                requested_environment_id,
            )
            if environment_id is None:
                return
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="auth.api_key.scope_violation",
                    source_component="api-key-auth",
                    actor_type="api_key",
                    actor_id=principal.id,
                    resource_type="api_key",
                    resource_id=principal.id,
                    decision="deny",
                    severity="warning",
                    correlation_id=context.correlation_id,
                    trace_id=context.request_id,
                    payload_json={
                        "reason_code": "api_key_scope_violation",
                        "requested_environment_id": requested_environment_id,
                        "environment_ids": list(getattr(principal, "environment_ids", [])),
                        "path": request.url.path,
                        "method": request.method,
                    },
                )
            )

    def _gateway_token_verification_audit_event(
        *,
        request: Request,
        result: str,
        reason_code: str,
        principal: GatewayPrincipal | None = None,
        error: GatewayAuthenticationError | None = None,
    ) -> AuditEventEnvelope:
        context = _request_context_from_request(request)
        organization_id = (
            principal.organization_id
            if principal is not None
            else error.organization_id
            if error is not None and error.organization_id is not None
            else request.headers.get("X-Organization-ID")
            or resolved_settings.default_organization_id
        )
        environment_id = (
            principal.environment_id
            if principal is not None
            else error.environment_id
            if error is not None and error.environment_id is not None
            else request.headers.get("X-Environment-ID")
            or _default_environment_id_for_org(organization_id)
        )
        agent_id = principal.agent_id if principal is not None else error.agent_id if error else None
        credential_id = (
            principal.credential_id
            if principal is not None
            else error.credential_id
            if error
            else None
        )
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=f"gateway.token_verification.{result}",
            source_component="tool-gateway-auth",
            actor_type="agent" if agent_id else "system",
            agent_id=agent_id,
            resource_type="agent_credential" if credential_id else "gateway_token_verification",
            resource_id=credential_id,
            decision="allow" if result == "succeeded" else "deny",
            severity="info" if result == "succeeded" else "warning",
            correlation_id=context.correlation_id,
            payload_json={
                "result": result,
                "reason_code": reason_code,
                "request_id": context.request_id,
            },
        )

    def _append_tool_runtime_event(
        repository: ToolRuntimeActionRepository,
        action_id: str,
        event_type: str,
        event_summary: dict[str, Any],
    ) -> None:
        repository.append_event(
            action_id,
            ToolRuntimeActionEventCreate(
                event_type=event_type,
                event_summary=event_summary,
            ),
        )

    def _record_gateway_auth_failure_runtime_action(
        *,
        connection: Any,
        request: Request,
        error: GatewayAuthenticationError,
    ) -> None:
        if not error.organization_id or not error.environment_id:
            return
        if not error.agent_id and not error.credential_id:
            return
        context = _request_context_from_request(request)
        repository = ToolRuntimeActionRepository(
            connection,
            error.organization_id,
            error.environment_id,
        )
        row = repository.create_action(
            ToolRuntimeActionCreate(
                request_id=context.request_id,
                correlation_id=context.correlation_id,
                **_trace_context_fields(context),
                agent_id=error.agent_id,
                credential_id=error.credential_id,
                action_status="authentication_failed",
                reason_code=error.reason_code,
                payload_summary={
                    "path": request.url.path,
                    "reason_code": error.reason_code,
                },
                error_code=error.reason_code,
            )
        )
        _append_tool_runtime_event(
            repository,
            row["id"],
            "tool.runtime.authentication_failed",
            {"reason_code": error.reason_code},
        )

    def _runtime_response_summary(
        execution: Any,
        *,
        store_full_response: bool = False,
    ) -> dict[str, Any]:
        if isinstance(execution, ToolExecutionResult):
            return {
                "status": execution.status,
                "body": execution.body if store_full_response else None,
                "body_stored": bool(store_full_response),
                "upstream_status_code": execution.upstream_status_code,
                "response_schema_valid": execution.response_schema_valid,
                "redaction_applied": execution.redaction_applied,
                "exposed_to_agent": execution.exposed_to_agent,
                "warnings": execution.warnings,
            }
        if isinstance(execution, dict):
            return {"result": execution}
        return {"result": jsonable_encoder(execution)}

    def _runtime_execution_error_code(execution: ToolExecutionResult) -> str:
        if isinstance(execution.error, dict) and execution.error.get("code"):
            return str(execution.error["code"])
        return "upstream_error"

    def _response_policy_store_full_response(response_policy: Any | None) -> bool:
        if response_policy is None:
            return False
        try:
            status = str(response_policy["status"]).strip().lower()
        except Exception:
            status = "active"
        if status != "active":
            return False
        return bool(response_policy["store_full_response"])

    def _get_gateway_principal(request: Request) -> GatewayPrincipal:
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                principal = GatewayTokenVerifier(connection).verify_authorization_header(
                    request.headers.get("Authorization"),
                    request_id=context.request_id,
                )
                principal.delegated_user_id = _trusted_trace_id(
                    request.headers.get("X-Delegated-User-ID")
                )
                principal.delegated_provider_account_id = _trusted_trace_id(
                    request.headers.get("X-Delegated-Provider-Account-ID")
                )
                AuditEventRepository(connection).insert(
                    _gateway_token_verification_audit_event(
                        request=request,
                        result="succeeded",
                        reason_code="verified",
                        principal=principal,
                    )
                )
                request.state.gateway_principal = principal
                return principal
        except GatewayAuthenticationError as exc:
            with _audit_database().transaction() as connection:
                AuditEventRepository(connection).insert(
                    _gateway_token_verification_audit_event(
                        request=request,
                        result="failed",
                        reason_code=exc.reason_code,
                        error=exc,
                    )
                )
                _record_gateway_auth_failure_runtime_action(
                    connection=connection,
                    request=request,
                    error=exc,
                )
            raise HTTPException(
                status_code=401,
                detail="Gateway authentication failed.",
            ) from exc

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
            max_size_bytes=int(resolved_settings.artifact_max_bytes),
        )

    def _api_key_store(connection: Any) -> DatabaseApiKeyStore:
        return DatabaseApiKeyStore(connection, api_key_hash_pepper)

    def _api_key_environment_scope(
        requested_environment_ids: list[str],
        *,
        organization_id: str,
        selected_environment_id: str,
    ) -> list[str]:
        environment_ids = list(requested_environment_ids or [selected_environment_id])
        if not environment_ids:
            raise HTTPException(status_code=400, detail="At least one API key environment is required.")
        for requested_environment_id in environment_ids:
            environment = tenants.get_environment(requested_environment_id)
            if environment is None or environment.organization_id != organization_id:
                raise HTTPException(status_code=400, detail="API key environment is not visible.")
        return environment_ids

    def _api_key_expiration(requested_expires_at: int | None) -> int:
        now = int(time.time())
        default_ttl = max(1, int(resolved_settings.api_key_default_ttl_seconds))
        max_ttl = max(default_ttl, int(resolved_settings.api_key_max_ttl_seconds))
        expires_at = int(requested_expires_at) if requested_expires_at is not None else now + default_ttl
        if expires_at <= now:
            raise HTTPException(status_code=400, detail="API key expiration must be in the future.")
        if expires_at - now > max_ttl:
            raise HTTPException(status_code=400, detail="API key expiration exceeds policy.")
        return expires_at

    def _api_key_reason(value: str | None, fallback: str) -> str:
        reason = str(value or "").strip()
        return reason or fallback

    def _create_generated_artifact(
        *,
        connection: Any,
        organization_id: str,
        environment_id: str,
        artifact_type: str,
        name: str,
        content_type: str,
        content: bytes,
        actor_id: str,
        target_type: str,
        target_id: str,
        link_type: str,
    ) -> Any:
        repository = _artifact_repository(connection, organization_id, environment_id)
        artifact = repository.create(
            ArtifactCreateRequest(
                artifact_type=artifact_type,
                name=name,
                content_type=content_type,
                content_base64=base64.b64encode(content).decode("ascii"),
            ),
            actor_id=actor_id,
        )
        repository.create_link(
            artifact["id"],
            ArtifactLinkCreateRequest(
                target_type=target_type,
                target_id=target_id,
                link_type=link_type,
            ),
        )
        return artifact

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
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> WorkflowRunResponse:
        """Create and optionally execute a workflow run."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
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
            if not body.run_immediately:
                JobStateRepository(connection).create_job(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    job_type=WORKFLOW_JOB_TYPE,
                    queue_name="workflows",
                    payload={
                        "workflow_run_id": run["id"],
                        "workflow_definition_id": definition["id"],
                        "workflow_type": definition["workflow_type"],
                        "command_ref": definition["command_ref"],
                        "inputs": body.inputs,
                        "started_by": current_user.id,
                    },
                    max_attempts=3,
                    job_id=run["id"],
                    **_trace_context_fields(context),
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
                try:
                    JobStateRepository(connection).cancel(
                        run_id,
                        organization_id=organization_id,
                        environment_id=environment_id,
                    )
                except (KeyError, JobStateConflictError):
                    pass
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
        if not _is_local_environment(resolved_settings.environment):
            raise HTTPException(status_code=404, detail="Demo reset is not available.")
        environment = tenants.get_environment(environment_id)
        if environment is None or environment.type not in {"development", "demo", "local-demo", "test"}:
            raise HTTPException(status_code=403, detail="Demo reset is only available for demo environments.")
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
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
        except Exception as exc:
            with _audit_database().transaction() as connection:
                record_demo_reset_failure(
                    connection,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    requested_by=current_user.id,
                    error_message=exc.__class__.__name__,
                    correlation_id=context.correlation_id,
                )
            raise HTTPException(status_code=500, detail="Demo reset failed.") from exc

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

    def _format_policy_evaluation_sse_event(evaluation: PolicyEvaluationResponse) -> str:
        data = json.dumps(evaluation.model_dump(mode="json"), sort_keys=True)
        return f"id: {evaluation.id}\nevent: policy_evaluation\ndata: {data}\n\n"

    def _resolve_policy_evaluation_stream_environment(
        *,
        request: Request,
        organization_id: str,
        environment_id: str | None,
    ) -> str:
        selected_environment_id = environment_id or getattr(
            request.state,
            "selected_environment_id",
            None,
        )
        if not selected_environment_id:
            raise HTTPException(status_code=400, detail="environment_id query parameter or X-Environment-ID is required.")
        environment = tenants.get_environment(selected_environment_id)
        if environment is None or environment.organization_id != organization_id:
            raise HTTPException(status_code=403, detail="Environment access is denied.")
        return str(selected_environment_id)

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

    def _record_agent_registration_policy_evaluation(
        *,
        connection: Any,
        organization_id: str,
        environment_id: str,
        simulation: AgentRegistrationSimulationResponse,
        capability_names: list[str],
        policy_ids: list[str],
        correlation_id: str | None,
    ) -> None:
        try:
            persisted_policy_id = _first_persisted_policy_id(connection, organization_id, policy_ids)
            PolicyEvaluationRepository(connection).create(
                PolicyEvaluationResponse(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    policy_id=persisted_policy_id,
                    agent_id=simulation.agent_id,
                    target_type="agent",
                    target_id=simulation.agent_id,
                    action=simulation.action or "agent.registration.simulate",
                    resource_type="agent_registration_draft",
                    resource_id=simulation.agent_id,
                    context={
                        "capability_names": capability_names,
                        "matched_policy_ids": simulation.matched_policy_ids,
                        "selected_policy_ids": policy_ids,
                    },
                    decision=_policy_feed_decision(simulation.decision),
                    policy_action=simulation.decision,
                    matched_rule="agent_registration_policy_selection",
                    reason=simulation.reason,
                    latency_ms=0.0,
                    mode="simulate",
                    correlation_id=correlation_id,
                    backend="agent-registration",
                    audit_preview={
                        "event_type": "agent.registration.simulated",
                        "resource_type": "agent_registration_draft",
                        "resource_id": simulation.agent_id,
                    },
                )
            )
        except Exception:
            return

    def _record_integration_health_policy_evaluation(
        *,
        connection: Any,
        organization_id: str,
        environment_id: str,
        health_check: Any,
        correlation_id: str | None,
        credential: Any | None = None,
    ) -> None:
        try:
            status = str(health_check["status"])
            decision = "allow" if status in {"healthy", "ok", "passed"} else "deny"
            context = {
                "health_check_id": health_check["id"],
                "health_status": status,
                "message": health_check["message"],
                "details": _loads_json_mapping(health_check["details_json"]),
            }
            if credential is not None:
                context.update(
                    {
                        "provider_credential_id": credential["id"],
                        "provider_type": credential["provider_type"],
                        "credential_status": credential["status"],
                    }
                )
            target_type = str(health_check["target_type"])
            action = (
                "integration.provider_credential.test"
                if target_type == "provider_credential"
                else "integration.health_check"
            )
            PolicyEvaluationRepository(connection).create(
                PolicyEvaluationResponse(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    agent_id=None,
                    target_type="framework-connector",
                    target_id=str(health_check["target_id"]),
                    action=action,
                    resource_type=target_type,
                    resource_id=str(health_check["target_id"]),
                    context=context,
                    decision=decision,
                    policy_action=status,
                    matched_rule=f"integration_health:{status}",
                    reason=str(health_check["message"]),
                    latency_ms=float(health_check["latency_ms"]),
                    mode="live",
                    correlation_id=correlation_id,
                    backend="integration-health",
                    audit_preview={
                        "event_type": "integration.health_check",
                        "resource_type": target_type,
                        "resource_id": str(health_check["target_id"]),
                    },
                )
            )
        except Exception:
            return

    def _first_persisted_policy_id(
        connection: Any,
        organization_id: str,
        policy_ids: list[str],
    ) -> str | None:
        repository = PolicyRepository(connection, organization_id)
        for policy_id in policy_ids:
            if repository.get_policy(policy_id) is not None:
                return policy_id
        return None

    def _loads_json_mapping(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else {}

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
        decision: str | None = None,
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
            decision=decision,
            severity="warning" if decision == "deny" else "info",
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

    def _trust_handshake_blocked_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        body: TrustHandshakeRequest,
        reason: str,
        reason_code: str,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="trust.handshake.blocked",
            source_component="trust-handshakes",
            actor_type="user",
            actor_id=actor_id,
            agent_id=body.source_agent_id,
            resource_type="handshake",
            resource_id=body.target_agent_id,
            decision="deny",
            severity="warning",
            correlation_id=correlation_id,
            payload_json={
                "source_agent_id": body.source_agent_id,
                "target_agent_id": body.target_agent_id,
                "purpose": body.purpose,
                "threshold_type": body.threshold_type,
                "reason": reason,
                "reason_code": reason_code,
            },
        )

    def _trust_handshake_challenge_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        challenge: TrustHandshakeChallengeResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="trust.handshake.challenge_issued",
            source_component="trust-handshakes",
            actor_type="user",
            actor_id=actor_id,
            agent_id=challenge.source_agent_id,
            resource_type="handshake_challenge",
            resource_id=challenge.challenge_id,
            decision="allow",
            severity="info",
            correlation_id=correlation_id,
            payload_json={
                "challenge_id": challenge.challenge_id,
                "source_agent_id": challenge.source_agent_id,
                "target_agent_id": challenge.target_agent_id,
                "audience": challenge.audience,
                "environment_id": challenge.environment_id,
                "contract_version": challenge.contract_version,
                "signature_algorithm": challenge.signature_algorithm,
                "expires_at": challenge.expires_at,
            },
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

    def _mesh_handoff_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        handoff: MeshHandoffResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        status = handoff.status.lower()
        event_type = "mesh.handoff.escalated" if status in {"requires_approval", "escalated"} else "mesh.handoff.blocked"
        decision = "allow" if status in {"accepted", "allowed"} else "deny"
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="mesh-message-feed",
            actor_type="user",
            actor_id=actor_id,
            agent_id=handoff.source_agent_id,
            resource_type="mesh_handoff",
            resource_id=handoff.id,
            decision=decision,
            severity="warning" if decision == "deny" else "info",
            correlation_id=correlation_id,
            payload_json=handoff.model_dump(),
        )

    def _mesh_blocked_attempt_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        source_agent_id: str,
        target_agent_id: str,
        resource_type: str,
        reason: str,
        correlation_id: str | None,
        payload_json: dict[str, Any],
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="mesh-message-feed",
            actor_type="user",
            actor_id=actor_id,
            agent_id=source_agent_id,
            resource_type=resource_type,
            resource_id=target_agent_id,
            decision="deny",
            severity="warning",
            correlation_id=correlation_id,
            payload_json={
                **payload_json,
                "source_agent_id": source_agent_id,
                "target_agent_id": target_agent_id,
                "reason": reason,
            },
        )

    def _mesh_trust_snapshot(
        *,
        connection: Any,
        organization_id: str,
        environment_id: str,
        agent_id: str,
    ) -> dict[str, Any]:
        trust_score = TrustRepository(connection, organization_id, environment_id).get_score(agent_id)
        if trust_score is not None:
            return {
                "agent_id": agent_id,
                "score": int(trust_score["score"]),
                "tier": trust_score["tier"],
                "calculated_at": trust_score["calculated_at"],
                "source": "trust_scores",
            }
        row = connection.execute(
            """
            SELECT trust_score, trust_tier
            FROM agents
            WHERE id = ?
              AND organization_id = ?
              AND environment_id = ?
              AND deleted_at IS NULL
            """,
            (agent_id, organization_id, environment_id),
        ).fetchone()
        score = int(row["trust_score"]) if row is not None and row["trust_score"] is not None else 500
        return {
            "agent_id": agent_id,
            "score": score,
            "tier": row["trust_tier"] if row is not None and row["trust_tier"] else "standard",
            "calculated_at": None,
            "source": "agent_snapshot",
        }

    def _mesh_trust_decision(
        *,
        connection: Any,
        organization_id: str,
        environment_id: str,
        source_agent_id: str,
        target_agent_id: str,
        threshold_type: str,
    ) -> dict[str, Any]:
        repository = TrustRepository(connection, organization_id, environment_id)
        repository.seed_default_thresholds()
        resolution = TrustThresholdResolver(repository).resolve(
            TrustThresholdResolveRequest(
                threshold_type=threshold_type,
                target_type="environment",
                target_id=None,
            )
        )
        source_snapshot = _mesh_trust_snapshot(
            connection=connection,
            organization_id=organization_id,
            environment_id=environment_id,
            agent_id=source_agent_id,
        )
        target_snapshot = _mesh_trust_snapshot(
            connection=connection,
            organization_id=organization_id,
            environment_id=environment_id,
            agent_id=target_agent_id,
        )
        required_rank = TRUST_TIER_RANK[resolution.required_tier]
        source_rank = TRUST_TIER_RANK[source_snapshot["tier"]]
        target_rank = TRUST_TIER_RANK[target_snapshot["tier"]]
        allowed = (
            not resolution.fail_closed
            and source_snapshot["score"] >= resolution.min_score
            and target_snapshot["score"] >= resolution.min_score
            and source_rank >= required_rank
            and target_rank >= required_rank
        )
        reason = "trust_threshold_satisfied" if allowed else (
            resolution.reason if resolution.fail_closed else "low_trust"
        )
        return {
            "decision": "allow" if allowed else "deny",
            "reason": reason,
            "threshold_resolution": resolution.model_dump(),
            "source_trust_snapshot": source_snapshot,
            "target_trust_snapshot": target_snapshot,
        }

    def _mesh_policy_decision(
        *,
        connection: Any,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        source_agent_id: str,
        target_agent_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        context: dict[str, Any],
        correlation_id: str | None,
    ) -> PolicyEvaluationResponse:
        evaluation = PolicyEvaluationAdapter(
            connection,
            organization_id,
            environment_id,
        ).evaluate(
            PolicyEvaluationRequest(
                target_type="environment",
                target_id=environment_id,
                agent_id=source_agent_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                context={
                    **context,
                    "source_agent_id": source_agent_id,
                    "target_agent_id": target_agent_id,
                },
                mode="live",
            ),
            correlation_id=correlation_id,
        )
        row = PolicyEvaluationRepository(connection).create(evaluation)
        persisted = policy_evaluation_response(row)
        AuditEventRepository(connection).insert(
            _policy_evaluation_audit_event(
                evaluation=persisted,
                actor_id=actor_id,
            )
        )
        return persisted

    def _policy_decision_name(evaluation: PolicyEvaluationResponse) -> str:
        action = evaluation.policy_action.strip().lower()
        if evaluation.error or evaluation.decision == "deny" or action == "deny":
            return "deny"
        if action in {"approve", "approval", "require_approval", "requires_approval", "escalate", "escalated"}:
            return "requires_approval"
        return "allow"

    def _server_mesh_decision_evidence(
        *,
        policy: PolicyEvaluationResponse,
        trust: dict[str, Any],
        client_supplied: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "policy_evaluation_id": policy.id,
            "policy_id": policy.policy_id,
            "policy_version_id": policy.policy_version_id,
            "binding_id": policy.binding_id,
            "binding_mode": policy.binding_mode,
            "policy_decision": policy.decision,
            "policy_action": policy.policy_action,
            "matched_rule": policy.matched_rule,
            "reason": policy.reason,
            "backend": policy.backend,
            "trust_decision": trust["decision"],
            "trust_reason": trust["reason"],
            "threshold_resolution": trust["threshold_resolution"],
            "source_trust_snapshot": trust["source_trust_snapshot"],
            "target_trust_snapshot": trust["target_trust_snapshot"],
            "client_supplied": client_supplied,
        }

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

    def _tool_definition_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        tool: ToolDefinitionResponse,
        correlation_id: str | None,
        previous_status: str | None = None,
        reason: str | None = None,
    ) -> AuditEventEnvelope:
        payload = tool.model_dump()
        if previous_status is not None:
            payload["previous_status"] = previous_status
            payload["status_changed"] = previous_status != tool.status
        if reason is not None:
            payload["reason"] = reason
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="tool-gateway-registry",
            actor_type="user",
            actor_id=actor_id,
            resource_type="tool_definition",
            resource_id=tool.id,
            correlation_id=correlation_id,
            payload_json=payload,
        )

    def _tool_upstream_target_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        target: ToolUpstreamTargetResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="tool-gateway-upstreams",
            actor_type="user",
            actor_id=actor_id,
            resource_type="tool_upstream_target",
            resource_id=target.id,
            correlation_id=correlation_id,
            payload_json=target.model_dump(),
        )

    def _agent_tool_permission_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        permission: AgentToolPermissionResponse,
        correlation_id: str | None,
        reason: str | None = None,
    ) -> AuditEventEnvelope:
        payload = permission.model_dump()
        if reason is not None:
            payload["reason"] = reason
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="tool-gateway-permissions",
            actor_type="user",
            actor_id=actor_id,
            agent_id=permission.agent_id,
            resource_type="agent_tool_permission",
            resource_id=permission.id,
            correlation_id=correlation_id,
            payload_json=payload,
        )

    def _schema_validation_error_response(
        request: Request,
        exc: ToolSchemaValidationError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=422,
            code="SCHEMA_VALIDATION_ERROR",
            message="Payload failed schema validation.",
            details={"field": exc.field},
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

    def _archive_runtime_session_if_active(
        *,
        repository: RuntimeRepository,
        audit_repository: AuditEventRepository,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        session_id: str,
        reason: str,
        correlation_id: str | None,
    ) -> RuntimeSessionResponse | None:
        session_row = repository.get_session(session_id)
        if session_row is None or session_row["state"] != "active":
            return None
        session = runtime_session_response(repository.end_session(session_id, reason=reason))
        audit_repository.insert(
            _runtime_session_audit_event(
                organization_id=organization_id,
                environment_id=environment_id,
                actor_id=actor_id,
                event_type="runtime.session.ended",
                session=session,
                correlation_id=correlation_id,
            )
        )
        return session

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
        worker_job_id = step.result.get("worker_job_id")
        idempotency_key = step.result.get("idempotency_key")
        external_operation_id = step.result.get("external_operation_id")
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
                "worker_job_id": worker_job_id,
                "idempotency_key": idempotency_key,
                "external_operation_id": external_operation_id,
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

    def _plugin_installation_blocked_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        body: PluginInstallationCreateRequest,
        reason: str,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="marketplace.plugin.install_blocked",
            source_component="marketplace",
            actor_type="user",
            actor_id=actor_id,
            agent_id=body.target_agent_id,
            resource_type="plugin_version",
            resource_id=body.plugin_version_id,
            decision="deny",
            severity="warning",
            correlation_id=correlation_id,
            payload_json={
                "plugin_version_id": body.plugin_version_id,
                "environment_id": body.environment_id,
                "target_agent_id": body.target_agent_id,
                "reason": reason,
            },
        )

    def _plugin_runtime_tool_grants_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        event_type: str,
        installation: PluginInstallationResponse,
        grants: list[Any],
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        decision = "deny" if event_type.endswith(".revoked") else "allow"
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="marketplace-runtime-grants",
            actor_type="user",
            actor_id=actor_id,
            agent_id=installation.target_agent_id,
            resource_type="plugin_installation",
            resource_id=installation.id,
            decision=decision,
            severity="info",
            correlation_id=correlation_id,
            payload_json={
                "plugin_installation_id": installation.id,
                "plugin_version_id": installation.plugin_version_id,
                "environment_id": environment_id,
                "target_agent_id": installation.target_agent_id,
                "grants": [
                    {
                        "id": grant["id"],
                        "tool_id": grant["tool_id"],
                        "tool_name": grant["tool_name"],
                        "scope": grant["scope"],
                        "status": grant["status"],
                        "agent_tool_permission_id": grant["agent_tool_permission_id"],
                    }
                    for grant in grants
                ],
            },
        )

    def _plugin_runtime_tool_grants_plugin_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        plugin_id: str,
        event_type: str,
        grants: list[Any],
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event_type,
            source_component="marketplace-runtime-grants",
            actor_type="user",
            actor_id=actor_id,
            resource_type="plugin",
            resource_id=plugin_id,
            decision="deny",
            severity="info",
            correlation_id=correlation_id,
            payload_json={
                "plugin_id": plugin_id,
                "environment_id": environment_id,
                "grants": [
                    {
                        "id": grant["id"],
                        "installation_id": grant["installation_id"],
                        "tool_id": grant["tool_id"],
                        "tool_name": grant["tool_name"],
                        "scope": grant["scope"],
                        "status": grant["status"],
                        "agent_tool_permission_id": grant["agent_tool_permission_id"],
                    }
                    for grant in grants
                ],
            },
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

    def _plugin_artifact_evidence_audit_event(
        *,
        organization_id: str,
        environment_id: str,
        actor_id: str,
        evidence: PluginArtifactEvidenceResponse,
        correlation_id: str | None,
    ) -> AuditEventEnvelope:
        return AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type="marketplace.plugin.artifact_evidence.recorded",
            source_component="marketplace-artifacts",
            actor_type="user",
            actor_id=actor_id,
            resource_type="plugin_artifact_evidence",
            resource_id=evidence.id,
            decision="allow" if evidence.status == "passed" else "deny",
            severity="info" if evidence.status == "passed" else "warning",
            correlation_id=correlation_id,
            payload_json=evidence.model_dump(),
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
            dependencies=[],
            uptime_seconds=round(time.monotonic() - started_at, 3),
        )

    @app.get("/ready", response_model=HealthStatus, tags=["system"])
    async def ready() -> HealthStatus:
        """Return readiness information."""

        ready_status, dependencies = registry.readiness_status()
        payload = HealthStatus(
            status="ready" if ready_status else "unhealthy",
            version=__version__,
            dependencies=_public_dependency_statuses(
                dependencies,
                expose_messages=resolved_settings.environment.strip().lower() != "production",
            ),
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

        if not enable_api_docs:
            raise HTTPException(status_code=404, detail="OpenAPI schema is disabled.")
        return app.openapi()

    @app.get("/api/v1/system/config", response_model=PublicConfig, tags=["system"])
    async def system_config() -> PublicConfig:
        """Return configuration safe for frontend clients."""

        return PublicConfig(
            app_name=resolved_settings.app_name,
            environment=resolved_settings.environment,
            api_base_path=resolved_settings.api_base_path,
            docs_url="/docs" if enable_api_docs else None,
            cors_origins=resolved_settings.cors_origins,
            features={
                "auth": True,
                "audit": True,
                "worker": True,
                "frontend_shell": False,
            },
        )

    if enable_dev_login:

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
                secure=not _is_local_environment(resolved_settings.environment),
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

    @app.get(
        "/api/v1/gateway/tools",
        response_model=list[GatewayToolDefinitionResponse] | GatewayToolListPageResponse,
        tags=["tool-gateway"],
    )
    async def list_gateway_callable_tools(
        owner_team: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        pagination: str = Query(default="offset", pattern="^(offset|cursor)$"),
        cursor: str | None = None,
        principal: GatewayPrincipal = Depends(_get_gateway_principal),
    ) -> list[GatewayToolDefinitionResponse] | GatewayToolListPageResponse:
        """List active Tool Gateway contracts callable by the authenticated agent."""

        with _audit_database().transaction() as connection:
            repository = ToolRegistryRepository(
                connection,
                principal.organization_id,
                principal.environment_id,
            )
            if pagination == "cursor" or cursor is not None:
                try:
                    decoded_cursor = (
                        decode_gateway_tool_cursor(
                            cursor,
                            secret=resolved_settings.session_secret,
                        )
                        if cursor
                        else GatewayToolCursor(
                            snapshot_before=utc_now_iso(),
                            last_updated_at=None,
                            last_id=None,
                            owner_team=owner_team.strip() if owner_team else None,
                        )
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                normalized_owner_team = owner_team.strip() if owner_team else None
                if decoded_cursor.owner_team != normalized_owner_team:
                    raise HTTPException(
                        status_code=400,
                        detail="Discovery cursor does not match the requested owner_team filter.",
                    )
                rows = repository.list_tools_for_gateway_principal_cursor(
                    agent_id=principal.agent_id,
                    credential_id=principal.credential_id,
                    owner_team=normalized_owner_team,
                    limit=limit + 1,
                    snapshot_before=decoded_cursor.snapshot_before,
                    last_updated_at=decoded_cursor.last_updated_at,
                    last_id=decoded_cursor.last_id,
                )
                page_rows = rows[:limit]
                next_cursor = None
                if len(rows) > limit and page_rows:
                    last_row = page_rows[-1]
                    next_cursor = encode_gateway_tool_cursor(
                        GatewayToolCursor(
                            snapshot_before=decoded_cursor.snapshot_before,
                            last_updated_at=str(last_row["updated_at"]),
                            last_id=str(last_row["id"]),
                            owner_team=normalized_owner_team,
                        ),
                        secret=resolved_settings.session_secret,
                    )
                return GatewayToolListPageResponse(
                    tools=[gateway_tool_definition_response(row) for row in page_rows],
                    next_cursor=next_cursor,
                )
            return [
                gateway_tool_definition_response(row)
                for row in repository.list_tools_for_gateway_principal(
                    agent_id=principal.agent_id,
                    credential_id=principal.credential_id,
                    owner_team=owner_team,
                    limit=limit,
                    offset=offset,
                )
            ]

    @app.get(
        "/api/v1/gateway/capabilities",
        response_model=GatewayCapabilitiesResponse,
        tags=["tool-gateway"],
    )
    async def get_gateway_capabilities(
        principal: GatewayPrincipal = Depends(_get_gateway_principal),
    ) -> GatewayCapabilitiesResponse:
        """Return the authenticated SDK compatibility contract."""

        _ = principal
        return GatewayCapabilitiesResponse(
            max_payload_bytes=int(resolved_settings.tool_gateway_max_body_bytes),
            max_response_bytes=int(resolved_settings.tool_gateway_max_upstream_response_bytes),
            idempotency_in_progress_ttl_seconds=int(
                resolved_settings.tool_gateway_idempotency_in_progress_ttl_seconds
            ),
            idempotency_replay_retention_seconds=int(
                resolved_settings.tool_gateway_idempotency_replay_retention_seconds
            ),
            rate_limit_window_seconds=int(
                resolved_settings.tool_gateway_rate_limit_window_seconds
            ),
            rate_limit_max_requests=int(resolved_settings.tool_gateway_rate_limit_max_requests),
            circuit_breaker_failure_threshold=int(
                resolved_settings.tool_gateway_circuit_breaker_failure_threshold
            ),
            circuit_breaker_cooldown_seconds=int(
                resolved_settings.tool_gateway_circuit_breaker_cooldown_seconds
            ),
        )

    @app.get(
        "/api/v1/gateway/authorizations/{authorization_session_id}",
        response_model=AuthorizationStatusResponse,
        tags=["tool-gateway"],
    )
    async def get_gateway_authorization_status(
        authorization_session_id: str,
        principal: GatewayPrincipal = Depends(_get_gateway_principal),
    ) -> AuthorizationStatusResponse:
        """Return one delegated authorization session visible to this gateway credential."""

        repository = ToolDelegationRepository(
            _audit_database().connect(),
            principal.organization_id,
            principal.environment_id,
        )
        row = repository.get_authorization_session(
            authorization_session_id,
            agent_id=principal.agent_id,
            credential_id=principal.credential_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Authorization session not found.")
        return authorization_session_response(row)

    @app.post(
        "/api/v1/tools/{tool_name}/invoke",
        response_model=ToolInvocationResponse,
        tags=["tool-gateway"],
    )
    async def invoke_tool_gateway_tool(
        tool_name: str,
        body: ToolInvocationRequest,
        request: Request,
        principal: GatewayPrincipal = Depends(_get_gateway_principal),
    ) -> ToolInvocationResponse | JSONResponse:
        """Authenticate an external agent and invoke a registered tool."""

        context = _request_context_from_request(request)
        correlation_id = body.correlation_id or context.correlation_id
        idempotency_key = _tool_gateway_idempotency_key(request, body)
        idempotency_record_id: str | None = None
        try:
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(
                    connection,
                    principal.organization_id,
                    principal.environment_id,
                )
                decision = ToolPolicyDecisionService(
                    connection,
                    principal.organization_id,
                    principal.environment_id,
                ).evaluate_tool_call(
                    principal,
                    tool_name,
                    body.payload,
                    request_id=context.request_id,
                    correlation_id=correlation_id,
                )
                runtime_repository = ToolRuntimeActionRepository(
                    connection,
                    principal.organization_id,
                    principal.environment_id,
                )
                if decision.decision in {"deny", "pending_authorization", "require_approval"}:
                    pending_authorization = decision.decision == "pending_authorization"
                    pending_approval = decision.decision == "require_approval"
                    action_status = (
                        "authorization_pending"
                        if pending_authorization
                        else "approval_required"
                        if pending_approval
                        else "denied"
                    )
                    runtime_action = runtime_repository.create_action(
                        ToolRuntimeActionCreate(
                            request_id=context.request_id,
                            correlation_id=correlation_id,
                            **_trace_context_fields(context),
                            agent_id=principal.agent_id,
                            credential_id=principal.credential_id,
                            tool_id=decision.tool_id,
                            permission_id=decision.permission_id,
                            decision_id=decision.id,
                            action_status=action_status,
                            reason_code=decision.reason_code,
                            payload_summary=body.payload,
                            error_code=decision.reason_code,
                            delegated_user_id=decision.delegated_user_id,
                            provider_account_id=decision.provider_account_id,
                            delegated_authorization_id=decision.delegated_authorization_id,
                            approval_state=decision.approval_state,
                            authorization_session_id=decision.authorization_session_id,
                        )
                    )
                    event_type = (
                        "tool.runtime.authorization_pending"
                        if pending_authorization
                        else "tool.runtime.approval_required"
                        if pending_approval
                        else "tool.runtime.denied"
                    )
                    _append_tool_runtime_event(
                        runtime_repository,
                        runtime_action["id"],
                        event_type,
                        {
                            "decision_id": decision.id,
                            "reason_code": decision.reason_code,
                            "authorization_session_id": decision.authorization_session_id,
                            "delegation_id": decision.delegated_authorization_id,
                            "delegated_user_id": decision.delegated_user_id,
                            "provider_account_id": decision.provider_account_id,
                            "approval_state": decision.approval_state,
                        },
                    )
                    if pending_authorization or pending_approval:
                        error_body: dict[str, Any] = {
                            "code": decision.reason_code,
                            "message": decision.reason_message,
                        }
                        if decision.authorization_challenge is not None:
                            error_body["authorization"] = decision.authorization_challenge.model_dump()
                        return JSONResponse(
                            status_code=403,
                            content=jsonable_encoder(
                                ToolInvocationResponse(
                                    request_id=context.request_id,
                                    correlation_id=correlation_id,
                                    tool_name=tool_name,
                                    decision=_tool_invocation_decision_summary(decision),
                                    reason_code=decision.reason_code,
                                    result=None,
                                    error=error_body,
                                )
                            ),
                        )
                    return JSONResponse(
                        status_code=403,
                        content=jsonable_encoder(
                            ToolInvocationResponse(
                                request_id=context.request_id,
                                correlation_id=correlation_id,
                                tool_name=tool_name,
                                decision=None,
                                reason_code="tool_call_denied",
                                result=None,
                                error={
                                    "code": "tool_call_denied",
                                    "message": "Tool call denied by gateway policy.",
                                },
                            )
                        ),
                    )
                tool = repository.get_tool_by_name(tool_name, active_only=True)
                if tool is None:
                    raise HTTPException(status_code=404, detail="Tool not found.")
                input_schema = (
                    json.loads(tool["input_schema_json"])
                    if tool["input_schema_json"] is not None
                    else None
                )
                if input_schema is not None:
                    try:
                        validate_payload(body.payload, input_schema)
                    except ToolSchemaValidationError as exc:
                        runtime_action = runtime_repository.create_action(
                            ToolRuntimeActionCreate(
                                request_id=context.request_id,
                                correlation_id=correlation_id,
                                **_trace_context_fields(context),
                                agent_id=principal.agent_id,
                                credential_id=principal.credential_id,
                                tool_id=tool["id"],
                                permission_id=decision.permission_id,
                                decision_id=decision.id,
                                action_status="validation_failed",
                                reason_code=decision.reason_code,
                                payload_summary=body.payload,
                                error_code="schema_validation_failed",
                                delegated_user_id=principal.delegated_user_id,
                                provider_account_id=principal.delegated_provider_account_id,
                                delegated_authorization_id=principal.delegated_authorization_id,
                                approval_state=principal.approval_state,
                                authorization_session_id=principal.authorization_session_id,
                            )
                        )
                        _append_tool_runtime_event(
                            runtime_repository,
                            runtime_action["id"],
                            "tool.runtime.validation_failed",
                            {
                                "decision_id": decision.id,
                                "error_code": "schema_validation_failed",
                            },
                        )
                        return _schema_validation_error_response(request, exc)
                if idempotency_key is not None:
                    try:
                        created_idempotency_record, idempotency_record = (
                            ToolInvocationIdempotencyRepository(
                                connection,
                                principal.organization_id,
                                principal.environment_id,
                            ).begin_invocation(
                                credential_id=principal.credential_id,
                                tool_id=tool["id"],
                                idempotency_key=idempotency_key,
                                request_hash=invocation_request_hash(
                                    tool_name=tool_name,
                                    payload=body.payload,
                                ),
                                request_id=context.request_id,
                                correlation_id=correlation_id,
                                in_progress_ttl_seconds=(
                                    resolved_settings.tool_gateway_idempotency_in_progress_ttl_seconds
                                ),
                            )
                        )
                    except ToolInvocationIdempotencyConflictError:
                        return JSONResponse(
                            status_code=409,
                            content=jsonable_encoder(
                                ToolInvocationResponse(
                                    request_id=context.request_id,
                                    correlation_id=correlation_id,
                                    tool_name=tool_name,
                                    decision=None,
                                    reason_code="idempotency_conflict",
                                    result=None,
                                    error={
                                        "code": "idempotency_conflict",
                                        "message": (
                                            "Idempotency key was already used with "
                                            "different request content."
                                        ),
                                    },
                                )
                            ),
                        )
                    except ToolInvocationIdempotencyInProgressError:
                        return JSONResponse(
                            status_code=409,
                            content=jsonable_encoder(
                                ToolInvocationResponse(
                                    request_id=context.request_id,
                                    correlation_id=correlation_id,
                                    tool_name=tool_name,
                                    decision=None,
                                    reason_code="idempotency_in_progress",
                                    result=None,
                                    error={
                                        "code": "idempotency_in_progress",
                                        "message": (
                                            "An invocation with this idempotency key "
                                            "is still in progress."
                                        ),
                                    },
                                )
                            ),
                        )
                    except ToolInvocationIdempotencyStaleError:
                        return JSONResponse(
                            status_code=409,
                            content=jsonable_encoder(
                                ToolInvocationResponse(
                                    request_id=context.request_id,
                                    correlation_id=correlation_id,
                                    tool_name=tool_name,
                                    decision=None,
                                    reason_code="idempotency_stale",
                                    result=None,
                                    error={
                                        "code": "idempotency_stale",
                                        "message": (
                                            "A previous invocation with this idempotency key "
                                            "did not complete and its outcome is unknown; "
                                            "use a new idempotency key after reconciliation."
                                        ),
                                    },
                                )
                            ),
                        )
                    if not created_idempotency_record:
                        return JSONResponse(
                            status_code=int(idempotency_record["response_status_code"] or 200),
                            content=jsonable_encoder(idempotency_response_body(idempotency_record)),
                            headers={"Idempotency-Replayed": "true"},
                        )
                    idempotency_record_id = str(idempotency_record["id"])
                runtime_action = runtime_repository.create_action(
                    ToolRuntimeActionCreate(
                        request_id=context.request_id,
                        correlation_id=correlation_id,
                        **_trace_context_fields(context),
                        agent_id=principal.agent_id,
                        credential_id=principal.credential_id,
                        tool_id=tool["id"],
                        permission_id=decision.permission_id,
                        decision_id=decision.id,
                        action_status="denied" if decision.decision == "deny" else "allowed",
                        reason_code=decision.reason_code,
                        payload_summary=body.payload,
                        delegated_user_id=principal.delegated_user_id,
                        provider_account_id=principal.delegated_provider_account_id,
                        delegated_authorization_id=principal.delegated_authorization_id,
                        approval_state=principal.approval_state,
                        authorization_session_id=principal.authorization_session_id,
                    )
                )
                _append_tool_runtime_event(
                    runtime_repository,
                    runtime_action["id"],
                    "tool.runtime.allowed",
                    {
                        "decision_id": decision.id,
                        "reason_code": decision.reason_code,
                        "delegation_id": principal.delegated_authorization_id,
                        "delegated_user_id": principal.delegated_user_id,
                        "provider_account_id": principal.delegated_provider_account_id,
                        "approval_state": principal.approval_state,
                    },
                )
                runtime_action_id = str(runtime_action["id"])
                response_policy = repository.get_response_policy(tool["id"])
                upstream_target = repository.get_upstream_target_for_tool(tool["id"])

            def _update_runtime_action(
                update: ToolRuntimeActionUpdate,
                event_type: str,
                event_summary: dict[str, Any],
            ) -> None:
                with _audit_database().transaction() as update_connection:
                    update_repository = ToolRuntimeActionRepository(
                        update_connection,
                        principal.organization_id,
                        principal.environment_id,
                    )
                    update_repository.update_action(runtime_action_id, update)
                    _append_tool_runtime_event(
                        update_repository,
                        runtime_action_id,
                        event_type,
                        event_summary,
                    )

            def _store_idempotency_response(
                status_code: int,
                response_body: dict[str, Any],
                *,
                error_code: str | None = None,
            ) -> bool:
                if idempotency_record_id is None:
                    return True
                try:
                    with _audit_database().transaction() as idem_connection:
                        ToolInvocationIdempotencyRepository(
                            idem_connection,
                            principal.organization_id,
                            principal.environment_id,
                        ).complete_invocation(
                            idempotency_record_id,
                            response_status_code=status_code,
                            response_body=response_body,
                            error_code=error_code,
                        )
                except Exception:
                    LOGGER.exception(
                        "Failed to persist Tool Gateway idempotency response.",
                        extra={
                            "idempotency_record_id": idempotency_record_id,
                            "request_id": context.request_id,
                            "correlation_id": correlation_id,
                            "tool_name": tool_name,
                        },
                    )
                    return False
                return True

            def _idempotency_persistence_failure_response(
                *,
                status_code: int = 503,
            ) -> JSONResponse:
                return JSONResponse(
                    status_code=status_code,
                    content=jsonable_encoder(
                        ToolInvocationResponse(
                            request_id=context.request_id,
                            correlation_id=correlation_id,
                            tool_name=tool_name,
                            decision=_tool_invocation_decision_summary(decision),
                            reason_code="idempotency_persistence_failed",
                            result=None,
                            error={
                                "code": "idempotency_persistence_failed",
                                "message": (
                                    "Tool execution completed, but the gateway could not "
                                    "persist the idempotency replay record; the outcome is "
                                    "unknown for retries. Reconcile the upstream operation "
                                    "before using a new idempotency key."
                                ),
                            },
                        )
                    ),
                    headers={"Idempotency-Persistence": "failed"},
                )

            executor = getattr(app.state, "tool_gateway_executor", None)
            if executor is None:
                circuit_breaker = getattr(app.state, "tool_gateway_circuit_breaker", None)
                if circuit_breaker is None:
                    circuit_breaker = DatabaseToolGatewayCircuitBreaker(
                        _audit_database(),
                        failure_threshold=int(
                            resolved_settings.tool_gateway_circuit_breaker_failure_threshold
                        ),
                        cooldown_seconds=float(
                            resolved_settings.tool_gateway_circuit_breaker_cooldown_seconds
                        ),
                    )
                    app.state.tool_gateway_circuit_breaker = circuit_breaker
                executor = AsyncHttpToolInvocationExecutor(
                    _PreloadedToolUpstreamTargetRepository(upstream_target),
                    http_client=getattr(app.state, "tool_gateway_http_client", None),
                    secret_provider=_secret_provider(),
                    max_response_bytes=int(
                        resolved_settings.tool_gateway_max_upstream_response_bytes
                    ),
                    allowed_upstream_hosts=resolved_settings.tool_gateway_upstream_host_allowlist,
                    circuit_breaker=circuit_breaker,
                )
            try:
                maybe_execution = executor.execute(
                    tool=tool,
                    payload=body.payload,
                    decision=decision,
                    principal=principal,
                )
                execution = (
                    await maybe_execution
                    if inspect.isawaitable(maybe_execution)
                    else maybe_execution
                )
            except ToolExecutionError as exc:
                safe_message = safe_agent_error_message(exc.message)
                _update_runtime_action(
                    ToolRuntimeActionUpdate(
                        action_status="upstream_failed",
                        error_code=exc.code,
                        response_summary={"error": safe_message},
                    ),
                    "tool.runtime.upstream_failed",
                    {"error_code": exc.code},
                )
                response_body = jsonable_encoder(
                    ToolInvocationResponse(
                        request_id=context.request_id,
                        correlation_id=correlation_id,
                        tool_name=tool_name,
                        decision=_tool_invocation_decision_summary(decision),
                        reason_code=decision.reason_code,
                        result=None,
                        error={"code": exc.code, "message": safe_message},
                    )
                )
                if not _store_idempotency_response(
                    exc.status_code,
                    response_body,
                    error_code=exc.code,
                ):
                    return _idempotency_persistence_failure_response()
                return JSONResponse(
                    status_code=exc.status_code,
                    content=response_body,
                )
            except Exception:
                _update_runtime_action(
                    ToolRuntimeActionUpdate(
                        action_status="upstream_failed",
                        error_code="executor_error",
                        response_summary={"error": "Tool executor failed."},
                    ),
                    "tool.runtime.upstream_failed",
                    {"error_code": "executor_error"},
                )
                response_body = jsonable_encoder(
                    ToolInvocationResponse(
                        request_id=context.request_id,
                        correlation_id=correlation_id,
                        tool_name=tool_name,
                        decision=_tool_invocation_decision_summary(decision),
                        reason_code=decision.reason_code,
                        result=None,
                        error={
                            "code": "executor_error",
                            "message": "Tool executor failed.",
                        },
                    )
                )
                if not _store_idempotency_response(
                    502,
                    response_body,
                    error_code="executor_error",
                ):
                    return _idempotency_persistence_failure_response()
                return JSONResponse(
                    status_code=502,
                    content=response_body,
                )

            _update_runtime_action(
                ToolRuntimeActionUpdate(
                    action_status="forwarded",
                    upstream_status_code=execution.upstream_status_code
                    if isinstance(execution, ToolExecutionResult)
                    else None,
                    latency_ms=execution.latency_ms
                    if isinstance(execution, ToolExecutionResult)
                    else None,
                ),
                "tool.runtime.forwarded",
                {
                    "upstream_status_code": execution.upstream_status_code
                    if isinstance(execution, ToolExecutionResult)
                    else None,
                },
            )
            if isinstance(execution, ToolExecutionResult):
                try:
                    if response_policy is not None:
                        execution = process_tool_execution_response(tool, response_policy, execution)
                except ToolExecutionError as exc:
                    _update_runtime_action(
                        ToolRuntimeActionUpdate(
                            action_status="response_blocked",
                            upstream_status_code=execution.upstream_status_code,
                            latency_ms=execution.latency_ms,
                            response_summary=_runtime_response_summary(
                                execution,
                                store_full_response=_response_policy_store_full_response(
                                    response_policy
                                ),
                            ),
                            redaction_applied=execution.redaction_applied,
                            error_code=exc.code,
                        ),
                        "tool.runtime.response_blocked",
                        {"error_code": exc.code},
                    )
                    response_body = jsonable_encoder(
                        ToolInvocationResponse(
                            request_id=context.request_id,
                            correlation_id=correlation_id,
                            tool_name=tool_name,
                            decision=_tool_invocation_decision_summary(decision),
                            reason_code=decision.reason_code,
                            result=None,
                            error={
                                "code": exc.code,
                                "message": safe_agent_error_message(exc.message),
                            },
                        )
                    )
                    if not _store_idempotency_response(
                        exc.status_code,
                        response_body,
                        error_code=exc.code,
                    ):
                        return _idempotency_persistence_failure_response()
                    return JSONResponse(
                        status_code=exc.status_code,
                        content=response_body,
                    )
            result = execution.model_dump() if isinstance(execution, ToolExecutionResult) else execution
            if isinstance(execution, ToolExecutionResult) and execution.status == "failed":
                if isinstance(result, dict):
                    result = {
                        **result,
                        "body": None,
                        "exposed_to_agent": False,
                    }
                error_code = _runtime_execution_error_code(execution)
                _update_runtime_action(
                    ToolRuntimeActionUpdate(
                        action_status="upstream_failed",
                        upstream_status_code=execution.upstream_status_code,
                        latency_ms=execution.latency_ms,
                        response_summary=_runtime_response_summary(
                            execution,
                            store_full_response=_response_policy_store_full_response(
                                response_policy
                            ),
                        ),
                        redaction_applied=execution.redaction_applied,
                        error_code=error_code,
                    ),
                    "tool.runtime.upstream_failed",
                    {"error_code": error_code},
                )
                response_body = jsonable_encoder(
                    ToolInvocationResponse(
                        request_id=context.request_id,
                        correlation_id=correlation_id,
                        tool_name=tool_name,
                        decision=_tool_invocation_decision_summary(decision),
                        reason_code=decision.reason_code,
                        result=None,
                        error=_tool_execution_error_body(execution.error),
                    )
                )
                if not _store_idempotency_response(502, response_body, error_code=error_code):
                    return _idempotency_persistence_failure_response()
                return JSONResponse(
                    status_code=502,
                    content=response_body,
                )
            _update_runtime_action(
                ToolRuntimeActionUpdate(
                    action_status="completed",
                    upstream_status_code=execution.upstream_status_code
                    if isinstance(execution, ToolExecutionResult)
                    else None,
                    latency_ms=execution.latency_ms
                    if isinstance(execution, ToolExecutionResult)
                    else None,
                    response_summary=_runtime_response_summary(
                        execution,
                        store_full_response=_response_policy_store_full_response(response_policy),
                    ),
                    redaction_applied=execution.redaction_applied
                    if isinstance(execution, ToolExecutionResult)
                    else False,
                ),
                "tool.runtime.completed",
                {
                    "upstream_status_code": execution.upstream_status_code
                    if isinstance(execution, ToolExecutionResult)
                    else None,
                },
            )
            response_model = ToolInvocationResponse(
                request_id=context.request_id,
                correlation_id=correlation_id,
                tool_name=tool_name,
                decision=_tool_invocation_decision_summary(decision),
                reason_code=decision.reason_code,
                result=result,
                error=None,
            )
            if not _store_idempotency_response(200, jsonable_encoder(response_model)):
                return _idempotency_persistence_failure_response()
            return response_model
        except ToolSchemaValidationError as exc:
            return _schema_validation_error_response(request, exc)

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
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.TENANT_MANAGE)),
    ) -> Environment:
        """Create an environment in the current organization."""

        if current_user.organization_id is None:
            raise HTTPException(status_code=400, detail="Organization context is required.")
        environment = tenants.create_environment(
            organization_id=current_user.organization_id,
            name=body.name,
            slug=body.slug,
            environment_type=body.type,
        )
        _record_admin_settings_audit_event(
            request=request,
            principal=current_user,
            event_type="admin.environment.created",
            resource_type="environment",
            resource_id=environment.id,
            payload_json={
                "environment_id": environment.id,
                "name": environment.name,
                "slug": environment.slug,
                "type": environment.type,
            },
        )
        return environment

    @app.post("/api/v1/api-keys", response_model=ApiKeyCreateResponse, status_code=201, tags=["auth"])
    async def create_api_key(
        body: ApiKeyCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.API_KEYS_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ApiKeyCreateResponse:
        """Create a scoped API key and return its one-time secret."""

        if current_user.organization_id is None:
            raise HTTPException(status_code=400, detail="Organization context is required.")
        try:
            delegated_scopes = validate_delegated_api_key_scopes(current_user, body.scopes)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        environment_ids = _api_key_environment_scope(
            body.environment_ids,
            organization_id=current_user.organization_id,
            selected_environment_id=environment_id,
        )
        expires_at = _api_key_expiration(body.expires_at)
        if use_persistent_api_keys:
            with _audit_database().transaction() as connection:
                record, secret = _api_key_store(connection).create_key(
                    organization_id=current_user.organization_id,
                    name=body.name,
                    scopes=delegated_scopes,
                    kind=body.kind,
                    environment_ids=environment_ids,
                    expires_at=expires_at,
                    created_by=current_user.id,
                )
                _record_admin_settings_audit_event(
                    request=request,
                    principal=current_user,
                    event_type="admin.api_key.created",
                    resource_type="api_key",
                    resource_id=record.id,
                    payload_json={
                        "key_id": record.id,
                        "name": record.name,
                        "kind": record.kind,
                        "scopes": list(record.scopes),
                        "environment_ids": list(record.environment_ids),
                        "expires_at": record.expires_at,
                        "created_by": record.created_by,
                    },
                    connection=connection,
                )
        else:
            record, secret = api_keys.create_key(
                organization_id=current_user.organization_id,
                name=body.name,
                scopes=delegated_scopes,
                kind=body.kind,
                environment_ids=environment_ids,
                expires_at=expires_at,
                created_by=current_user.id,
            )
            _record_admin_settings_audit_event(
                request=request,
                principal=current_user,
                event_type="admin.api_key.created",
                resource_type="api_key",
                resource_id=record.id,
                payload_json={
                    "key_id": record.id,
                    "name": record.name,
                    "kind": record.kind,
                    "scopes": list(record.scopes),
                    "environment_ids": list(record.environment_ids),
                    "expires_at": record.expires_at,
                    "created_by": record.created_by,
                },
            )
        return ApiKeyCreateResponse(key=record.to_response(), secret=secret)

    @app.get("/api/v1/api-keys", response_model=list[ApiKeyResponse], tags=["auth"])
    async def list_api_keys(
        current_user: UserPrincipal = Depends(require_permission(Permission.API_KEYS_MANAGE)),
    ) -> list[ApiKeyResponse]:
        """List API keys for the current organization without raw secrets."""

        if current_user.organization_id is None:
            return []
        if use_persistent_api_keys:
            with _audit_database().transaction() as connection:
                records = _api_key_store(connection).list_keys(current_user.organization_id)
        else:
            records = api_keys.list_keys(current_user.organization_id)
        return [record.to_response() for record in records]

    @app.post(
        "/api/v1/api-keys/{key_id}/rotate",
        response_model=ApiKeyRotationResponse,
        status_code=201,
        tags=["auth"],
    )
    async def rotate_api_key(
        key_id: str,
        body: ApiKeyRotateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.API_KEYS_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ApiKeyRotationResponse:
        """Create a replacement API key and atomically revoke the previous key."""

        if current_user.organization_id is None:
            raise HTTPException(status_code=404, detail="API key not found.")
        if use_persistent_api_keys:
            with _audit_database().transaction() as connection:
                previous = _api_key_store(connection).get_key(key_id, current_user.organization_id)
                if previous is None:
                    raise HTTPException(status_code=404, detail="API key not found.")
                if previous.revoked_at is not None:
                    raise HTTPException(status_code=409, detail="API key is already revoked.")
                environment_ids = _api_key_environment_scope(
                    body.environment_ids if body.environment_ids is not None else previous.environment_ids,
                    organization_id=current_user.organization_id,
                    selected_environment_id=environment_id,
                )
                rotated = _api_key_store(connection).rotate_key(
                    key_id,
                    current_user.organization_id,
                    name=body.name or previous.name,
                    environment_ids=environment_ids,
                    expires_at=_api_key_expiration(body.expires_at),
                    actor_id=current_user.id,
                    reason=_api_key_reason(body.reason, "rotated via API"),
                )
                if rotated is None:
                    raise HTTPException(status_code=409, detail="API key is already revoked.")
                revoked_record, replacement, secret = rotated
                _record_admin_settings_audit_event(
                    request=request,
                    principal=current_user,
                    event_type="admin.api_key.rotated",
                    resource_type="api_key",
                    resource_id=revoked_record.id,
                    payload_json={
                        "key_id": revoked_record.id,
                        "replacement_key_id": replacement.id,
                        "reason": revoked_record.revoked_reason,
                        "rotated_by": current_user.id,
                        "previous_expires_at": previous.expires_at,
                        "replacement_expires_at": replacement.expires_at,
                        "environment_ids": list(replacement.environment_ids),
                    },
                    connection=connection,
                )
                _record_admin_settings_audit_event(
                    request=request,
                    principal=current_user,
                    event_type="admin.api_key.revoked",
                    resource_type="api_key",
                    resource_id=revoked_record.id,
                    payload_json={
                        "key_id": revoked_record.id,
                        "reason": revoked_record.revoked_reason,
                        "revoked_by": revoked_record.revoked_by,
                        "revoked_at": revoked_record.revoked_at,
                        "rotated_to_key_id": replacement.id,
                    },
                    connection=connection,
                )
        else:
            previous = api_keys.get_key(key_id, current_user.organization_id)
            if previous is None:
                raise HTTPException(status_code=404, detail="API key not found.")
            if previous.revoked_at is not None:
                raise HTTPException(status_code=409, detail="API key is already revoked.")
            environment_ids = _api_key_environment_scope(
                body.environment_ids if body.environment_ids is not None else previous.environment_ids,
                organization_id=current_user.organization_id,
                selected_environment_id=environment_id,
            )
            rotated = api_keys.rotate_key(
                key_id,
                current_user.organization_id,
                name=body.name or previous.name,
                environment_ids=environment_ids,
                expires_at=_api_key_expiration(body.expires_at),
                actor_id=current_user.id,
                reason=_api_key_reason(body.reason, "rotated via API"),
            )
            if rotated is None:
                raise HTTPException(status_code=409, detail="API key is already revoked.")
            revoked_record, replacement, secret = rotated
            _record_admin_settings_audit_event(
                request=request,
                principal=current_user,
                event_type="admin.api_key.rotated",
                resource_type="api_key",
                resource_id=revoked_record.id,
                payload_json={
                    "key_id": revoked_record.id,
                    "replacement_key_id": replacement.id,
                    "reason": revoked_record.revoked_reason,
                    "rotated_by": current_user.id,
                    "previous_expires_at": previous.expires_at,
                    "replacement_expires_at": replacement.expires_at,
                    "environment_ids": list(replacement.environment_ids),
                },
            )
            _record_admin_settings_audit_event(
                request=request,
                principal=current_user,
                event_type="admin.api_key.revoked",
                resource_type="api_key",
                resource_id=revoked_record.id,
                payload_json={
                    "key_id": revoked_record.id,
                    "reason": revoked_record.revoked_reason,
                    "revoked_by": revoked_record.revoked_by,
                    "revoked_at": revoked_record.revoked_at,
                    "rotated_to_key_id": replacement.id,
                },
            )
        return ApiKeyRotationResponse(
            previous_key=revoked_record.to_response(),
            replacement_key=replacement.to_response(),
            secret=secret,
        )

    @app.delete("/api/v1/api-keys/{key_id}", status_code=204, tags=["auth"])
    async def revoke_api_key(
        key_id: str,
        request: Request,
        body: ApiKeyRevokeRequest | None = Body(default=None),
        current_user: UserPrincipal = Depends(require_permission(Permission.API_KEYS_MANAGE)),
    ) -> None:
        """Revoke an API key for the current organization."""

        if current_user.organization_id is None:
            raise HTTPException(status_code=404, detail="API key not found.")
        reason = _api_key_reason(body.reason if body else None, "revoked via API")
        if use_persistent_api_keys:
            with _audit_database().transaction() as connection:
                revoked_record = _api_key_store(connection).revoke_key(
                    key_id,
                    current_user.organization_id,
                    revoked_by=current_user.id,
                    revoked_reason=reason,
                )
                if revoked_record is not None:
                    _record_admin_settings_audit_event(
                        request=request,
                        principal=current_user,
                        event_type="admin.api_key.revoked",
                        resource_type="api_key",
                        resource_id=key_id,
                        payload_json={
                            "key_id": key_id,
                            "reason": revoked_record.revoked_reason,
                            "revoked_by": revoked_record.revoked_by,
                            "revoked_at": revoked_record.revoked_at,
                        },
                        connection=connection,
                    )
        else:
            revoked_record = api_keys.revoke_key(
                key_id,
                current_user.organization_id,
                revoked_by=current_user.id,
                revoked_reason=reason,
            )
            if revoked_record is not None:
                _record_admin_settings_audit_event(
                    request=request,
                    principal=current_user,
                    event_type="admin.api_key.revoked",
                    resource_type="api_key",
                    resource_id=key_id,
                    payload_json={
                        "key_id": key_id,
                        "reason": revoked_record.revoked_reason,
                        "revoked_by": revoked_record.revoked_by,
                        "revoked_at": revoked_record.revoked_at,
                    },
                )
        if revoked_record is None:
            raise HTTPException(status_code=404, detail="API key not found.")

    @app.post("/api/v1/audit/events", response_model=AuditEventEnvelope, status_code=201, tags=["audit"])
    async def create_audit_event(
        event: AuditEventEnvelope,
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AuditEventEnvelope:
        """Persist a canonical audit event."""

        organization_id = _require_organization_id(current_user)
        if event.organization_id != organization_id or event.environment_id != environment_id:
            raise HTTPException(status_code=403, detail="Organization access is denied.")
        payload_json = dict(event.payload_json)
        payload_json.setdefault("_submitted_event_id", event.id)
        payload_json.setdefault("_submitted_source_component", event.source_component)
        payload_json.setdefault("_submitted_actor_type", event.actor_type)
        if event.actor_id is not None:
            payload_json.setdefault("_submitted_actor_id", event.actor_id)
        canonical_event = AuditEventEnvelope(
            organization_id=organization_id,
            environment_id=environment_id,
            event_type=event.event_type,
            source_component="external-api",
            actor_type="user",
            actor_id=current_user.id,
            agent_id=event.agent_id,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            decision=event.decision,
            severity=event.severity,
            correlation_id=event.correlation_id,
            trace_id=event.trace_id,
            policy_id=event.policy_id,
            policy_version_id=event.policy_version_id,
            trust_delta=event.trust_delta,
            payload_json=payload_json,
        )
        database_for_audit = _audit_database()
        with database_for_audit.transaction() as connection:
            return AuditEventRepository(connection).insert(canonical_event)

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
        environment_id: str = Depends(require_environment_context),
    ) -> list[AuditEventEnvelope]:
        """List audit events for the selected environment."""

        if current_user.organization_id is None:
            return []
        return AuditEventRepository(_audit_database().connect()).query(
            AuditEventQuery(
                organization_id=current_user.organization_id,
                environment_id=environment_id,
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
        environment_id: str = Depends(require_environment_context),
    ) -> AuditExportResponse:
        """Persist audit export metadata for compliance evidence workflows."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            try:
                audit_repository = AuditEventRepository(connection)
                event_set = collect_audit_export_events(
                    audit_repository=audit_repository,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    filters=body.filters,
                )
                checkpoint = audit_repository.create_checkpoint(
                    organization_id,
                    environment_id=environment_id,
                    created_by=current_user.id,
                    scope={
                        "purpose": "audit_export",
                        "filters": event_set.filters,
                        "complete": event_set.complete,
                    },
                    signing_key=settings.session_secret,
                )
                chain_proof = audit_repository.export_chain_proof(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_ids=[event.id for event in event_set.events],
                    checkpoint=checkpoint,
                )
                linked_runtime_actions = audit_export_runtime_links(
                    connection=connection,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    events=event_set.events,
                )
                chain_proof["linked_runtime_actions"] = linked_runtime_actions
                chain_proof["linked_artifacts"] = audit_export_linked_artifacts(
                    connection=connection,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    runtime_links=linked_runtime_actions,
                )
                row = AuditExportRepository(connection, organization_id, environment_id).create(
                    AuditExportRequest(format=body.format, filters=event_set.filters),
                    actor_id=current_user.id,
                    event_count=len(event_set.events),
                    complete=event_set.complete,
                    completeness_reason=event_set.completeness_reason,
                    chain_proof=chain_proof,
                )
                response = audit_export_response(row)
                content_type, content = audit_export_content(
                    response=response,
                    events=event_set.events,
                )
            except AuditExportValidationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            _create_generated_artifact(
                connection=connection,
                organization_id=organization_id,
                environment_id=environment_id,
                artifact_type="audit.export",
                name=f"{row['id']}.{row['format']}",
                content_type=content_type,
                content=content,
                actor_id=current_user.id,
                target_type="audit_export",
                target_id=row["id"],
                link_type="export",
            )
            return response

    @app.get("/api/v1/audit/events/stream", tags=["audit"])
    async def stream_audit_events(
        event_type: str | None = None,
        last_event_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> StreamingResponse:
        """Stream current audit events for the selected environment as server-sent events."""

        if current_user.organization_id is None:
            events = []
        else:
            events = AuditEventRepository(_audit_database().connect()).stream_events(
                organization_id=current_user.organization_id,
                environment_id=environment_id,
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
        environment_id: str = Depends(require_environment_context),
    ) -> AuditEventEnvelope:
        """Get a single audit event in the selected environment."""

        if current_user.organization_id is None:
            raise HTTPException(status_code=404, detail="Audit event not found.")
        event = AuditEventRepository(_audit_database().connect()).get(
            event_id, current_user.organization_id, environment_id=environment_id
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
        "/api/v1/policy-evaluations/summary",
        response_model=PolicyEvaluationSummaryResponse,
        tags=["policies"],
    )
    async def get_policy_evaluation_summary(
        decision: str | None = None,
        mode: str | None = None,
        agent_id: str | None = None,
        action: str | None = None,
        policy_id: str | None = None,
        correlation_id: str | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> PolicyEvaluationSummaryResponse:
        """Return aggregate policy evaluation counts for the selected environment."""

        organization_id = _require_organization_id(current_user)
        return PolicyEvaluationRepository(_audit_database().connect()).summary(
            PolicyEvaluationQuery(
                organization_id=organization_id,
                environment_id=environment_id,
                decision=decision,
                mode=mode,
                agent_id=agent_id,
                action=action,
                policy_id=policy_id,
                correlation_id=correlation_id,
            )
        )

    @app.get("/api/v1/policy-evaluations/stream", tags=["policies"])
    async def stream_policy_evaluations(
        request: Request,
        decision: str | None = None,
        mode: str | None = None,
        agent_id: str | None = None,
        action: str | None = None,
        policy_id: str | None = None,
        correlation_id: str | None = None,
        environment_query_id: str | None = Query(default=None, alias="environment_id"),
        last_event_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        current_user: UserPrincipal = Depends(require_permission(Permission.POLICY_READ)),
    ) -> StreamingResponse:
        """Stream current policy evaluation rows as server-sent events."""

        organization_id = _require_organization_id(current_user)
        environment_id = _resolve_policy_evaluation_stream_environment(
            request=request,
            organization_id=organization_id,
            environment_id=environment_query_id,
        )
        rows = PolicyEvaluationRepository(_audit_database().connect()).stream(
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
            ),
            last_event_id=last_event_id,
        )

        def body() -> Any:
            for row in rows:
                yield _format_policy_evaluation_sse_event(policy_evaluation_response(row))

        return StreamingResponse(body(), media_type="text/event-stream")

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
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ComplianceReportResponse:
        """Generate report content from current evidence and violations."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = ComplianceRepository(connection, organization_id, environment_id)
                row = repository.generate_report(report_id, actor_id=current_user.id)
                _create_generated_artifact(
                    connection=connection,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    artifact_type="compliance.report",
                    name=f"{row['id']}.md",
                    content_type="text/markdown",
                    content=str(row["rendered_markdown"] or "").encode("utf-8"),
                    actor_id=current_user.id,
                    target_type="compliance_report",
                    target_id=row["id"],
                    link_type="report",
                )
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
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
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
        "/api/v1/trust/handshakes/challenges",
        response_model=TrustHandshakeChallengeResponse,
        status_code=201,
        tags=["trust"],
    )
    async def issue_trust_handshake_challenge(
        body: TrustHandshakeChallengeRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> TrustHandshakeChallengeResponse:
        """Issue a canonical server challenge for a signed trust handshake."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = TrustRepository(connection, organization_id, environment_id)
                challenge = TrustHandshakeService(repository).issue_challenge(body)
                AuditEventRepository(connection).insert(
                    _trust_handshake_challenge_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        challenge=challenge,
                        correlation_id=context.correlation_id,
                    )
                )
                return challenge
        except TrustAgentNotOperationalError as exc:
            with _audit_database().transaction() as connection:
                AuditEventRepository(connection).insert(
                    _trust_handshake_blocked_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        body=TrustHandshakeRequest(
                            source_agent_id=body.source_agent_id,
                            target_agent_id=body.target_agent_id,
                            purpose=body.purpose,
                            threshold_type=body.threshold_type,
                            target_type=body.target_type,
                            target_id=body.target_id,
                            metadata=body.metadata,
                        ),
                        reason=str(exc),
                        reason_code=exc.reason_code,
                        correlation_id=context.correlation_id,
                    )
                )
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except TrustAgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
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
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
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
        except TrustAgentNotOperationalError as exc:
            with _audit_database().transaction() as connection:
                AuditEventRepository(connection).insert(
                    _trust_handshake_blocked_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        body=body,
                        reason=str(exc),
                        reason_code=exc.reason_code,
                        correlation_id=context.correlation_id,
                    )
                )
            raise HTTPException(status_code=409, detail=str(exc)) from exc
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
        except TrustAgentNotOperationalError as exc:
            with _audit_database().transaction() as connection:
                AuditEventRepository(connection).insert(
                    _trust_handshake_blocked_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        body=body,
                        reason=str(exc),
                        reason_code=exc.reason_code,
                        correlation_id=context.correlation_id,
                    )
                )
            raise HTTPException(status_code=409, detail=str(exc)) from exc
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
                policy = _mesh_policy_decision(
                    connection=connection,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    actor_id=current_user.id,
                    source_agent_id=body.source_agent_id,
                    target_agent_id=body.target_agent_id,
                    action=body.action,
                    resource_type="mesh_message",
                    resource_id=body.target_agent_id,
                    context={
                        "protocol": body.protocol,
                        "latency_ms": body.latency_ms,
                        "payload_summary": body.payload_summary,
                    },
                    correlation_id=context.correlation_id,
                )
                threshold_type = "mcp_tool_use" if body.protocol.lower() == "mcp" else "handoff"
                trust = _mesh_trust_decision(
                    connection=connection,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    source_agent_id=body.source_agent_id,
                    target_agent_id=body.target_agent_id,
                    threshold_type=threshold_type,
                )
                policy_decision = _policy_decision_name(policy)
                client_decision = body.decision.lower()
                client_restrictive = client_decision in {"deny", "denied", "blocked"}
                server_decision = (
                    "deny"
                    if policy_decision == "deny"
                    or trust["decision"] == "deny"
                    or client_restrictive
                    else policy_decision
                )
                server_body = body.model_copy(
                    update={
                        "decision": server_decision,
                        "payload_summary": {
                            **body.payload_summary,
                            "server_decision": _server_mesh_decision_evidence(
                                policy=policy,
                                trust=trust,
                                client_supplied={
                                    "decision": body.decision,
                                    "restrictive_signal": client_restrictive,
                                },
                            ),
                        },
                    }
                )
                message = mesh_message_response(
                    MeshRepository(connection, organization_id, environment_id).create_message(server_body)
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
        except MeshAgentNotOperationalError as exc:
            with _audit_database().transaction() as connection:
                AuditEventRepository(connection).insert(
                    _mesh_blocked_attempt_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="mesh.message.blocked",
                        source_agent_id=body.source_agent_id,
                        target_agent_id=body.target_agent_id,
                        resource_type="mesh_message",
                        reason=str(exc),
                        correlation_id=context.correlation_id,
                        payload_json={
                            "protocol": body.protocol,
                            "action": body.action,
                            "client_supplied_decision": body.decision,
                        },
                    )
                )
            raise HTTPException(status_code=409, detail=str(exc)) from exc
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
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> MeshHandoffResponse:
        """Ingest a mesh handoff attempt from an SDK or adapter."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                policy = _mesh_policy_decision(
                    connection=connection,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    actor_id=current_user.id,
                    source_agent_id=body.source_agent_id,
                    target_agent_id=body.target_agent_id,
                    action=body.task_type,
                    resource_type="mesh_handoff",
                    resource_id=body.target_agent_id,
                    context={
                        "task_type": body.task_type,
                        "required_capabilities": body.required_capabilities,
                        "metadata": body.metadata,
                    },
                    correlation_id=context.correlation_id,
                )
                trust = _mesh_trust_decision(
                    connection=connection,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    source_agent_id=body.source_agent_id,
                    target_agent_id=body.target_agent_id,
                    threshold_type="handoff",
                )
                policy_decision = _policy_decision_name(policy)
                client_policy_result = body.policy_result.lower()
                client_status = body.status.lower()
                client_restrictive = client_policy_result in {"deny", "denied", "blocked"} or client_status in {
                    "blocked",
                    "denied",
                }
                policy_result = (
                    "deny"
                    if policy_decision == "deny" or client_restrictive
                    else policy_decision
                )
                trust_result = "allowed" if trust["decision"] == "allow" else "denied"
                status = "accepted"
                reason = "trust_and_policy_satisfied"
                if policy_result == "deny":
                    status = "blocked"
                    reason = policy.reason if policy_decision == "deny" else (body.reason or "client_restrictive_signal")
                elif trust_result == "denied":
                    status = "blocked"
                    reason = trust["reason"]
                elif policy_result == "requires_approval":
                    status = "requires_approval"
                    reason = policy.reason
                server_body = body.model_copy(
                    update={
                        "trust_result": trust_result,
                        "policy_result": policy_result,
                        "status": status,
                        "reason": reason,
                        "metadata": {
                            **body.metadata,
                            "server_decision": _server_mesh_decision_evidence(
                                policy=policy,
                                trust=trust,
                                client_supplied={
                                    "trust_result": body.trust_result,
                                    "policy_result": body.policy_result,
                                    "status": body.status,
                                    "reason": body.reason,
                                    "restrictive_signal": client_restrictive,
                                },
                            ),
                        },
                    }
                )
                handoff = mesh_handoff_response(
                    MeshRepository(connection, organization_id, environment_id).create_handoff(server_body)
                )
                if handoff.status.lower() in {"blocked", "denied", "requires_approval", "escalated"}:
                    AuditEventRepository(connection).insert(
                        _mesh_handoff_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            handoff=handoff,
                            correlation_id=context.correlation_id,
                        )
                    )
                return handoff
        except MeshAgentNotOperationalError as exc:
            with _audit_database().transaction() as connection:
                AuditEventRepository(connection).insert(
                    _mesh_blocked_attempt_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="mesh.handoff.blocked",
                        source_agent_id=body.source_agent_id,
                        target_agent_id=body.target_agent_id,
                        resource_type="mesh_handoff",
                        reason=str(exc),
                        correlation_id=context.correlation_id,
                        payload_json={
                            "task_type": body.task_type,
                            "client_supplied_policy_result": body.policy_result,
                            "client_supplied_trust_result": body.trust_result,
                        },
                    )
                )
            raise HTTPException(status_code=409, detail=str(exc)) from exc
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
        "/api/v1/tools",
        response_model=ToolDefinitionResponse,
        status_code=201,
        tags=["tool-gateway"],
    )
    async def create_tool_definition(
        body: ToolDefinitionCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolDefinitionResponse | JSONResponse:
        """Create a tenant-scoped Tool Gateway contract."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                row = repository.create_tool(body, created_by=current_user.id)
                tool = tool_definition_response(repository, row, include_versions=True)
                AuditEventRepository(connection).insert(
                    _tool_definition_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="tool.definition.created",
                        tool=tool,
                        correlation_id=context.correlation_id,
                    )
                )
                return tool
        except DuplicateToolNameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ToolSchemaValidationError as exc:
            return _schema_validation_error_response(request, exc)

    @app.get(
        "/api/v1/tools",
        response_model=list[ToolDefinitionResponse],
        tags=["tool-gateway"],
    )
    async def list_tool_definitions(
        status: str | None = None,
        owner_team: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ToolDefinitionResponse]:
        """List tenant-scoped Tool Gateway contracts."""

        organization_id = _require_organization_id(current_user)
        try:
            repository = ToolRegistryRepository(
                _audit_database().connect(),
                organization_id,
                environment_id,
            )
            return [
                tool_definition_response(repository, row)
                for row in repository.list_tools(
                    status=status,
                    owner_team=owner_team,
                    limit=limit,
                    offset=offset,
                )
            ]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get(
        "/api/v1/tools/{tool_id}",
        response_model=ToolDefinitionResponse,
        tags=["tool-gateway"],
    )
    async def get_tool_definition(
        tool_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolDefinitionResponse:
        """Get one Tool Gateway contract with version history."""

        organization_id = _require_organization_id(current_user)
        repository = ToolRegistryRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        row = repository.get_tool(tool_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Tool definition not found.")
        return tool_definition_response(repository, row, include_versions=True)

    @app.patch(
        "/api/v1/tools/{tool_id}",
        response_model=ToolDefinitionResponse,
        tags=["tool-gateway"],
    )
    async def patch_tool_definition(
        tool_id: str,
        body: ToolDefinitionPatchRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolDefinitionResponse | JSONResponse:
        """Patch a Tool Gateway contract and version contract changes."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                row = repository.update_tool(tool_id, body, updated_by=current_user.id)
                tool = tool_definition_response(repository, row, include_versions=True)
                AuditEventRepository(connection).insert(
                    _tool_definition_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="tool.definition.updated",
                        tool=tool,
                        correlation_id=context.correlation_id,
                    )
                )
                return tool
        except ToolDefinitionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ToolSchemaValidationError as exc:
            return _schema_validation_error_response(request, exc)

    @app.post(
        "/api/v1/tools/{tool_id}/activate",
        response_model=ToolDefinitionResponse,
        tags=["tool-gateway"],
    )
    async def activate_tool_definition(
        tool_id: str,
        request: Request,
        body: ToolLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolDefinitionResponse | JSONResponse:
        """Activate a Tool Gateway contract after schema validation."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                existing = repository.get_tool(tool_id)
                if existing is None:
                    raise ToolDefinitionNotFoundError("Tool definition not found.")
                row = repository.activate_tool(
                    tool_id,
                    actor_id=current_user.id,
                    reason=body.reason if body else None,
                )
                tool = tool_definition_response(repository, row, include_versions=True)
                AuditEventRepository(connection).insert(
                    _tool_definition_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="tool.definition.activated",
                        tool=tool,
                        previous_status=existing["status"],
                        reason=body.reason if body else None,
                        correlation_id=context.correlation_id,
                    )
                )
                return tool
        except ToolDefinitionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ToolLifecycleError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ToolSchemaValidationError as exc:
            return _schema_validation_error_response(request, exc)

    @app.post(
        "/api/v1/tools/{tool_id}/disable",
        response_model=ToolDefinitionResponse,
        tags=["tool-gateway"],
    )
    async def disable_tool_definition(
        tool_id: str,
        request: Request,
        body: ToolLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolDefinitionResponse:
        """Disable a Tool Gateway contract without removing version history."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                existing = repository.get_tool(tool_id)
                if existing is None:
                    raise ToolDefinitionNotFoundError("Tool definition not found.")
                row = repository.disable_tool(
                    tool_id,
                    actor_id=current_user.id,
                    reason=body.reason if body else None,
                )
                tool = tool_definition_response(repository, row, include_versions=True)
                AuditEventRepository(connection).insert(
                    _tool_definition_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="tool.definition.disabled",
                        tool=tool,
                        previous_status=existing["status"],
                        reason=body.reason if body else None,
                        correlation_id=context.correlation_id,
                    )
                )
                return tool
        except ToolDefinitionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/tools/{tool_id}/versions",
        response_model=list[ToolDefinitionVersionResponse],
        tags=["tool-gateway"],
    )
    async def list_tool_definition_versions(
        tool_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ToolDefinitionVersionResponse]:
        """List version history for a Tool Gateway contract."""

        organization_id = _require_organization_id(current_user)
        repository = ToolRegistryRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        try:
            return [
                tool_definition_version_response(row)
                for row in repository.list_versions(tool_id)
            ]
        except ToolDefinitionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/tool-runtime/actions",
        response_model=list[ToolRuntimeActionResponse],
        tags=["tool-gateway"],
    )
    async def list_tool_runtime_actions(
        decision_id: str | None = None,
        correlation_id: str | None = None,
        action_status: str | None = None,
        agent_id: str | None = None,
        tool_id: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ToolRuntimeActionResponse]:
        """List Tool Gateway runtime actions in tenant/environment scope."""

        organization_id = _require_organization_id(current_user)
        try:
            query = ToolRuntimeActionQuery(
                decision_id=decision_id,
                correlation_id=correlation_id,
                action_status=action_status,
                agent_id=agent_id,
                tool_id=tool_id,
                created_from=created_from,
                created_to=created_to,
                limit=limit,
                offset=offset,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        repository = ToolRuntimeActionRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        return [tool_runtime_action_response(row) for row in repository.list_actions(query)]

    @app.get(
        "/api/v1/tool-runtime/actions/{action_id}",
        response_model=ToolRuntimeActionDetailResponse,
        tags=["tool-gateway"],
    )
    async def get_tool_runtime_action(
        action_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolRuntimeActionDetailResponse:
        """Get one Tool Gateway runtime action with event timeline."""

        organization_id = _require_organization_id(current_user)
        repository = ToolRuntimeActionRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        detail = repository.get_action_detail(action_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Tool runtime action not found.")
        return tool_runtime_action_detail_response(detail)

    @app.get(
        "/api/v1/tools/{tool_id}/response-policy",
        response_model=ToolResponsePolicyResponse,
        tags=["tool-gateway"],
    )
    async def get_tool_response_policy(
        tool_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolResponsePolicyResponse:
        """Get response handling policy for a tool."""

        organization_id = _require_organization_id(current_user)
        repository = ToolRegistryRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        try:
            row = repository.get_response_policy(tool_id)
        except ToolDefinitionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if row is None:
            raise HTTPException(status_code=404, detail="Response policy not found.")
        return tool_response_policy_response(row)

    @app.patch(
        "/api/v1/tools/{tool_id}/response-policy",
        response_model=ToolResponsePolicyResponse,
        tags=["tool-gateway"],
    )
    async def patch_tool_response_policy(
        tool_id: str,
        body: ToolResponsePolicyPatchRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolResponsePolicyResponse:
        """Patch response handling policy for a tool."""

        if (
            body.status == "disabled"
            and not _is_local_environment(resolved_settings.environment)
            and not _bool_env("OPHANIX_ALLOW_DISABLED_TOOL_RESPONSE_POLICY", False)
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Disabling Tool Gateway response policy is blocked outside local/test "
                    "environments unless OPHANIX_ALLOW_DISABLED_TOOL_RESPONSE_POLICY=true."
                ),
            )
        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                row = repository.update_response_policy(tool_id, body)
                return tool_response_policy_response(row)
        except ToolDefinitionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/agents/{agent_id}/tool-permissions",
        response_model=AgentToolPermissionResponse,
        status_code=201,
        tags=["tool-gateway"],
    )
    async def grant_agent_tool_permission(
        agent_id: str,
        body: AgentToolPermissionGrantRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentToolPermissionResponse:
        """Grant an active agent access to an active tool."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                row = repository.grant_agent_tool_permission(
                    agent_id,
                    body,
                    granted_by=current_user.id,
                )
                permission = agent_tool_permission_response(row)
                AuditEventRepository(connection).insert(
                    _agent_tool_permission_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="agent_tool_permission.granted",
                        permission=permission,
                        correlation_id=context.correlation_id,
                        reason=body.granted_reason or None,
                    )
                )
                return permission
        except DuplicateAgentToolPermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except AgentToolPermissionValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/agents/{agent_id}/tool-permissions",
        response_model=list[AgentToolPermissionResponse],
        tags=["tool-gateway"],
    )
    async def list_agent_tool_permissions_for_agent(
        agent_id: str,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[AgentToolPermissionResponse]:
        """List tool permissions granted to one agent."""

        organization_id = _require_organization_id(current_user)
        repository = ToolRegistryRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        try:
            return [
                agent_tool_permission_response(row)
                for row in repository.list_agent_tool_permissions(
                    agent_id=agent_id,
                    status=status,
                    limit=limit,
                    offset=offset,
                )
            ]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get(
        "/api/v1/tools/{tool_id}/agent-permissions",
        response_model=list[AgentToolPermissionResponse],
        tags=["tool-gateway"],
    )
    async def list_agent_tool_permissions_for_tool(
        tool_id: str,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[AgentToolPermissionResponse]:
        """List agents allowed to call one tool."""

        organization_id = _require_organization_id(current_user)
        repository = ToolRegistryRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        if repository.get_tool(tool_id) is None:
            raise HTTPException(status_code=404, detail="Tool definition not found.")
        try:
            return [
                agent_tool_permission_response(row)
                for row in repository.list_agent_tool_permissions(
                    tool_id=tool_id,
                    status=status,
                    limit=limit,
                    offset=offset,
                )
            ]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.patch(
        "/api/v1/agent-tool-permissions/{permission_id}",
        response_model=AgentToolPermissionResponse,
        tags=["tool-gateway"],
    )
    async def patch_agent_tool_permission(
        permission_id: str,
        body: AgentToolPermissionPatchRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentToolPermissionResponse:
        """Patch an agent-tool permission scope or expiration."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                row = repository.update_agent_tool_permission(
                    permission_id,
                    body,
                    actor_id=current_user.id,
                )
                permission = agent_tool_permission_response(row)
                AuditEventRepository(connection).insert(
                    _agent_tool_permission_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="agent_tool_permission.updated",
                        permission=permission,
                        correlation_id=context.correlation_id,
                    )
                )
                return permission
        except AgentToolPermissionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/agent-tool-permissions/{permission_id}/pause",
        response_model=AgentToolPermissionResponse,
        tags=["tool-gateway"],
    )
    async def pause_agent_tool_permission(
        permission_id: str,
        body: AgentToolPermissionActionRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentToolPermissionResponse:
        """Pause an agent-tool permission with a required reason."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                row = repository.pause_agent_tool_permission(
                    permission_id,
                    actor_id=current_user.id,
                    reason=body.reason,
                )
                permission = agent_tool_permission_response(row)
                AuditEventRepository(connection).insert(
                    _agent_tool_permission_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="agent_tool_permission.paused",
                        permission=permission,
                        correlation_id=context.correlation_id,
                        reason=body.reason,
                    )
                )
                return permission
        except AgentToolPermissionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/agent-tool-permissions/{permission_id}/revoke",
        response_model=AgentToolPermissionResponse,
        tags=["tool-gateway"],
    )
    async def revoke_agent_tool_permission(
        permission_id: str,
        body: AgentToolPermissionActionRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentToolPermissionResponse:
        """Revoke an agent-tool permission with a required reason."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                row = repository.revoke_agent_tool_permission(
                    permission_id,
                    actor_id=current_user.id,
                    reason=body.reason,
                )
                permission = agent_tool_permission_response(row)
                AuditEventRepository(connection).insert(
                    _agent_tool_permission_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="agent_tool_permission.revoked",
                        permission=permission,
                        correlation_id=context.correlation_id,
                        reason=body.reason,
                    )
                )
                return permission
        except AgentToolPermissionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/tools/{tool_id}/upstream-target",
        response_model=ToolUpstreamTargetResponse,
        status_code=201,
        tags=["tool-gateway"],
    )
    async def create_tool_upstream_target(
        tool_id: str,
        body: ToolUpstreamTargetCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolUpstreamTargetResponse:
        """Create an upstream target for a registered tool."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            _validate_upstream_target_host_allowed(body.base_url, resolved_settings)
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                row = repository.create_upstream_target(tool_id, body)
                target = tool_upstream_target_response(repository, row)
                AuditEventRepository(connection).insert(
                    _tool_upstream_target_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="tool.upstream_target.created",
                        target=target,
                        correlation_id=context.correlation_id,
                    )
                )
                return target
        except ToolDefinitionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DuplicateToolUpstreamTargetError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ToolUpstreamTargetValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/v1/tools/{tool_id}/upstream-target",
        response_model=ToolUpstreamTargetResponse,
        tags=["tool-gateway"],
    )
    async def get_tool_upstream_target(
        tool_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolUpstreamTargetResponse:
        """Get the active upstream target for a registered tool."""

        organization_id = _require_organization_id(current_user)
        repository = ToolRegistryRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        if repository.get_tool(tool_id) is None:
            raise HTTPException(status_code=404, detail="Tool definition not found.")
        row = repository.get_upstream_target_for_tool(tool_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Upstream target not found.")
        return tool_upstream_target_response(repository, row)

    @app.patch(
        "/api/v1/tool-upstream-targets/{target_id}",
        response_model=ToolUpstreamTargetResponse,
        tags=["tool-gateway"],
    )
    async def patch_tool_upstream_target(
        target_id: str,
        body: ToolUpstreamTargetPatchRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolUpstreamTargetResponse:
        """Patch upstream target settings or health-check configuration."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            if body.base_url is not None:
                _validate_upstream_target_host_allowed(body.base_url, resolved_settings)
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                row = repository.update_upstream_target(target_id, body)
                target = tool_upstream_target_response(repository, row)
                AuditEventRepository(connection).insert(
                    _tool_upstream_target_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="tool.upstream_target.updated",
                        target=target,
                        correlation_id=context.correlation_id,
                    )
                )
                return target
        except ToolUpstreamTargetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DuplicateToolUpstreamTargetError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ToolUpstreamTargetValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/tool-upstream-targets/{target_id}/check-health",
        response_model=ToolUpstreamHealthResponse,
        tags=["tool-gateway"],
    )
    async def check_tool_upstream_target_health(
        target_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolUpstreamHealthResponse:
        """Run and persist a manual upstream health check."""

        organization_id = _require_organization_id(current_user)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolRegistryRepository(connection, organization_id, environment_id)
                return await ToolUpstreamHealthChecker(
                    repository,
                    http_client=getattr(app.state, "tool_gateway_http_client", None),
                ).check_target_async(target_id)
        except ToolUpstreamTargetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/tool-upstream-targets/{target_id}/health",
        response_model=ToolUpstreamHealthResponse,
        tags=["tool-gateway"],
    )
    async def get_tool_upstream_target_health(
        target_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> ToolUpstreamHealthResponse:
        """Return persisted upstream health-check state."""

        organization_id = _require_organization_id(current_user)
        repository = ToolRegistryRepository(
            _audit_database().connect(),
            organization_id,
            environment_id,
        )
        row = repository.get_upstream_health(target_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Upstream health not found.")
        return tool_upstream_health_response(row)

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
                raw_tools = select_mcp_tool_discovery_adapter(
                    server,
                    environment=settings.environment,
                ).discover_tools(server)
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
                    repository.refresh_server_scan_gate_state(server_id)
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
                repository = MCPProxyRepository(
                    connection,
                    organization_id,
                    environment_id,
                    runtime_environment=settings.environment,
                )
                row = MCPProxyDecisionService(
                    repository,
                    runtime_environment=settings.environment,
                ).evaluate_and_record(
                    body,
                    request_correlation_id=context.correlation_id,
                    **_trace_context_fields(context),
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
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
            release_error: str | None = None
            response: MCPApprovalResponse
            with _audit_database().transaction() as connection:
                repository = MCPProxyRepository(
                    connection,
                    organization_id,
                    environment_id,
                    runtime_environment=settings.environment,
                )
                row = repository.decide_approval(
                    approval_id,
                    status="approved",
                    actor_id=current_user.id,
                    reason=body.reason,
                    idempotency_key=body.idempotency_key,
                )
                call_row = repository.get_tool_call(row["tool_call_id"])
                response = mcp_approval_response(
                    row,
                    tool_call=mcp_tool_call_response(call_row) if call_row is not None else None,
                )
                event_type = {
                    "approved": "mcp.approval.approved",
                    "expired": "mcp.approval.expired",
                    "denied": "mcp.approval.release_denied",
                }.get(response.status, "mcp.approval.release_failed")
                AuditEventRepository(connection).insert(
                    _mcp_approval_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type=event_type,
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
                if response.status != "approved":
                    release_error = (
                        response.release_error
                        or response.decision_reason
                        or "MCP approval could not be released."
                    )
            if release_error is not None:
                raise MCPApprovalDecisionError(release_error)
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
                repository = MCPProxyRepository(
                    connection,
                    organization_id,
                    environment_id,
                    runtime_environment=settings.environment,
                )
                row = repository.decide_approval(
                    approval_id,
                    status="denied",
                    actor_id=current_user.id,
                    reason=body.reason,
                    idempotency_key=body.idempotency_key,
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
        except TrustCardAgentNotOperationalError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
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
                terminal_event = {
                    "succeeded": "discovery.scan.completed",
                    "skipped": "discovery.scan.skipped",
                }.get(completed["status"], "discovery.scan.failed")
                audit.insert(
                    _discovery_scan_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type=terminal_event,
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
        environment_id: str = Depends(require_environment_context),
    ) -> AuditVerificationResult:
        """Verify one audit event hash in the selected environment."""

        if current_user.organization_id is None:
            raise HTTPException(status_code=404, detail="Audit event not found.")
        return AuditEventRepository(_audit_database().connect()).verify_event(
            event_id, current_user.organization_id, environment_id=environment_id
        )

    @app.post(
        "/api/v1/audit/verify-range",
        response_model=AuditVerificationResult,
        tags=["audit"],
    )
    async def verify_audit_range(
        current_user: UserPrincipal = Depends(require_permission(Permission.AUDIT_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> AuditVerificationResult:
        """Verify the selected environment's audit hash chain."""

        if current_user.organization_id is None:
            return AuditVerificationResult(valid=True, checked_count=0)
        return AuditEventRepository(_audit_database().connect()).verify_range(
            current_user.organization_id,
            environment_id=environment_id,
        )

    @app.post("/api/v1/jobs", response_model=JobResponse, status_code=201, tags=["jobs"])
    async def create_job(
        body: JobCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> JobResponse:
        """Create a background job in the selected environment."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        database_for_jobs = _audit_database()
        with database_for_jobs.transaction() as connection:
            jobs = JobStateRepository(connection)
            audit = AuditEventRepository(connection)
            try:
                created = jobs.create_job(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    job_type=body.job_type,
                    queue_name=body.queue_name,
                    priority=body.priority,
                    concurrency_key=body.concurrency_key,
                    idempotency_key=body.idempotency_key,
                    operation_type=body.operation_type,
                    operation_id=body.operation_id,
                    payload=body.payload,
                    max_attempts=body.max_attempts,
                    **_trace_context_fields(context),
                )
            except JobIdempotencyConflictError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
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
                    running = jobs.mark_running(created["id"])
                    completed = jobs.mark_succeeded(
                        created["id"],
                        expected_attempt=int(running["attempts"]),
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
                    running = jobs.mark_running(created["id"])
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
                            expected_attempt=int(running["attempts"]),
                            error_message=completed_run["error_message"]
                            or "Discovery scan failed.",
                            logs=["queued", "started discovery.scan", "failed discovery.scan"],
                        )
                    else:
                        completed = jobs.mark_succeeded(
                            created["id"],
                            expected_attempt=int(running["attempts"]),
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
                session = runtime_session_response(
                    repository.create_session(
                        body,
                        actor_user_id=current_user.id,
                        **_trace_context_fields(context),
                    )
                )
                repository.ensure_session_run(
                    session.id,
                    run_type="session",
                    started_by_user_id=current_user.id,
                    correlation_id=context.correlation_id,
                    metadata={"source": "runtime.session"},
                )
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

    @app.get(
        "/api/v1/runtime/sessions/{session_id}/runs",
        response_model=list[RuntimeRunResponse],
        tags=["runtime"],
    )
    async def list_runtime_session_runs(
        session_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[RuntimeRunResponse]:
        """List runtime runs and steps for one session."""

        organization_id = _require_organization_id(current_user)
        repository = RuntimeRepository(_audit_database().connect(), organization_id, environment_id)
        if repository.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Runtime session not found.")
        responses = []
        for run_row in repository.list_runs_for_session(session_id):
            steps = [
                runtime_run_step_response(step_row)
                for step_row in repository.list_steps_for_run(run_row["id"])
            ]
            responses.append(runtime_run_response(run_row, steps=steps))
        return responses

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
                    **_trace_context_fields(context),
                )
                decision = runtime_ring_decision_response(decision_row)
                action = runtime_action_response(action_row, ring_decision=decision)
                run = repository.ensure_session_run(
                    session_id,
                    run_type="session",
                    started_by_user_id=current_user.id,
                    correlation_id=context.correlation_id,
                    metadata={"source": "runtime.action"},
                )
                repository.create_run_step(
                    run["id"],
                    session_id=session_id,
                    step_type="runtime_action",
                    name=action.action_name,
                    status=action.decision,
                    runtime_action_id=action.id,
                    policy_decision_id=decision.id,
                    trace_id=action.trace_id,
                    span_id=action.span_id,
                    parent_span_id=action.parent_span_id,
                    correlation_id=action.correlation_id,
                    metadata={"resource_type": action.resource_type},
                )
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
        owned_runtime_session_id: str | None = None
        saga_run_id: str | None = None
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
                recovering = saga_row["status"] in SAGA_RECOVERABLE_STATUSES
                if saga_row["status"] not in SAGA_EXECUTABLE_STATUSES | SAGA_RECOVERABLE_STATUSES:
                    raise SagaExecutionError(f"Saga cannot be executed from status: {saga_row['status']}.")

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
                        ),
                        actor_user_id=current_user.id,
                        **_trace_context_fields(context),
                    )
                    session = runtime_session_response(session_row)
                    owned_runtime_session_id = session.id
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

                linked_runtime_session_id = body.runtime_session_id or saga_repository.get_saga(saga_id)["runtime_session_id"]
                saga_run = runtime_repository.ensure_session_run(
                    linked_runtime_session_id,
                    run_type="saga",
                    source_type="saga",
                    source_id=saga_id,
                    started_by_user_id=current_user.id,
                    correlation_id=context.correlation_id,
                    metadata={"source": "saga.execute"},
                )
                saga_run_id = saga_run["id"]
                linked_saga = _saga_detail_response(saga_repository, saga_id)
                audit_repository.insert(
                    _saga_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="saga.recovered" if recovering else "saga.started",
                        saga=linked_saga,
                        correlation_id=context.correlation_id,
                        payload={
                            "failure_actions": body.failure_actions,
                            "recovered_from_status": saga_row["status"] if recovering else None,
                        },
                        decision="allow",
                    )
                )

            try:
                result = await SagaExecutionService(
                    SagaRepository(_audit_database().connect(), organization_id, environment_id),
                    action_runner=WorkerBackedSagaActionRunner(
                        transaction_factory=_audit_database().transaction,
                        failure_actions=body.failure_actions,
                    ),
                    transaction_factory=_audit_database().transaction,
                ).execute(saga_id)
            except Exception:
                if owned_runtime_session_id is not None:
                    with _audit_database().transaction() as connection:
                        _archive_runtime_session_if_active(
                            repository=RuntimeRepository(connection, organization_id, environment_id),
                            audit_repository=AuditEventRepository(connection),
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            session_id=owned_runtime_session_id,
                            reason="Saga execution aborted.",
                            correlation_id=context.correlation_id,
                        )
                raise

            with _audit_database().transaction() as connection:
                saga_repository = SagaRepository(connection, organization_id, environment_id)
                runtime_repository = RuntimeRepository(connection, organization_id, environment_id)
                audit_repository = AuditEventRepository(connection)
                final_saga = _saga_detail_response(saga_repository, saga_id)
                if owned_runtime_session_id is not None:
                    _archive_runtime_session_if_active(
                        repository=runtime_repository,
                        audit_repository=audit_repository,
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        session_id=owned_runtime_session_id,
                        reason=f"Saga execution ended with status: {result.status}.",
                        correlation_id=context.correlation_id,
                    )

                step_event_by_status = {
                    "committed": "saga.step.committed",
                    "failed": "saga.step.failed",
                    "compensated": "saga.step.compensated",
                    "compensation_failed": "saga.step.compensation_failed",
                }
                for step in final_saga.steps:
                    if final_saga.runtime_session_id:
                        if saga_run_id is None:
                            saga_run = runtime_repository.ensure_session_run(
                                final_saga.runtime_session_id,
                                run_type="saga",
                                source_type="saga",
                                source_id=final_saga.id,
                                started_by_user_id=current_user.id,
                                correlation_id=context.correlation_id,
                                metadata={"source": "saga.execute"},
                            )
                            saga_run_id = saga_run["id"]
                        checkpoint = saga_repository.get_checkpoint(step.id, "execute")
                        runtime_repository.create_run_step(
                            saga_run_id,
                            session_id=final_saga.runtime_session_id,
                            step_type="saga_step",
                            name=step.name,
                            status=step.status,
                            saga_id=final_saga.id,
                            saga_step_id=step.id,
                            checkpoint_id=checkpoint["id"] if checkpoint is not None else None,
                            trace_id=context.trace_id,
                            span_id=context.span_id,
                            parent_span_id=context.parent_span_id,
                            correlation_id=context.correlation_id or final_saga.correlation_id,
                            metadata={
                                "action_name": step.action_name,
                                "required_capability": step.required_capability,
                                "worker_job_id": step.result.get("worker_job_id"),
                                "idempotency_key": step.result.get("idempotency_key"),
                                "external_operation_id": step.result.get("external_operation_id"),
                            },
                        )
                    event_type = step_event_by_status.get(step.status)
                    if event_type is None:
                        continue
                    if step.id in result.replayed_step_ids:
                        audit_repository.insert(
                            _saga_audit_event(
                                organization_id=organization_id,
                                environment_id=environment_id,
                                actor_id=current_user.id,
                                event_type="saga.activity.replayed",
                                saga=final_saga,
                                correlation_id=context.correlation_id,
                                payload={
                                    "step_id": step.id,
                                    "step_order": step.step_order,
                                    "action_name": step.action_name,
                                },
                                decision="allow",
                            )
                        )
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

                for saga_event in final_saga.events:
                    if saga_event.event_type not in {"saga.checkpoint.created", "saga.checkpoint.restored"}:
                        continue
                    audit_repository.insert(
                        _saga_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            event_type=saga_event.event_type,
                            saga=final_saga,
                            correlation_id=context.correlation_id,
                            payload={
                                "saga_event_id": saga_event.id,
                                "step_id": saga_event.step_id,
                                **saga_event.payload,
                            },
                            decision="allow",
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
                            "replayed_step_ids": result.replayed_step_ids,
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
                    replayed_step_ids=result.replayed_step_ids,
                    failed_step_id=result.failed_step_id,
                    saga=final_saga,
                )
        except SagaNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeSessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (RuntimeAgentNotActiveError, SagaExecutionError, SagaStateTransitionError, SagaStepValidationError) as exc:
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
        try:
            with _audit_database().transaction() as connection:
                saga_repository = SagaRepository(connection, organization_id, environment_id)
                runtime_repository = RuntimeRepository(connection, organization_id, environment_id)
                audit_repository = AuditEventRepository(connection)
                saga_row = saga_repository.get_saga(saga_id)
                if saga_row is None:
                    raise SagaNotFoundError("Saga not found.")
                if saga_row["status"] in SAGA_TERMINAL_STATUSES:
                    raise SagaExecutionError("Terminal saga cannot be cancelled.")
                saga_repository.update_saga_status(
                    saga_id,
                    "cancelled",
                    mark_finished=True,
                    expected_statuses=set(SAGA_EXECUTABLE_STATUSES) | {"running", "compensating"},
                )
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
        except (RuntimeSessionStateError, SagaExecutionError, SagaStateTransitionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/jobs", response_model=list[JobResponse], tags=["jobs"])
    async def list_jobs(
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[JobResponse]:
        """List background jobs for the current organization."""

        organization_id = _require_organization_id(current_user)
        if status is not None and status not in JobStatus.ALL:
            raise HTTPException(status_code=422, detail="Unsupported job status filter.")
        jobs = JobStateRepository(_audit_database().connect())
        return [
            job_response(row, jobs.runs_for_job(row["id"]))
            for row in jobs.list_jobs(
                organization_id,
                environment_id=environment_id,
                status=status,
                limit=limit,
                offset=offset,
            )
        ]

    @app.get("/api/v1/jobs/{job_id}", response_model=JobResponse, tags=["jobs"])
    async def get_job(
        job_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> JobResponse:
        """Get one background job and its run attempts."""

        organization_id = _require_organization_id(current_user)
        jobs = JobStateRepository(_audit_database().connect())
        row = jobs.get_job_for_org(job_id, organization_id, environment_id=environment_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return job_response(row, jobs.runs_for_job(job_id))

    @app.post("/api/v1/jobs/{job_id}/cancel", response_model=JobResponse, tags=["jobs"])
    async def cancel_job(
        job_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_CANCEL)),
        environment_id: str = Depends(require_environment_context),
    ) -> JobResponse:
        """Cancel a queued background job."""

        organization_id = _require_organization_id(current_user)
        database_for_jobs = _audit_database()
        with database_for_jobs.transaction() as connection:
            jobs = JobStateRepository(connection)
            row = jobs.get_job_for_org(job_id, organization_id, environment_id=environment_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Job not found.")
            try:
                canceled = jobs.cancel(
                    job_id,
                    organization_id=organization_id,
                    environment_id=environment_id,
                )
            except JobStateConflictError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
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

    @app.post("/api/v1/jobs/{job_id}/replay", response_model=JobResponse, tags=["jobs"])
    async def replay_job(
        job_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.JOB_RUN)),
        environment_id: str = Depends(require_environment_context),
    ) -> JobResponse:
        """Replay a failed or dead-lettered background job."""

        organization_id = _require_organization_id(current_user)
        database_for_jobs = _audit_database()
        with database_for_jobs.transaction() as connection:
            jobs = JobStateRepository(connection)
            row = jobs.get_job_for_org(job_id, organization_id, environment_id=environment_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Job not found.")
            try:
                replayed = jobs.replay(
                    job_id,
                    organization_id=organization_id,
                    environment_id=environment_id,
                )
            except JobStateConflictError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            _insert_job_audit_event(
                AuditEventRepository(connection),
                organization_id=organization_id,
                environment_id=replayed["environment_id"],
                job_id=replayed["id"],
                job_type=replayed["job_type"],
                status=replayed["status"],
            )
            return job_response(replayed, jobs.runs_for_job(job_id))

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
        environment_id: str = Depends(require_environment_context),
    ) -> list[JobScheduleResponse]:
        """List recurring background job schedules for the current organization."""

        organization_id = _require_organization_id(current_user)
        schedules = JobScheduleRepository(_audit_database().connect()).list_schedules(
            organization_id,
            environment_id=environment_id,
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
        environment_id: str = Depends(require_environment_context),
    ) -> JobScheduleResponse:
        """Patch schedule enablement and next-run controls."""

        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            schedules = JobScheduleRepository(connection)
            schedule = schedules.update_schedule(
                schedule_id,
                organization_id,
                environment_id=environment_id,
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
                if body.capabilities:
                    agents.replace_capabilities(
                        row["id"],
                        body.capabilities,
                        requested_by=current_user.id,
                    )
                if body.policy_selections:
                    agents.replace_policy_selections(row["id"], body.policy_selections)
                AuditEventRepository(connection).insert(
                    _agent_registration_audit_event(
                        row=row,
                        actor_id=current_user.id,
                        event_type="agent.registration_draft.created",
                        correlation_id=context.correlation_id,
                    )
                )
                return agent_registration_draft_response(
                    row,
                    capabilities=agents.list_capabilities(row["id"]),
                    policy_selections=agents.list_policy_selections(row["id"]),
                )
        except DuplicateAgentNameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentRegistrationSimulationResponse:
        """Simulate the first requested draft capability against selected policies."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            agents = AgentRegistryRepository(connection, organization_id, environment_id)
            draft = agents.get(draft_id)
            if draft is None or draft["status"] != "draft":
                raise HTTPException(status_code=404, detail="Registration draft not found.")
            capabilities = [
                row["capability_name"] for row in agents.list_capabilities(draft_id)
            ]
            policy_ids = [
                row["policy_id"] for row in agents.list_policy_selections(draft_id)
            ]
            simulation = simulate_registration_action(
                agent_id=draft_id,
                capability_names=capabilities,
                policy_ids=policy_ids,
            )
            _record_agent_registration_policy_evaluation(
                connection=connection,
                organization_id=organization_id,
                environment_id=environment_id,
                simulation=simulation,
                capability_names=capabilities,
                policy_ids=policy_ids,
                correlation_id=context.correlation_id,
            )
            return simulation

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
        request: Request,
        body: AgentIdentityProofRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentIdentityCreateResponse:
        """Create an AgentMesh identity for a draft and return bootstrap material once."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
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
                    environment_id=environment_id,
                    proof=body,
                )
                row = agents.create_identity(draft_id, created)
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="agent.identity.verified",
                        source_component="agent-registry",
                        actor_type="user",
                        actor_id=current_user.id,
                        agent_id=draft_id,
                        resource_type="agent_identity",
                        resource_id=row["id"],
                        correlation_id=context.correlation_id,
                        payload_json={
                            "proof_type": row["proof_type"],
                            "issuer": row["issuer"],
                            "audience": row["audience"],
                            "trusted_root_id": row["trusted_root_id"],
                            "trusted_root_version": row["trusted_root_version"],
                            "identity_status": row["identity_status"],
                        },
                    )
                )
                return AgentIdentityCreateResponse(
                    identity=agent_identity_response(row),
                    bootstrap=created.bootstrap,
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/agents/{agent_id}/identity/rotate",
        response_model=AgentIdentityCreateResponse,
        tags=["agents"],
    )
    async def rotate_agent_identity(
        agent_id: str,
        request: Request,
        body: AgentIdentityRotationRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentIdentityCreateResponse:
        """Rotate an agent workload identity and persist historical evidence."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                agents = AgentRegistryRepository(connection, organization_id, environment_id)
                agent = agents.get(agent_id)
                if agent is None:
                    raise AgentNotFoundError("Agent not found.")
                created = AgentIdentityAdapter().create_identity(
                    name=agent["name"],
                    sponsor_email=_resolve_sponsor_email(agent, current_user, connection),
                    organization=organization_id,
                    description=agent["description"],
                    environment_id=environment_id,
                    proof=body.proof,
                )
                row = agents.rotate_identity(
                    agent_id,
                    created,
                    actor_id=current_user.id,
                    reason=body.reason,
                )
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="agent.identity.rotated",
                        source_component="agent-registry",
                        actor_type="user",
                        actor_id=current_user.id,
                        agent_id=agent_id,
                        resource_type="agent_identity",
                        resource_id=row["id"],
                        correlation_id=context.correlation_id,
                        payload_json={
                            "reason": body.reason,
                            "did": row["did"],
                            "public_key_fingerprint": row["public_key_fingerprint"],
                            "trusted_root_id": row["trusted_root_id"],
                            "trusted_root_version": row["trusted_root_version"],
                            "rotation_count": row["rotation_count"],
                        },
                    )
                )
                return AgentIdentityCreateResponse(
                    identity=agent_identity_response(row),
                    bootstrap=created.bootstrap,
                )
        except AgentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        request: Request,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentRegistrationDraftResponse:
        """Activate an approved agent and queue initial credential issuance."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
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
                    **_trace_context_fields(context),
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

    def _transition_agent_lifecycle_status(
        *,
        agent_id: str,
        next_status: str,
        reason: str,
        request: Request,
        current_user: UserPrincipal,
        environment_id: str,
    ) -> AgentInventorySummary:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = AgentRegistryRepository(connection, organization_id, environment_id)
                existing = repository.get(agent_id)
                if existing is None:
                    raise AgentNotFoundError("Agent not found.")
                row = repository.transition_status(
                    agent_id,
                    next_status=next_status,
                    actor_id=current_user.id,
                    reason=reason,
                    metadata_json=json.dumps(
                        {
                            "action": next_status,
                            "decision": "allow",
                            "reason": reason,
                        },
                        sort_keys=True,
                    ),
                )
                cascade = AgentCredentialRepository(
                    connection,
                    organization_id,
                    environment_id,
                ).cascade_agent_lifecycle_status(
                    agent_id=agent_id,
                    next_status=next_status,
                    actor_id=current_user.id,
                    reason=reason,
                )
                invalidated_cards = []
                if not is_agent_operational(next_status):
                    invalidated_cards = TrustCardRepository(
                        connection,
                        organization_id,
                        environment_id,
                    ).invalidate_agent_cards(
                        agent_id,
                        reason=reason,
                        revoked_by=current_user.id,
                    )
                audit = AuditEventRepository(connection)
                audit.insert(
                    agent_lifecycle_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        agent_id=agent_id,
                        lifecycle_state=next_status,
                        actor_id=current_user.id,
                        previous_state=existing["status"],
                        reason=reason,
                        decision="allow",
                        correlation_id=context.correlation_id,
                    )
                )
                _insert_lifecycle_cascade_audit_events(
                    audit,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    agent_id=agent_id,
                    actor_id=current_user.id,
                    next_status=next_status,
                    reason=reason,
                    correlation_id=context.correlation_id,
                    cascade=cascade,
                )
                for card in invalidated_cards:
                    audit.insert(
                        _trust_card_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            event_type="trust.card.revoked",
                            actor_id=current_user.id,
                            card=card,
                            correlation_id=context.correlation_id,
                            payload_json={
                                "reason": reason,
                                "trigger": "agent_lifecycle",
                                "lifecycle_state": next_status,
                            },
                            decision="deny",
                        )
                    )
                return agent_inventory_summary(repository.get_inventory_summary(agent_id) or row)
        except (AgentLifecycleTransitionError, AgentNotFoundError) as exc:
            raise HTTPException(
                status_code=400 if isinstance(exc, AgentLifecycleTransitionError) else 404,
                detail=str(exc),
            ) from exc

    def _insert_lifecycle_cascade_audit_events(
        audit: AuditEventRepository,
        *,
        organization_id: str,
        environment_id: str,
        agent_id: str,
        actor_id: str,
        next_status: str,
        reason: str,
        correlation_id: str | None,
        cascade: AgentLifecycleCredentialCascadeResult,
    ) -> None:
        for credential_id in cascade.credential_ids:
            payload = {
                "credential_id": credential_id,
                "reason": reason,
                "trigger": "agent_lifecycle",
                "lifecycle_state": next_status,
            }
            audit.insert(
                _credential_audit_event(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="agent.credential.revoked",
                    actor_id=actor_id,
                    agent_id=agent_id,
                    credential_id=credential_id,
                    correlation_id=correlation_id,
                    payload_json=payload,
                )
            )
            audit.insert(
                _credential_audit_event(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="agent.credential.revocation_published",
                    actor_id=actor_id,
                    agent_id=agent_id,
                    credential_id=credential_id,
                    correlation_id=correlation_id,
                    payload_json={
                        **payload,
                        "publication_type": "lifecycle_transition",
                        "targets": ["agent-gateways", "agent-runtime"],
                    },
                )
            )
        if cascade.identity_status is not None:
            event_type = (
                "agent.identity.enabled"
                if cascade.identity_status == "active"
                else "agent.identity.disabled"
            )
            audit.insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type=event_type,
                    source_component="agent-registry",
                    actor_type="user",
                    actor_id=actor_id,
                    agent_id=agent_id,
                    resource_type="agent_identity",
                    resource_id=agent_id,
                    correlation_id=correlation_id,
                    payload_json={
                        "identity_status": cascade.identity_status,
                        "lifecycle_state": next_status,
                        "reason": reason,
                    },
                )
            )

    @app.post("/api/v1/agents/{agent_id}/restrict", response_model=AgentInventorySummary, tags=["agents"])
    async def restrict_agent(
        agent_id: str,
        request: Request,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        reason = _require_reason(body, "restrict an agent")
        return _transition_agent_lifecycle_status(
            agent_id=agent_id,
            next_status="restricted",
            reason=reason,
            request=request,
            current_user=current_user,
            environment_id=environment_id,
        )

    @app.post("/api/v1/agents/{agent_id}/quarantine", response_model=AgentInventorySummary, tags=["agents"])
    async def quarantine_agent(
        agent_id: str,
        request: Request,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        reason = _require_reason(body, "quarantine an agent")
        return _transition_agent_lifecycle_status(
            agent_id=agent_id,
            next_status="quarantined",
            reason=reason,
            request=request,
            current_user=current_user,
            environment_id=environment_id,
        )

    @app.post("/api/v1/agents/{agent_id}/revoke", response_model=AgentInventorySummary, tags=["agents"])
    async def revoke_agent_identity(
        agent_id: str,
        request: Request,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        reason = _require_reason(body, "revoke an agent")
        return _transition_agent_lifecycle_status(
            agent_id=agent_id,
            next_status="revoked",
            reason=reason,
            request=request,
            current_user=current_user,
            environment_id=environment_id,
        )

    @app.post("/api/v1/agents/{agent_id}/archive", response_model=AgentInventorySummary, tags=["agents"])
    async def archive_agent(
        agent_id: str,
        request: Request,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        reason = _require_reason(body, "archive an agent")
        return _transition_agent_lifecycle_status(
            agent_id=agent_id,
            next_status="archived",
            reason=reason,
            request=request,
            current_user=current_user,
            environment_id=environment_id,
        )

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
        request: Request,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        reason = _require_reason(body, "suspend an agent")
        return _transition_agent_lifecycle_status(
            agent_id=agent_id,
            next_status="suspended",
            reason=reason,
            request=request,
            current_user=current_user,
            environment_id=environment_id,
        )

    @app.post("/api/v1/agents/{agent_id}/resume", response_model=AgentInventorySummary, tags=["agents"])
    async def resume_agent(
        agent_id: str,
        request: Request,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        return _transition_agent_lifecycle_status(
            agent_id=agent_id,
            next_status="active",
            reason=body.reason if body else "agent resumed",
            request=request,
            current_user=current_user,
            environment_id=environment_id,
        )

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
        request: Request,
        body: AgentLifecycleActionRequest | None = None,
        current_user: UserPrincipal = Depends(require_permission(Permission.AGENT_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AgentInventorySummary:
        reason = _require_reason(body, "decommission an agent")
        _transition_agent_lifecycle_status(
            agent_id=agent_id,
            next_status="decommissioning",
            reason=reason,
            request=request,
            current_user=current_user,
            environment_id=environment_id,
        )
        return _transition_agent_lifecycle_status(
            agent_id=agent_id,
            next_status="decommissioned",
            reason=reason,
            request=request,
            current_user=current_user,
            environment_id=environment_id,
        )

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
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
    ) -> PluginResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        environment_id = context.environment_id or _default_environment_id_for_org(organization_id)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.import_plugin(body, imported_by=current_user.id)
            except MarketplaceManifestError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if body.status == "disabled":
                grants = repository.list_runtime_tool_grants_for_plugin(row["id"])
                if grants:
                    AuditEventRepository(connection).insert(
                        _plugin_runtime_tool_grants_plugin_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            plugin_id=row["id"],
                            event_type="marketplace.plugin.runtime_grants.revoked",
                            grants=grants,
                            correlation_id=context.correlation_id,
                        )
                    )
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
        "/api/v1/marketplace/plugins/{version_id}/artifact-evidence",
        response_model=PluginArtifactEvidenceResponse,
        status_code=201,
        tags=["marketplace"],
    )
    async def submit_marketplace_plugin_artifact_evidence(
        version_id: str,
        body: PluginArtifactEvidenceSubmitRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> PluginArtifactEvidenceResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.submit_artifact_evidence(version_id, body)
            except PluginNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            response = plugin_artifact_evidence_response(row)
            AuditEventRepository(connection).insert(
                _plugin_artifact_evidence_audit_event(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    actor_id=current_user.id,
                    evidence=response,
                    correlation_id=context.correlation_id,
                )
            )
            return response

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
        blocked_reason: str | None = None
        response: PluginInstallationResponse | None = None
        with _audit_database().transaction() as connection:
            repository = MarketplaceCatalogRepository(connection, organization_id)
            try:
                row = repository.create_installation(body, installed_by=current_user.id)
            except PluginInstallationBlockedError as exc:
                blocked_reason = str(exc)
                AuditEventRepository(connection).insert(
                    _plugin_installation_blocked_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        body=body,
                        reason=blocked_reason,
                        correlation_id=context.correlation_id,
                    )
                )
            except PluginInstallationStateError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except PluginNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            else:
                response = plugin_installation_response(row)
                grants = repository.list_runtime_tool_grants_for_installation(response.id)
                AuditEventRepository(connection).insert(
                    _plugin_installation_audit_event(
                        organization_id=organization_id,
                        actor_id=current_user.id,
                        event_type="marketplace.plugin.installed",
                        installation=response,
                        correlation_id=context.correlation_id,
                    )
                )
                if grants:
                    AuditEventRepository(connection).insert(
                        _plugin_runtime_tool_grants_audit_event(
                            organization_id=organization_id,
                            environment_id=environment_id,
                            actor_id=current_user.id,
                            event_type="marketplace.plugin.runtime_grants.created",
                            installation=response,
                            grants=grants,
                            correlation_id=context.correlation_id,
                        )
                    )
        if blocked_reason is not None:
            raise HTTPException(status_code=409, detail=blocked_reason)
        if response is None:
            raise HTTPException(status_code=500, detail="Plugin installation did not complete.")
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
                row = repository.uninstall(installation_id, actor_id=current_user.id)
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
            grants = repository.list_runtime_tool_grants_for_installation(response.id)
            if grants:
                AuditEventRepository(connection).insert(
                    _plugin_runtime_tool_grants_audit_event(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        actor_id=current_user.id,
                        event_type="marketplace.plugin.runtime_grants.revoked",
                        installation=response,
                        grants=grants,
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
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ProviderCredentialResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            try:
                row = repository.create_provider_credential(
                    body,
                    created_by=current_user.id,
                    secret_provider=_secret_provider(),
                )
            except ProviderCredentialSecretError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type=(
                        "integration.provider_secret.store"
                        if body.secret_value is not None
                        else "integration.provider_secret.reference_registered"
                    ),
                    source_component="provider-secrets",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="provider_credential",
                    resource_id=row["id"],
                    decision="allow",
                    correlation_id=context.correlation_id,
                    payload_json={
                        "provider_type": row["provider_type"],
                        "credential_status": row["status"],
                        "secret_source": "stored_value" if body.secret_value is not None else "external_ref",
                    },
                )
            )
            return provider_credential_response(
                row,
                reveal_secret_ref=has_permission(current_user, Permission.SECRETS_READ),
                reveal_sensitive_metadata=has_permission(current_user, Permission.SECRETS_READ),
            )

    @app.get(
        "/api/v1/integrations/provider-credentials",
        response_model=list[ProviderCredentialResponse],
        tags=["integrations"],
    )
    async def list_integration_provider_credentials(
        provider_type: str | None = Query(default=None),
        status: str | None = Query(default=None),
        include_secret_ref: bool = Query(default=False),
        current_user: UserPrincipal = Depends(require_permission(Permission.COMPLIANCE_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ProviderCredentialResponse]:
        organization_id = _require_organization_id(current_user)
        if include_secret_ref and not has_permission(current_user, Permission.SECRETS_READ):
            raise HTTPException(status_code=403, detail=f"Missing permission: {Permission.SECRETS_READ}")
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            return [
                provider_credential_response(
                    row,
                    reveal_secret_ref=include_secret_ref,
                    reveal_sensitive_metadata=include_secret_ref,
                )
                for row in repository.list_provider_credentials(provider_type=provider_type, status=status)
            ]

    @app.post(
        "/api/v1/integrations/oauth/apps",
        response_model=OAuthProviderAppResponse,
        status_code=201,
        tags=["integrations"],
    )
    async def create_oauth_provider_app(
        body: OAuthProviderAppCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> OAuthProviderAppResponse:
        """Register OAuth app metadata without exposing client secret references."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = ToolDelegationRepository(connection, organization_id, environment_id)
            row = repository.create_oauth_provider_app(body, created_by=current_user.id)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="integration.oauth_app.created",
                    source_component="provider-oauth",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="oauth_provider_app",
                    resource_id=row["id"],
                    decision="allow",
                    correlation_id=context.correlation_id,
                    payload_json={
                        "provider": row["provider"],
                        "scope_count": len(body.scopes),
                        "client_secret_ref_redacted": row["client_secret_ref"] is not None,
                    },
                )
            )
            return oauth_provider_app_response(row)

    @app.post(
        "/api/v1/integrations/oauth/authorization-sessions",
        response_model=AuthorizationStatusResponse,
        status_code=201,
        tags=["integrations"],
    )
    async def start_oauth_authorization_session(
        body: OAuthAuthorizationSessionStartRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> AuthorizationStatusResponse:
        """Start an OAuth authorization session for delegated provider consent."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolDelegationRepository(connection, organization_id, environment_id)
                row = repository.start_authorization_session(body)
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="integration.oauth_authorization.started",
                        source_component="provider-oauth",
                        actor_type="user",
                        actor_id=current_user.id,
                        agent_id=body.agent_id,
                        resource_type="oauth_authorization_session",
                        resource_id=row["id"],
                        decision="pending_authorization",
                        correlation_id=context.correlation_id,
                        payload_json={
                            "provider": row["provider"],
                            "tool_id": row["tool_id"],
                            "scope_count": len(body.required_scopes),
                            "oauth_app_id": body.oauth_app_id,
                        },
                    )
                )
                return authorization_session_response(row)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/integrations/oauth/authorization-sessions/{authorization_session_id}/complete",
        response_model=DelegatedAuthorizationResponse,
        status_code=201,
        tags=["integrations"],
    )
    async def complete_oauth_authorization_session(
        authorization_session_id: str,
        body: OAuthAuthorizationSessionCompleteRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> DelegatedAuthorizationResponse:
        """Complete an OAuth session and store only vault/environment token references."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        if body.access_token is not None or body.refresh_token is not None:
            raise HTTPException(
                status_code=422,
                detail="Raw OAuth token material is not accepted; use token references.",
            )
        try:
            with _audit_database().transaction() as connection:
                repository = ToolDelegationRepository(connection, organization_id, environment_id)
                row = repository.complete_authorization_session(authorization_session_id, body)
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="integration.oauth_authorization.completed",
                        source_component="provider-oauth",
                        actor_type="user",
                        actor_id=current_user.id,
                        agent_id=row["agent_id"],
                        resource_type="delegated_authorization",
                        resource_id=row["id"],
                        decision="allow",
                        correlation_id=context.correlation_id,
                        payload_json={
                            "provider": row["provider"],
                            "tool_id": row["tool_id"],
                            "user_id": row["user_id"],
                            "provider_account_id": row["provider_account_id"],
                            "scope_count": len(body.scopes),
                            "token_refs_redacted": True,
                        },
                    )
                )
                return delegated_authorization_response(row)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/integrations/oauth/delegated-authorizations/{authorization_id}/refresh",
        response_model=DelegatedAuthorizationResponse,
        tags=["integrations"],
    )
    async def refresh_oauth_delegated_authorization(
        authorization_id: str,
        body: OAuthDelegatedAuthorizationRefreshRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> DelegatedAuthorizationResponse:
        """Refresh delegated authorization token references without storing raw tokens."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        if body.access_token is not None or body.refresh_token is not None:
            raise HTTPException(
                status_code=422,
                detail="Raw OAuth token material is not accepted; use token references.",
            )
        try:
            with _audit_database().transaction() as connection:
                repository = ToolDelegationRepository(connection, organization_id, environment_id)
                row = repository.refresh_authorization(authorization_id, body)
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="integration.oauth_authorization.refreshed",
                        source_component="provider-oauth",
                        actor_type="user",
                        actor_id=current_user.id,
                        agent_id=row["agent_id"],
                        resource_type="delegated_authorization",
                        resource_id=row["id"],
                        decision="allow",
                        correlation_id=context.correlation_id,
                        payload_json={
                            "provider": row["provider"],
                            "tool_id": row["tool_id"],
                            "token_refs_redacted": True,
                            "expires_at": row["expires_at"],
                        },
                    )
                )
                return delegated_authorization_response(row)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/v1/integrations/oauth/delegated-authorizations/{authorization_id}/revoke",
        response_model=DelegatedAuthorizationResponse,
        tags=["integrations"],
    )
    async def revoke_oauth_delegated_authorization(
        authorization_id: str,
        body: OAuthDelegatedAuthorizationRevokeRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> DelegatedAuthorizationResponse:
        """Revoke delegated authorization so future tool calls cannot use it."""

        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        try:
            with _audit_database().transaction() as connection:
                repository = ToolDelegationRepository(connection, organization_id, environment_id)
                row = repository.revoke_authorization(authorization_id, body)
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="integration.oauth_authorization.revoked",
                        source_component="provider-oauth",
                        actor_type="user",
                        actor_id=current_user.id,
                        agent_id=row["agent_id"],
                        resource_type="delegated_authorization",
                        resource_id=row["id"],
                        decision="deny",
                        severity="warning",
                        correlation_id=context.correlation_id,
                        payload_json={
                            "provider": row["provider"],
                            "tool_id": row["tool_id"],
                            "reason": body.reason,
                        },
                    )
                )
                return delegated_authorization_response(row)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/v1/integrations/provider-credentials/{credential_id}/test",
        response_model=IntegrationHealthCheckResponse,
        status_code=201,
        tags=["integrations"],
    )
    async def test_integration_provider_credential(
        credential_id: str,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> IntegrationHealthCheckResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            try:
                credential = repository.require_provider_credential_selectable(credential_id)
            except ProviderCredentialNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Provider credential not found.") from exc
            except ProviderCredentialSelectionError as exc:
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="integration.provider_secret.retrieve",
                        source_component="provider-secrets",
                        actor_type="user",
                        actor_id=current_user.id,
                        resource_type="provider_credential",
                        resource_id=credential_id,
                        decision="deny",
                        severity="warning",
                        correlation_id=context.correlation_id,
                        payload_json={
                            "purpose": "health_check",
                            "reason": "credential_not_selectable",
                            "message": str(exc),
                        },
                    )
                )
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            try:
                secret_value = _secret_provider().retrieve(credential["secret_ref"])
            except ValueError as exc:
                AuditEventRepository(connection).insert(
                    AuditEventEnvelope(
                        organization_id=organization_id,
                        environment_id=environment_id,
                        event_type="integration.provider_secret.retrieve",
                        source_component="provider-secrets",
                        actor_type="user",
                        actor_id=current_user.id,
                        resource_type="provider_credential",
                        resource_id=credential["id"],
                        decision="deny",
                        severity="warning",
                        correlation_id=context.correlation_id,
                        payload_json={
                            "provider_type": credential["provider_type"],
                            "purpose": "health_check",
                            "reason": "invalid_secret_ref",
                            "secret_present": False,
                        },
                    )
                )
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="integration.provider_secret.retrieve",
                    source_component="provider-secrets",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="provider_credential",
                    resource_id=credential["id"],
                    decision="allow",
                    correlation_id=context.correlation_id,
                    payload_json={
                        "provider_type": credential["provider_type"],
                        "purpose": "health_check",
                        "secret_present": secret_value is not None,
                    },
                )
            )
            result = run_provider_health_test(credential["provider_type"], secret_value)
            row = repository.create_provider_credential_health_check(credential, result)
            _record_integration_health_policy_evaluation(
                connection=connection,
                organization_id=organization_id,
                environment_id=environment_id,
                health_check=row,
                credential=credential,
                correlation_id=context.correlation_id,
            )
            return integration_health_check_response(row)

    @app.post(
        "/api/v1/integrations/health-checks",
        response_model=IntegrationHealthCheckResponse,
        status_code=201,
        tags=["integrations"],
    )
    async def create_integration_health_check(
        body: IntegrationHealthCheckCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.SECURITY_MANAGE)),
        environment_id: str = Depends(require_environment_context),
    ) -> IntegrationHealthCheckResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = IntegrationRegistryRepository(connection, organization_id, environment_id)
            row = repository.create_health_check(body)
            _record_integration_health_policy_evaluation(
                connection=connection,
                organization_id=organization_id,
                environment_id=environment_id,
                health_check=row,
                correlation_id=context.correlation_id,
            )
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
            except ProviderCredentialNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ProviderCredentialSelectionError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
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
            except ProviderCredentialNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ProviderCredentialSelectionError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
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
        "/api/v1/observability/traces",
        response_model=ObservabilityTraceResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_trace(
        body: ObservabilityTraceCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ObservabilityTraceResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            row = repository.create_trace(
                body,
                created_by=current_user.id,
                correlation_id=context.correlation_id,
            )
            response = observability_trace_response(row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="observability.trace.ingested",
                    source_component="observability",
                    actor_type="user",
                    actor_id=current_user.id,
                    agent_id=response.agent_id,
                    resource_type="observability_trace",
                    resource_id=response.id,
                    decision="allow",
                    correlation_id=response.correlation_id or context.correlation_id,
                    trace_id=context.trace_id or response.trace_id,
                    payload_json=response.model_dump(),
                )
            )
            return response

    @app.get(
        "/api/v1/observability/traces",
        response_model=list[ObservabilityTraceResponse],
        tags=["observability"],
    )
    async def list_observability_traces(
        status: str | None = Query(default=None),
        agent_id: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ObservabilityTraceResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            return [
                observability_trace_response(row)
                for row in repository.list_traces(
                    status=status,
                    agent_id=agent_id,
                    limit=limit,
                    offset=offset,
                )
            ]

    @app.get(
        "/api/v1/observability/traces/{trace_id}",
        response_model=ObservabilityTraceDetailResponse,
        tags=["observability"],
    )
    async def get_observability_trace(
        trace_id: str,
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> ObservabilityTraceDetailResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            detail = repository.get_trace_detail(trace_id)
            if detail is None:
                raise HTTPException(status_code=404, detail="Trace not found.")
            return detail

    @app.post(
        "/api/v1/observability/traces/{trace_id}/spans",
        response_model=ObservabilitySpanResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_trace_span(
        trace_id: str,
        body: ObservabilitySpanCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ObservabilitySpanResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            try:
                row = repository.create_span(trace_id.strip().lower(), body)
            except ObservabilityTraceNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            response = observability_span_response(row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="observability.span.ingested",
                    source_component="observability",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="observability_span",
                    resource_id=response.id,
                    decision="allow",
                    correlation_id=context.correlation_id,
                    trace_id=context.trace_id or response.trace_id,
                    payload_json=response.model_dump(),
                )
            )
            return response

    @app.post(
        "/api/v1/observability/eval-results",
        response_model=ObservabilityEvalResultResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_eval_result(
        body: ObservabilityEvalResultCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ObservabilityEvalResultResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            row = repository.create_eval_result(body, created_by=current_user.id)
            response = observability_eval_result_response(row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="observability.eval_result.ingested",
                    source_component="observability",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="observability_eval_result",
                    resource_id=response.id,
                    decision="allow",
                    correlation_id=context.correlation_id,
                    trace_id=context.trace_id or response.trace_id,
                    payload_json=response.model_dump(),
                )
            )
            return response

    @app.get(
        "/api/v1/observability/eval-results",
        response_model=list[ObservabilityEvalResultResponse],
        tags=["observability"],
    )
    async def list_observability_eval_results(
        trace_id: str | None = Query(default=None),
        dataset_id: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=200),
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> list[ObservabilityEvalResultResponse]:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            return [
                observability_eval_result_response(row)
                for row in repository.list_eval_results(
                    trace_id=trace_id.strip().lower() if trace_id else None,
                    dataset_id=dataset_id,
                    limit=limit,
                )
            ]

    @app.post(
        "/api/v1/observability/traces/{trace_id}/annotations",
        response_model=ObservabilityTraceAnnotationResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_trace_annotation(
        trace_id: str,
        body: ObservabilityTraceAnnotationCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ObservabilityTraceAnnotationResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        normalized_trace_id = trace_id.strip().lower()
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            row = repository.create_trace_annotation(
                normalized_trace_id,
                body,
                created_by=current_user.id,
            )
            response = observability_trace_annotation_response(row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="observability.trace.annotation.created",
                    source_component="observability",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="observability_trace_annotation",
                    resource_id=response.id,
                    decision="allow",
                    correlation_id=context.correlation_id,
                    trace_id=context.trace_id or normalized_trace_id,
                    payload_json=response.model_dump(),
                )
            )
            return response

    @app.post(
        "/api/v1/observability/traces/{trace_id}/feedback",
        response_model=ObservabilityTraceFeedbackResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_trace_feedback(
        trace_id: str,
        body: ObservabilityTraceFeedbackCreateRequest,
        request: Request,
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> ObservabilityTraceFeedbackResponse:
        organization_id = _require_organization_id(current_user)
        context = _request_context_from_request(request)
        normalized_trace_id = trace_id.strip().lower()
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            row = repository.create_trace_feedback(
                normalized_trace_id,
                body,
                created_by=current_user.id,
            )
            response = observability_trace_feedback_response(row)
            AuditEventRepository(connection).insert(
                AuditEventEnvelope(
                    organization_id=organization_id,
                    environment_id=environment_id,
                    event_type="observability.trace.feedback.created",
                    source_component="observability",
                    actor_type="user",
                    actor_id=current_user.id,
                    resource_type="observability_trace_feedback",
                    resource_id=response.id,
                    decision="allow",
                    correlation_id=context.correlation_id,
                    trace_id=context.trace_id or normalized_trace_id,
                    payload_json=response.model_dump(),
                )
            )
            return response

    @app.post(
        "/api/v1/observability/slo",
        response_model=SloObjectiveResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_slo(
        body: SloObjectiveCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_READ)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_READ)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
                                source="chaos_run",
                                source_resource_type="chaos_run",
                                source_resource_id=response.id,
                            ),
                        )
                repository.create_incident(
                    IncidentCreateRequest(
                        severity="critical",
                        title=f"Chaos guardrail tripped: {experiment['name']}",
                        summary="A chaos experiment stopped because one or more guardrails were breached.",
                        correlation_id=context.correlation_id,
                        source_event_id=event.id,
                        source="chaos_run",
                        source_resource_type="chaos_run",
                        source_resource_id=response.id,
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_READ)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_READ)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_READ)),
        environment_id: str = Depends(require_environment_context),
    ) -> CostDashboardResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            return cost_dashboard_response(repository)

    @app.post(
        "/api/v1/observability/telemetry/derive",
        response_model=TelemetryDerivationResponse,
        status_code=201,
        tags=["observability"],
    )
    async def derive_observability_telemetry(
        body: TelemetryDerivationRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
        environment_id: str = Depends(require_environment_context),
    ) -> TelemetryDerivationResponse:
        organization_id = _require_organization_id(current_user)
        with _audit_database().transaction() as connection:
            repository = ObservabilityRepository(connection, organization_id, environment_id)
            result = repository.derive_telemetry_signals(body)
            return TelemetryDerivationResponse(
                slo_measurements=[
                    slo_measurement_response(row)
                    for row in result["slo_measurements"]
                ],
                cost_events=[cost_event_response(row) for row in result["cost_events"]],
                incidents=[incident_response(repository, row) for row in result["incidents"]],
                examined_tool_runtime_actions=int(result["examined_tool_runtime_actions"]),
                examined_runtime_actions=int(result["examined_runtime_actions"]),
                skipped_duplicate_cost_events=int(result["skipped_duplicate_cost_events"]),
            )

    @app.post(
        "/api/v1/observability/incidents",
        response_model=IncidentResponse,
        status_code=201,
        tags=["observability"],
    )
    async def create_observability_incident(
        body: IncidentCreateRequest,
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_READ)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.OBSERVABILITY_WRITE)),
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
        current_user: UserPrincipal = Depends(require_permission(Permission.SYSTEM_READ)),
    ) -> list[DependencyStatus]:
        """Return downstream dependency states."""

        _require_organization_id(current_user)
        dependencies = registry.check_all()
        if required_only:
            return [dependency for dependency in dependencies if dependency.required]
        return dependencies

    @app.get("/api/v1/system/not-found-probe", include_in_schema=False)
    async def not_found_probe() -> None:
        raise HTTPException(status_code=404, detail="Probe not found.")

    return app


app = create_app()
