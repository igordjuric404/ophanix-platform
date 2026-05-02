import { DEFAULT_ROUTE, LOGIN_ROUTE, findRoute, normalizePath } from "./navigation.js";
import {
  agentInventoryParamsFromForm,
  registrationPayloadFromForm,
  renderAgentInventoryTable
} from "./agents.js";
import { createApiClient } from "./apiClient.js";
import { loadAuditEventDrawer } from "./auditDrawers.js";
import {
  backDrawer,
  closeDrawer,
  drawerFromDeepLink,
  handleDrawerKeydown,
  openDrawer,
  replaceDrawerContent
} from "./drawers.js";
import { renderShell } from "./render.js";
import { demoResetPayloadFromForm } from "./demo.js";
import { discoveryFindingParamsFromForm } from "./discovery.js";
import {
  meshHandoffParamsFromForm,
  meshMessageParamsFromForm,
  protocolBridgePayloadFromForm,
  protocolBridgeRoutePayloadFromForm,
  renderMeshHandoffDetail,
  renderMeshMessageDetail
} from "./mesh.js";
import {
  mcpApprovalDecisionPayloadFromForm,
  mcpFindingActionPayloadFromForm,
  mcpFindingFilterParamsFromForm,
  mcpRateLimitPayloadFromForm,
  mcpServerPayloadFromForm,
  mcpTrafficFilterParamsFromForm,
  renderMcpFindingDetail,
  renderMcpToolDetail
} from "./mcp.js";
import {
  marketplaceInstallPayloadFromForm,
  marketplacePolicyPayloadFromForm,
  marketplaceReviewDecisionPayloadFromForm,
  marketplaceReviewSubmitPayloadFromForm,
  marketplaceSigningKeyPayloadFromForm,
  marketplaceTrustPayloadFromForm
} from "./marketplace.js";
import {
  integrationAgentLinkPayloadFromForm,
  integrationInstancePayloadFromForm,
  providerCredentialPayloadFromForm
} from "./integrations.js";
import {
  observabilityChaosExperimentPayloadFromForm,
  observabilityChaosRunPayloadFromForm,
  observabilityCostBudgetPayloadFromForm,
  observabilityCostEventPayloadFromForm,
  observabilityIncidentPayloadFromForm,
  observabilityIncidentResolvePayloadFromForm,
  observabilityRolloutAdvancePayloadFromForm,
  observabilityRolloutPayloadFromForm,
  observabilityRolloutRollbackPayloadFromForm,
  observabilitySloPayloadFromForm,
  renderIncidentDetail
} from "./observability.js";
import {
  auditEventFilterParamsFromForm,
  auditExportPayloadFromForm,
  complianceEvidenceFilterParamsFromForm,
  complianceReportAttestationPayloadFromForm,
  complianceReportPayloadFromForm,
  complianceViolationFilterParamsFromForm,
  complianceViolationPatchPayloadFromForm
} from "./compliance.js";
import {
  artifactAttestationPayloadFromForm,
  artifactUploadPayloadFromForm,
  workflowRunPayloadFromForm
} from "./workflows.js";
import {
  policyBindingPayloadFromForm,
  policyEditorPayloadFromForm,
  policyEvaluationFilterParamsFromForm,
  policyEvaluationMatchesFilters,
  policyEvaluationPayloadFromForm,
  policyExceptionPayloadFromForm,
  policyFilterParamsFromForm,
  policyImportPayloadFromForm,
  policyPromotePayloadFromForm,
  upsertPolicyEvaluationFeed
} from "./policies.js";
import {
  trustCardIssuePayloadFromForm,
  trustCardRevokePayloadFromForm,
  trustEventParamsFromForm,
  trustHandshakeParamsFromForm,
  trustHandshakePayloadFromForm,
  trustThresholdPatchPayloadFromForm,
  trustThresholdPayloadFromForm,
  renderHandshakeDetail
} from "./trust.js";
import {
  runtimeActionPayloadFromForm,
  runtimeSagaCancelPayloadFromForm,
  runtimeSagaExecutePayloadFromForm,
  runtimeSagaPayloadFromForm,
  runtimeSagaStepPayloadFromForm,
  runtimeSandboxProfilePayloadFromForm,
  runtimeSandboxTestPayloadFromForm,
  runtimeKillSwitchPayloadFromForm,
  runtimeRingRulePayloadFromForm,
  runtimeSessionPayloadFromForm,
  renderRuntimeSagaStepDetail
} from "./runtime.js";
import {
  createLoadingState,
  loadAppContext,
  loadSystemStatus,
  tenantContext,
  updateSelectedEnvironment,
  withDrawer,
  withSystemStatus
} from "./state.js";

let appState = createLoadingState();
let policyEvaluationStream = null;

function currentPath() {
  return normalizePath(window.location.pathname);
}

export function mount(root = document.getElementById("app"), state = appState) {
  if (!root) {
    throw new Error("App root element was not found.");
  }
  const path = currentPath();
  if (window.location.pathname === "/") {
    window.history.replaceState({ path: DEFAULT_ROUTE }, "", DEFAULT_ROUTE);
  }
  root.innerHTML = renderShell({ currentPath: path, state });
  root.querySelector(".content-region")?.focus();
  return root;
}

export function navigate(path, root = document.getElementById("app")) {
  const normalized = normalizePath(path);
  window.history.pushState({ path: normalized }, "", normalized);
  return mount(root, appState);
}

async function loadDiscoveryState(apiClient, selectedRunId = null) {
  const [discoveryScanners, discoveryTargets, discoveryRuns, discoveryFindings] = await Promise.all([
    apiClient.listDiscoveryScanners(),
    apiClient.listDiscoveryTargets(),
    apiClient.listDiscoveryRuns(),
    apiClient.listDiscoveryFindings()
  ]);
  const runId = selectedRunId ?? discoveryRuns[0]?.id ?? null;
  const selectedDiscoveryRun = runId ? await apiClient.getDiscoveryRun(runId) : null;
  const selectedFindingId = discoveryFindings.find((finding) => finding.status !== "suppressed")?.id ?? discoveryFindings[0]?.id ?? null;
  const selectedDiscoveryFinding = selectedFindingId
    ? await apiClient.getDiscoveryFinding(selectedFindingId)
    : null;
  return {
    ...appState,
    discoveryScanners,
    discoveryTargets,
    discoveryRuns: selectedDiscoveryRun
      ? discoveryRuns.map((run) => (run.id === selectedDiscoveryRun.id ? selectedDiscoveryRun : run))
      : discoveryRuns,
    selectedDiscoveryRun,
    discoveryFindings,
    selectedDiscoveryFinding
  };
}

async function refreshDiscoveryWorkspace(root, apiClient, selectedRunId = null) {
  appState = await loadDiscoveryState(apiClient, selectedRunId);
  mount(root, appState);
}

async function loadPolicyState(apiClient, selectedPolicyId = null) {
  const [
    policies,
    policyBindings,
    policyExceptions,
    agents,
    policyEvaluations,
    policyEvaluationSummary
  ] = await Promise.all([
    apiClient.listPolicies(),
    apiClient.listPolicyBindings(),
    apiClient.listPolicyExceptions(),
    apiClient.listAgents(),
    apiClient.listPolicyEvaluations(),
    apiClient.getPolicyEvaluationSummary()
  ]);
  const policyId = selectedPolicyId ?? policies[0]?.id ?? null;
  const selectedPolicy = policyId ? await apiClient.getPolicy(policyId) : null;
  const policyAffectedResources = policyId
    ? await apiClient.getPolicyAffectedResources(policyId)
    : null;
  return {
    ...appState,
    policies: selectedPolicy
      ? policies.map((policy) => (policy.id === selectedPolicy.id ? selectedPolicy : policy))
      : policies,
    selectedPolicy,
    policyVersions: selectedPolicy?.versions ?? [],
    policyAffectedResources,
    policyBindings,
    policyExceptions,
    policyEvaluations,
    policyEvaluationSummary,
    policyBindingTargets: { agents }
  };
}

async function refreshPolicyWorkspace(root, apiClient, selectedPolicyId = null) {
  appState = await loadPolicyState(apiClient, selectedPolicyId);
  mount(root, appState);
  startPolicyEvaluationStream(root, apiClient);
}

function stopPolicyEvaluationStream() {
  if (policyEvaluationStream?.close) {
    policyEvaluationStream.close();
  }
  policyEvaluationStream = null;
}

function startPolicyEvaluationStream(root, apiClient) {
  stopPolicyEvaluationStream();
  if (!apiClient || currentPath() !== "/policies" || typeof window.EventSource !== "function") {
    return;
  }
  const filters = appState.policyEvaluationFilter ?? {};
  const source = new window.EventSource(apiClient.policyEvaluationStreamUrl(filters));
  policyEvaluationStream = source;
  source.addEventListener("policy_evaluation", async (event) => {
    const evaluation = parsePolicyEvaluationStreamEvent(event);
    if (!evaluation || currentPath() !== "/policies") {
      return;
    }
    const activeFilters = appState.policyEvaluationFilter ?? {};
    if (policyEvaluationMatchesFilters(evaluation, activeFilters)) {
      appState = {
        ...appState,
        policyEvaluations: upsertPolicyEvaluationFeed(
          appState.policyEvaluations ?? [],
          evaluation
        )
      };
      mount(root, appState);
    }
    try {
      const [policyEvaluations, policyEvaluationSummary] = await Promise.all([
        apiClient.listPolicyEvaluations(activeFilters),
        apiClient.getPolicyEvaluationSummary(activeFilters)
      ]);
      appState = {
        ...appState,
        policyEvaluations,
        policyEvaluationSummary
      };
      mount(root, appState);
    } catch (error) {
      return;
    }
  });
}

function parsePolicyEvaluationStreamEvent(event) {
  try {
    const payload = JSON.parse(event.data);
    return payload && typeof payload === "object" ? payload : null;
  } catch (error) {
    return null;
  }
}

async function loadComplianceState(
  apiClient,
  auditFilters = {},
  evidenceFilters = {},
  violationFilters = {}
) {
  const [
    complianceAuditEvents,
    complianceFrameworks,
    complianceControls,
    complianceEvidence,
    complianceViolations,
    complianceReports,
    complianceReportArtifacts
  ] = await Promise.all([
    apiClient.listAuditEvents(auditFilters),
    apiClient.listComplianceFrameworks(),
    apiClient.listComplianceControls(),
    apiClient.listComplianceEvidence(evidenceFilters),
    apiClient.listComplianceViolations(violationFilters),
    apiClient.listComplianceReports(),
    apiClient.listArtifacts({ artifact_type: "compliance.report" })
  ]);
  const selectedComplianceAuditEvent = complianceAuditEvents[0] ?? null;
  const selectedReportId = appState.selectedComplianceReport?.id ?? null;
  const selectedComplianceReport =
    complianceReports.find((report) => report.id === selectedReportId) ?? complianceReports[0] ?? null;
  const [complianceAuditVerification, complianceRelatedAuditEvents] = selectedComplianceAuditEvent
    ? await Promise.all([
        apiClient.verifyAuditEvent(selectedComplianceAuditEvent.id),
        selectedComplianceAuditEvent.correlation_id
          ? apiClient.listAuditEvents({ correlation_id: selectedComplianceAuditEvent.correlation_id })
          : Promise.resolve([])
      ])
    : [null, []];
  return {
    ...appState,
    complianceAuditEvents,
    complianceAuditFilters: auditFilters,
    selectedComplianceAuditEvent,
    complianceAuditVerification,
    complianceRelatedAuditEvents,
    complianceFrameworks,
    complianceControls,
    complianceEvidence,
    complianceEvidenceFilters: evidenceFilters,
    complianceViolations,
    complianceViolationFilters: violationFilters,
    complianceReports,
    complianceReportArtifacts,
    selectedComplianceReport
  };
}

async function refreshComplianceWorkspace(
  root,
  apiClient,
  auditFilters = {},
  evidenceFilters = {},
  violationFilters = {}
) {
  appState = await loadComplianceState(apiClient, auditFilters, evidenceFilters, violationFilters);
  mount(root, appState);
}

async function loadTrustState(apiClient, eventParams = {}, handshakeParams = {}) {
  const [trustScores, trustEvents, trustRules, trustCards, trustThresholds, trustHandshakes] = await Promise.all([
    apiClient.listTrustScores(),
    apiClient.listTrustEvents(eventParams),
    apiClient.listTrustRules(),
    apiClient.listTrustCards(),
    apiClient.listTrustThresholds(),
    apiClient.listTrustHandshakes(handshakeParams)
  ]);
  return {
    ...appState,
    trustScores,
    trustEvents,
    trustRules,
    trustCards,
    trustThresholds,
    trustHandshakes,
    selectedTrustCard: trustCards[0] ?? null,
    selectedTrustHandshake: trustHandshakes[0] ?? null,
    trustEventFilter: eventParams,
    trustHandshakeFilter: handshakeParams
  };
}

async function refreshTrustWorkspace(root, apiClient, eventParams = {}, handshakeParams = appState.trustHandshakeFilter ?? {}) {
  appState = await loadTrustState(apiClient, eventParams, handshakeParams);
  mount(root, appState);
}

async function loadMeshState(apiClient, messageParams = {}, handoffParams = {}, selectedBridgeId = null) {
  const [meshTopology, meshMessages, meshHandoffs, protocolBridges, agents] = await Promise.all([
    apiClient.getMeshTopology(),
    apiClient.listMeshMessages(messageParams),
    apiClient.listMeshHandoffs(handoffParams),
    apiClient.listProtocolBridges(),
    apiClient.listAgents()
  ]);
  const activeBridgeId =
    selectedBridgeId ?? appState.selectedProtocolBridge?.id ?? protocolBridges[0]?.id ?? null;
  const selectedProtocolBridge = activeBridgeId ? await apiClient.getProtocolBridge(activeBridgeId) : null;
  return {
    ...appState,
    meshTopology,
    meshMessages,
    meshHandoffs,
    protocolBridges: selectedProtocolBridge
      ? protocolBridges.map((bridge) =>
          bridge.id === selectedProtocolBridge.id ? selectedProtocolBridge : bridge
        )
      : protocolBridges,
    selectedProtocolBridge,
    protocolBridgeAgents: agents,
    meshMessageFilter: messageParams,
    meshHandoffFilter: handoffParams
  };
}

async function refreshMeshWorkspace(
  root,
  apiClient,
  messageParams = {},
  handoffParams = appState.meshHandoffFilter ?? {},
  selectedBridgeId = appState.selectedProtocolBridge?.id ?? null
) {
  appState = await loadMeshState(apiClient, messageParams, handoffParams, selectedBridgeId);
  mount(root, appState);
}

async function loadMcpState(
  apiClient,
  findingParams = appState.mcpFindingFilter ?? {},
  trafficParams = appState.mcpTrafficFilter ?? {}
) {
  const [
    mcpServers,
    mcpTools,
    mcpScanRuns,
    mcpFindings,
    mcpTraffic,
    mcpApprovals,
    mcpRateLimits
  ] = await Promise.all([
    apiClient.listMcpServers(),
    apiClient.listMcpTools(),
    apiClient.listMcpScans(),
    apiClient.listMcpFindings(findingParams),
    apiClient.listMcpTraffic(trafficParams),
    apiClient.listMcpApprovals(),
    apiClient.listMcpRateLimits()
  ]);
  return {
    ...appState,
    mcpServers,
    mcpTools,
    mcpScanRuns,
    mcpFindings,
    mcpFindingFilter: findingParams,
    mcpTraffic,
    mcpTrafficFilter: trafficParams,
    mcpApprovals,
    mcpRateLimits
  };
}

async function refreshMcpWorkspace(
  root,
  apiClient,
  findingParams = appState.mcpFindingFilter ?? {},
  trafficParams = appState.mcpTrafficFilter ?? {}
) {
  appState = await loadMcpState(apiClient, findingParams, trafficParams);
  mount(root, appState);
}

async function loadMarketplaceState(apiClient, selectedPluginId = appState.selectedMarketplacePlugin?.id ?? null) {
  const [marketplacePlugins, marketplaceInstallations, marketplaceReviews, marketplaceSigningKeys] = await Promise.all([
    apiClient.listMarketplacePlugins(),
    apiClient.listMarketplaceInstallations(),
    apiClient.listMarketplaceReviews(),
    apiClient.listMarketplaceSigningKeys()
  ]);
  const pluginId = selectedPluginId ?? marketplacePlugins[0]?.id ?? null;
  const selectedMarketplacePlugin = pluginId ? await apiClient.getMarketplacePlugin(pluginId) : null;
  const sameSelectedPlugin = selectedMarketplacePlugin?.id === appState.selectedMarketplacePlugin?.id;
  return {
    ...appState,
    marketplacePlugins: selectedMarketplacePlugin
      ? marketplacePlugins.map((plugin) =>
          plugin.id === selectedMarketplacePlugin.id ? selectedMarketplacePlugin : plugin
        )
      : marketplacePlugins,
    selectedMarketplacePlugin,
    marketplaceInstallations,
    marketplaceReviews,
    marketplaceSigningKeys,
    marketplacePolicyResult:
      sameSelectedPlugin
        ? appState.marketplacePolicyResult ?? null
        : null,
    marketplaceQualityAssessment: sameSelectedPlugin
      ? appState.marketplaceQualityAssessment ?? null
      : null,
    marketplaceTrustEvents: sameSelectedPlugin ? appState.marketplaceTrustEvents ?? [] : []
  };
}

async function refreshMarketplaceWorkspace(
  root,
  apiClient,
  selectedPluginId = appState.selectedMarketplacePlugin?.id ?? null
) {
  appState = await loadMarketplaceState(apiClient, selectedPluginId);
  mount(root, appState);
}

async function loadObservabilityState(apiClient) {
  const [
    observabilitySlos,
    observabilityCosts,
    observabilityIncidents,
    observabilityChaosExperiments,
    observabilityRollouts
  ] = await Promise.all([
    apiClient.listObservabilitySlos(),
    apiClient.getObservabilityCosts(),
    apiClient.listObservabilityIncidents(),
    apiClient.listObservabilityChaosExperiments(),
    apiClient.listObservabilityRollouts()
  ]);
  return {
    ...appState,
    observabilitySlos,
    observabilityCosts,
    observabilityIncidents,
    observabilityChaosExperiments,
    observabilityChaosRuns: appState.observabilityChaosRuns ?? [],
    observabilityRollouts
  };
}

async function refreshObservabilityWorkspace(root, apiClient) {
  appState = await loadObservabilityState(apiClient);
  mount(root, appState);
}

async function loadIntegrationsState(apiClient) {
  const [
    integrationFrameworks,
    integrationFrameworkInstances,
    integrationFrameworkAgents,
    providerCredentials,
    integrationHealthChecks
  ] = await Promise.all([
    apiClient.listIntegrationFrameworks(),
    apiClient.listIntegrationFrameworkInstances(),
    apiClient.listIntegrationFrameworkAgents(),
    apiClient.listProviderCredentials(),
    apiClient.listLatestIntegrationHealthChecks()
  ]);
  return {
    ...appState,
    integrationFrameworks,
    integrationFrameworkInstances,
    integrationFrameworkAgents,
    providerCredentials,
    integrationHealthChecks
  };
}

async function refreshIntegrationsWorkspace(root, apiClient) {
  appState = await loadIntegrationsState(apiClient);
  mount(root, appState);
}

async function loadRuntimeState(apiClient) {
  const [
    runtimeSessions,
    runtimeRingDecisions,
    runtimeRingRules,
    runtimeSagas,
    runtimeSandboxProfiles,
    runtimeKillSwitchEvents
  ] = await Promise.all([
    apiClient.listRuntimeSessions(),
    apiClient.listRuntimeRingDecisions(),
    apiClient.listRuntimeRingRules(),
    apiClient.listRuntimeSagas(),
    apiClient.listRuntimeSandboxProfiles(),
    apiClient.listRuntimeKillSwitchEvents()
  ]);
  const selectedSessionId = runtimeSessions[0]?.id ?? null;
  const selectedRuntimeSession = selectedSessionId
    ? await apiClient.getRuntimeSession(selectedSessionId)
    : null;
  const selectedSagaId = appState.selectedRuntimeSaga?.id ?? runtimeSagas[0]?.id ?? null;
  const selectedRuntimeSaga = selectedSagaId ? await apiClient.getRuntimeSaga(selectedSagaId) : null;
  return {
    ...appState,
    runtimeSessions,
    selectedRuntimeSession,
    runtimeRingDecisions,
    runtimeRingRules,
    runtimeSagas,
    selectedRuntimeSaga,
    runtimeSandboxProfiles,
    selectedRuntimeSandboxProfile: runtimeSandboxProfiles[0] ?? null,
    runtimeKillSwitchEvents
  };
}

async function refreshRuntimeWorkspace(root, apiClient, selectedSagaId = appState.selectedRuntimeSaga?.id ?? null) {
  appState = await loadRuntimeState(apiClient);
  if (selectedSagaId) {
    appState = {
      ...appState,
      selectedRuntimeSaga: await apiClient.getRuntimeSaga(selectedSagaId)
    };
  }
  mount(root, appState);
}

async function loadDemoState(
  apiClient,
  selectedScenarioId = appState.selectedDemoScenario?.id ?? null,
  selectedRunId = appState.selectedDemoRun?.id ?? null
) {
  const [demoScenarios, demoBaselineStatus, demoResetRuns] = await Promise.all([
    apiClient.listDemoScenarios(),
    apiClient.getDemoBaselineStatus(),
    apiClient.listDemoResetRuns()
  ]);
  const scenarioId = selectedScenarioId ?? demoScenarios[0]?.id ?? null;
  const selectedDemoScenario = scenarioId ? await apiClient.getDemoScenario(scenarioId) : null;
  const selectedDemoRun = selectedRunId ? await apiClient.getDemoRun(selectedRunId) : null;
  return {
    ...appState,
    demoScenarios: selectedDemoScenario
      ? demoScenarios.map((scenario) =>
          scenario.id === selectedDemoScenario.id ? selectedDemoScenario : scenario
        )
      : demoScenarios,
    demoBaselineStatus,
    demoResetRuns,
    selectedDemoScenario,
    selectedDemoRun
  };
}

async function refreshDemoWorkspace(
  root,
  apiClient,
  selectedScenarioId = appState.selectedDemoScenario?.id ?? null,
  selectedRunId = appState.selectedDemoRun?.id ?? null
) {
  appState = await loadDemoState(apiClient, selectedScenarioId, selectedRunId);
  mount(root, appState);
}

async function loadWorkflowState(
  apiClient,
  selectedRunId = appState.selectedWorkflowRun?.id ?? null,
  selectedArtifactId = appState.selectedArtifact?.id ?? null
) {
  const [workflowDefinitions, workflowRuns, workflowArtifacts] = await Promise.all([
    apiClient.listWorkflows(),
    apiClient.listWorkflowRuns(),
    apiClient.listArtifacts()
  ]);
  const selectedWorkflowId = appState.selectedWorkflowDefinition?.id ?? workflowDefinitions[0]?.id ?? null;
  const selectedWorkflowDefinition =
    workflowDefinitions.find((workflow) => workflow.id === selectedWorkflowId) ??
    workflowDefinitions[0] ??
    null;
  const runId = selectedRunId ?? workflowRuns[0]?.id ?? null;
  const selectedWorkflowRun = runId ? await apiClient.getWorkflowRun(runId) : null;
  const artifactId = selectedArtifactId ?? workflowArtifacts[0]?.id ?? null;
  const selectedArtifact = artifactId ? await apiClient.getArtifact(artifactId) : null;
  return {
    ...appState,
    workflowDefinitions,
    selectedWorkflowDefinition,
    workflowRuns: selectedWorkflowRun
      ? workflowRuns.map((run) => (run.id === selectedWorkflowRun.id ? selectedWorkflowRun : run))
      : workflowRuns,
    selectedWorkflowRun,
    workflowArtifacts: selectedArtifact
      ? workflowArtifacts.map((artifact) =>
          artifact.id === selectedArtifact.id ? selectedArtifact : artifact
        )
      : workflowArtifacts,
    selectedArtifact
  };
}

async function refreshWorkflowWorkspace(
  root,
  apiClient,
  selectedRunId = appState.selectedWorkflowRun?.id ?? null,
  selectedArtifactId = appState.selectedArtifact?.id ?? null
) {
  appState = await loadWorkflowState(apiClient, selectedRunId, selectedArtifactId);
  mount(root, appState);
}

export function installNavigation(root = document.getElementById("app"), apiClient = null) {
  document.addEventListener("click", async (event) => {
    const link = event.target.closest("[data-route]");
    if (!link) {
      return;
    }
    const targetPath = link.getAttribute("data-route");
    if (!targetPath || (normalizePath(targetPath) !== LOGIN_ROUTE && !findRoute(targetPath))) {
      return;
    }
    event.preventDefault();
    navigate(targetPath, root);
    if (normalizePath(targetPath) !== "/policies") {
      stopPolicyEvaluationStream();
    }
    if (apiClient && normalizePath(targetPath) === "/discovery") {
      await refreshDiscoveryWorkspace(root, apiClient);
    }
    if (apiClient && normalizePath(targetPath) === "/policies") {
      await refreshPolicyWorkspace(root, apiClient);
    }
    if (apiClient && normalizePath(targetPath) === "/trust") {
      await refreshTrustWorkspace(root, apiClient);
    }
    if (apiClient && normalizePath(targetPath) === "/mesh") {
      await refreshMeshWorkspace(root, apiClient);
    }
    if (apiClient && normalizePath(targetPath) === "/mcp") {
      await refreshMcpWorkspace(root, apiClient);
    }
    if (apiClient && normalizePath(targetPath) === "/marketplace") {
      await refreshMarketplaceWorkspace(root, apiClient);
    }
    if (apiClient && normalizePath(targetPath) === "/observability") {
      await refreshObservabilityWorkspace(root, apiClient);
    }
    if (apiClient && normalizePath(targetPath) === "/compliance") {
      await refreshComplianceWorkspace(root, apiClient);
    }
    if (apiClient && normalizePath(targetPath) === "/integrations") {
      await refreshIntegrationsWorkspace(root, apiClient);
    }
    if (apiClient && normalizePath(targetPath) === "/runtime") {
      await refreshRuntimeWorkspace(root, apiClient);
    }
    if (apiClient && normalizePath(targetPath) === "/demo-lab") {
      await refreshDemoWorkspace(root, apiClient);
    }
    if (apiClient && normalizePath(targetPath) === "/workflows") {
      await refreshWorkflowWorkspace(root, apiClient);
    }
  });
  document.addEventListener("click", async (event) => {
    const logoutButton = event.target.closest("[data-logout]");
    if (!logoutButton || !apiClient) {
      return;
    }
    event.preventDefault();
    await apiClient.logout();
    stopPolicyEvaluationStream();
    appState = await loadAppContext({ apiClient, storage: window.localStorage });
    navigate(LOGIN_ROUTE, root);
  });
  document.addEventListener("change", (event) => {
    const selector = event.target.closest("[data-environment-selector]");
    if (!selector) {
      return;
    }
    appState = updateSelectedEnvironment(appState, selector.value, window.localStorage);
    mount(root, appState);
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest("[data-drawer-close]")) {
      return;
    }
    appState = withDrawer(appState, closeDrawer());
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const backButton = event.target.closest("[data-drawer-back]");
    if (!backButton) {
      return;
    }
    appState = withDrawer(appState, backDrawer(appState.drawer));
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const workflowButton = event.target.closest("[data-workflow-open]");
    if (!workflowButton) {
      return;
    }
    const workflowId = workflowButton.getAttribute("data-workflow-open");
    const selectedWorkflowDefinition =
      appState.workflowDefinitions?.find((workflow) => workflow.id === workflowId) ?? null;
    if (!selectedWorkflowDefinition) {
      return;
    }
    appState = {
      ...appState,
      selectedWorkflowDefinition,
      workflowRunError: null,
      workflowRunResult: null
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const runOpenButton = event.target.closest("[data-workflow-run-open]");
    if (!runOpenButton || !apiClient) {
      return;
    }
    const runId = runOpenButton.getAttribute("data-workflow-run-open");
    if (!runId) {
      return;
    }
    appState = {
      ...appState,
      selectedWorkflowRun: await apiClient.getWorkflowRun(runId)
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const cancelButton = event.target.closest("[data-workflow-run-cancel]");
    if (!cancelButton || !apiClient) {
      return;
    }
    const runId = cancelButton.getAttribute("data-workflow-run-cancel");
    if (!runId) {
      return;
    }
    await apiClient.cancelWorkflowRun(runId);
    await refreshWorkflowWorkspace(root, apiClient, runId, appState.selectedArtifact?.id ?? null);
  });
  document.addEventListener("click", async (event) => {
    const artifactOpenButton = event.target.closest("[data-workflow-artifact-open]");
    if (!artifactOpenButton || !apiClient) {
      return;
    }
    const artifactId = artifactOpenButton.getAttribute("data-workflow-artifact-open");
    if (!artifactId) {
      return;
    }
    appState = {
      ...appState,
      selectedArtifact: await apiClient.getArtifact(artifactId),
      workflowArtifactDownload: null,
      workflowArtifactAttestationError: null
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const artifactDownloadButton = event.target.closest("[data-workflow-artifact-download]");
    if (!artifactDownloadButton || !apiClient) {
      return;
    }
    const artifactId = artifactDownloadButton.getAttribute("data-workflow-artifact-download");
    if (!artifactId) {
      return;
    }
    appState = {
      ...appState,
      workflowArtifactDownload: await apiClient.downloadArtifact(artifactId)
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const runNowButton = event.target.closest("[data-discovery-run-now]");
    if (!runNowButton || !apiClient) {
      return;
    }
    const targetId = runNowButton.getAttribute("data-discovery-run-now");
    if (!targetId) {
      return;
    }
    await apiClient.createDiscoveryRun({ target_id: targetId });
    await refreshDiscoveryWorkspace(root, apiClient);
  });
  document.addEventListener("click", async (event) => {
    const openFindingButton = event.target.closest("[data-discovery-finding-open]");
    if (!openFindingButton || !apiClient) {
      return;
    }
    const findingId = openFindingButton.getAttribute("data-discovery-finding-open");
    if (!findingId) {
      return;
    }
    appState = {
      ...appState,
      selectedDiscoveryFinding: await apiClient.getDiscoveryFinding(findingId)
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const openRunButton = event.target.closest("[data-discovery-run-open]");
    if (!openRunButton || !apiClient) {
      return;
    }
    const runId = openRunButton.getAttribute("data-discovery-run-open");
    if (!runId) {
      return;
    }
    appState = {
      ...appState,
      selectedDiscoveryRun: await apiClient.getDiscoveryRun(runId)
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const openPolicyButton = event.target.closest("[data-policy-open]");
    if (!openPolicyButton || !apiClient) {
      return;
    }
    const policyId = openPolicyButton.getAttribute("data-policy-open");
    if (!policyId) {
      return;
    }
    await refreshPolicyWorkspace(root, apiClient, policyId);
  });
  document.addEventListener("click", async (event) => {
    const exportPolicyButton = event.target.closest("[data-policy-export]");
    if (!exportPolicyButton || !apiClient) {
      return;
    }
    const policyId = exportPolicyButton.getAttribute("data-policy-export");
    if (!policyId) {
      return;
    }
    appState = {
      ...appState,
      policyExport: await apiClient.exportPolicy(policyId)
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const actionButton = event.target.closest(
      "[data-policy-activate], [data-policy-rollback], [data-policy-archive]"
    );
    if (!actionButton || !apiClient) {
      return;
    }
    const pair =
      actionButton.getAttribute("data-policy-activate") ??
      actionButton.getAttribute("data-policy-rollback") ??
      actionButton.getAttribute("data-policy-archive") ??
      "";
    const [policyId, versionId] = pair.split(":");
    if (!policyId || !versionId) {
      return;
    }
    if (actionButton.hasAttribute("data-policy-activate")) {
      await apiClient.activatePolicyVersion(policyId, versionId);
    }
    if (actionButton.hasAttribute("data-policy-rollback")) {
      await apiClient.rollbackPolicyVersion(policyId, versionId);
    }
    if (actionButton.hasAttribute("data-policy-archive")) {
      await apiClient.archivePolicyVersion(policyId, versionId);
    }
    await refreshPolicyWorkspace(root, apiClient, policyId);
  });
  document.addEventListener("click", async (event) => {
    const lintButton = event.target.closest("[data-policy-editor-lint]");
    if (!lintButton || !apiClient) {
      return;
    }
    const policyId = lintButton.getAttribute("data-policy-editor-lint");
    const form = document.querySelector(`[data-policy-editor-form][data-policy-id="${policyId}"]`);
    if (!policyId || !form) {
      return;
    }
    const payload = policyEditorPayloadFromForm(form);
    appState = {
      ...appState,
      policyEditorLint: await apiClient.lintPolicy(payload),
      policyEditorBody: payload.body_text,
      policyEditorBodyFormat: payload.body_format,
      policyEditorBackend: payload.backend
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const openExceptionButton = event.target.closest("[data-policy-exception-open]");
    if (!openExceptionButton) {
      return;
    }
    const bindingId = openExceptionButton.getAttribute("data-policy-exception-open");
    const dialog = bindingId
      ? document.querySelector(`[data-policy-exception-modal="${bindingId}"]`)
      : null;
    if (dialog?.showModal) {
      dialog.showModal();
    }
  });
  document.addEventListener("click", async (event) => {
    const deleteBindingButton = event.target.closest("[data-policy-binding-delete]");
    if (!deleteBindingButton || !apiClient) {
      return;
    }
    const bindingId = deleteBindingButton.getAttribute("data-policy-binding-delete");
    if (!bindingId) {
      return;
    }
    await apiClient.deletePolicyBinding(bindingId);
    await refreshPolicyWorkspace(root, apiClient, appState.selectedPolicy?.id ?? null);
  });
  document.addEventListener("click", async (event) => {
    const openEvaluationButton = event.target.closest("[data-policy-evaluation-open]");
    if (!openEvaluationButton || !apiClient) {
      return;
    }
    const evaluationId = openEvaluationButton.getAttribute("data-policy-evaluation-open");
    if (!evaluationId) {
      return;
    }
    appState = {
      ...appState,
      selectedPolicyEvaluation: await apiClient.getPolicyEvaluation(evaluationId)
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const auditOpenButton = event.target.closest("[data-compliance-audit-open]");
    if (!auditOpenButton || !apiClient) {
      const violationAckButton = event.target.closest("[data-compliance-violation-ack]");
      if (!violationAckButton || !apiClient) {
        return;
      }
      const violationId = violationAckButton.getAttribute("data-compliance-violation-ack");
      if (!violationId) {
        return;
      }
      await apiClient.patchComplianceViolation(violationId, { status: "acknowledged" });
      await refreshComplianceWorkspace(
        root,
        apiClient,
        appState.complianceAuditFilters ?? {},
        appState.complianceEvidenceFilters ?? {},
        appState.complianceViolationFilters ?? {}
      );
      return;
    }
    const eventId = auditOpenButton.getAttribute("data-compliance-audit-open");
    if (!eventId) {
      return;
    }
    const selected = await apiClient.getAuditEvent(eventId);
    const [verification, relatedEvents] = await Promise.all([
      apiClient.verifyAuditEvent(eventId),
      selected.correlation_id
        ? apiClient.listAuditEvents({ correlation_id: selected.correlation_id })
        : Promise.resolve([])
    ]);
    appState = {
      ...appState,
      selectedComplianceAuditEvent: selected,
      complianceAuditVerification: verification,
      complianceRelatedAuditEvents: relatedEvents
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const relatedButton = event.target.closest("[data-related-event-id]");
    if (!relatedButton || !apiClient) {
      return;
    }
    const eventId = relatedButton.getAttribute("data-related-event-id");
    if (!eventId) {
      return;
    }
    const nextDrawer = await loadAuditEventDrawer({ apiClient, eventId });
    appState = withDrawer(appState, replaceDrawerContent(appState.drawer, nextDrawer));
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const recalculateButton = event.target.closest("[data-trust-recalculate]");
    if (!recalculateButton || !apiClient) {
      return;
    }
    await apiClient.recalculateTrust({});
    await refreshTrustWorkspace(root, apiClient, appState.trustEventFilter ?? {});
  });
  document.addEventListener("click", async (event) => {
    const verifyButton = event.target.closest("[data-trust-card-verify]");
    if (!verifyButton || !apiClient) {
      return;
    }
    const cardId = verifyButton.getAttribute("data-trust-card-verify");
    if (!cardId) {
      return;
    }
    appState = {
      ...appState,
      selectedTrustCard: await apiClient.getTrustCard(cardId),
      trustCardVerification: await apiClient.verifyTrustCard(cardId)
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const openReportButton = event.target.closest("[data-compliance-report-open]");
    const generateReportButton = event.target.closest("[data-compliance-report-generate]");
    if ((!openReportButton && !generateReportButton) || !apiClient) {
      return;
    }
    const reportId =
      openReportButton?.getAttribute("data-compliance-report-open") ??
      generateReportButton?.getAttribute("data-compliance-report-generate");
    if (!reportId) {
      return;
    }
    const selectedReport = generateReportButton
      ? await apiClient.generateComplianceReport(reportId)
      : await apiClient.getComplianceReport(reportId);
    appState = await loadComplianceState(
      apiClient,
      appState.complianceAuditFilters ?? {},
      appState.complianceEvidenceFilters ?? {},
      appState.complianceViolationFilters ?? {}
    );
    appState = {
      ...appState,
      selectedComplianceReport: selectedReport
    };
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const detailButton = event.target.closest("[data-handshake-detail-open]");
    if (!detailButton) {
      return;
    }
    const handshakeId = detailButton.getAttribute("data-handshake-detail-open");
    const handshake = appState.trustHandshakes?.find((item) => item.id === handshakeId);
    if (!handshake) {
      return;
    }
    appState = withDrawer(
      appState,
      openDrawer({
        kind: "trust-handshake",
        resourceId: handshake.id,
        title: "Trust Handshake",
        subtitle: `${handshake.source_agent_id} -> ${handshake.target_agent_id}`,
        status: handshake.result,
        content: renderHandshakeDetail(handshake)
      })
    );
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const unlinkButton = event.target.closest("[data-integration-unlink-agent]");
    if (unlinkButton && apiClient) {
      const linkId = unlinkButton.getAttribute("data-integration-unlink-agent");
      if (!linkId) {
        return;
      }
      await apiClient.unlinkIntegrationFrameworkAgent(linkId);
      await refreshIntegrationsWorkspace(root, apiClient);
      return;
    }
    const testCredentialButton = event.target.closest("[data-provider-credential-test]");
    if (!testCredentialButton || !apiClient) {
      return;
    }
    const credentialId = testCredentialButton.getAttribute("data-provider-credential-test");
    if (!credentialId) {
      return;
    }
    await apiClient.testProviderCredential(credentialId);
    await refreshIntegrationsWorkspace(root, apiClient);
  });
  document.addEventListener("click", async (event) => {
    const discoverButton = event.target.closest("[data-mcp-discover-tools]");
    if (discoverButton && apiClient) {
      const serverId = discoverButton.getAttribute("data-mcp-discover-tools");
      if (!serverId) {
        return;
      }
      await apiClient.discoverMcpServerTools(serverId);
      await refreshMcpWorkspace(root, apiClient);
      return;
    }
    const scanButton = event.target.closest("[data-mcp-run-scan]");
    if (scanButton && apiClient) {
      const serverId = scanButton.getAttribute("data-mcp-run-scan");
      if (!serverId) {
        return;
      }
      await apiClient.runMcpSecurityScan(serverId);
      await refreshMcpWorkspace(root, apiClient);
      return;
    }
    const toolDetailButton = event.target.closest("[data-mcp-tool-detail-open]");
    if (toolDetailButton && apiClient) {
      const toolId = toolDetailButton.getAttribute("data-mcp-tool-detail-open");
      if (!toolId) {
        return;
      }
      const tool = await apiClient.getMcpTool(toolId);
      appState = withDrawer(
        appState,
        openDrawer({
          kind: "mcp-tool",
          resourceId: tool.id,
          title: "MCP Tool",
          subtitle: tool.name,
          status: tool.status,
          content: renderMcpToolDetail(tool)
        })
      );
      mount(root, appState);
      return;
    }
    const findingDetailButton = event.target.closest("[data-mcp-finding-detail-open]");
    if (findingDetailButton && apiClient) {
      const findingId = findingDetailButton.getAttribute("data-mcp-finding-detail-open");
      const finding = appState.mcpFindings?.find((item) => item.id === findingId);
      if (!finding) {
        return;
      }
      appState = withDrawer(
        appState,
        openDrawer({
          kind: "mcp-finding",
          resourceId: finding.id,
          title: "MCP Finding",
          subtitle: finding.title,
          status: finding.status,
          content: renderMcpFindingDetail(finding)
        })
      );
      mount(root, appState);
      return;
    }
    const acceptRiskButton = event.target.closest("[data-mcp-accept-risk-open]");
    if (acceptRiskButton) {
      const findingId = acceptRiskButton.getAttribute("data-mcp-accept-risk-open");
      const dialog = findingId
        ? document.querySelector(`[data-mcp-accept-risk-modal="${findingId}"]`)
        : null;
      if (dialog?.showModal) {
        dialog.showModal();
      }
      return;
    }
    const approveApprovalButton = event.target.closest("[data-mcp-approval-approve-open]");
    if (approveApprovalButton) {
      const approvalId = approveApprovalButton.getAttribute("data-mcp-approval-approve-open");
      const dialog = approvalId
        ? document.querySelector(`[data-mcp-approval-approve-modal="${approvalId}"]`)
        : null;
      if (dialog?.showModal) {
        dialog.showModal();
      }
      return;
    }
    const denyApprovalButton = event.target.closest("[data-mcp-approval-deny-open]");
    if (denyApprovalButton) {
      const approvalId = denyApprovalButton.getAttribute("data-mcp-approval-deny-open");
      const dialog = approvalId
        ? document.querySelector(`[data-mcp-approval-deny-modal="${approvalId}"]`)
        : null;
      if (dialog?.showModal) {
        dialog.showModal();
      }
      return;
    }
    const bridgeOpenButton = event.target.closest("[data-protocol-bridge-open]");
    if (bridgeOpenButton && apiClient) {
      const bridgeId = bridgeOpenButton.getAttribute("data-protocol-bridge-open");
      if (!bridgeId) {
        return;
      }
      appState = {
        ...appState,
        selectedProtocolBridge: await apiClient.getProtocolBridge(bridgeId)
      };
      mount(root, appState);
      return;
    }
    const bridgeHealthButton = event.target.closest("[data-protocol-bridge-health-check]");
    if (bridgeHealthButton && apiClient) {
      const bridgeId = bridgeHealthButton.getAttribute("data-protocol-bridge-health-check");
      if (!bridgeId) {
        return;
      }
      await apiClient.runProtocolBridgeHealthCheck(bridgeId);
      await refreshMeshWorkspace(
        root,
        apiClient,
        appState.meshMessageFilter ?? {},
        appState.meshHandoffFilter ?? {},
        bridgeId
      );
      return;
    }
    const messageButton = event.target.closest("[data-mesh-message-detail-open]");
    if (messageButton) {
      const messageId = messageButton.getAttribute("data-mesh-message-detail-open");
      const message = appState.meshMessages?.find((item) => item.id === messageId);
      if (!message) {
        return;
      }
      appState = withDrawer(
        appState,
        openDrawer({
          kind: "mesh-message",
          resourceId: message.id,
          title: "Mesh Message",
          subtitle: `${message.source_agent_id} -> ${message.target_agent_id}`,
          status: message.decision,
          content: renderMeshMessageDetail(message)
        })
      );
      mount(root, appState);
      return;
    }
    const handoffButton = event.target.closest("[data-mesh-handoff-detail-open]");
    if (!handoffButton) {
      return;
    }
    const handoffId = handoffButton.getAttribute("data-mesh-handoff-detail-open");
    const handoff = appState.meshHandoffs?.find((item) => item.id === handoffId);
    if (!handoff) {
      return;
    }
    appState = withDrawer(
      appState,
      openDrawer({
        kind: "mesh-handoff",
        resourceId: handoff.id,
        title: "Mesh Handoff",
        subtitle: `${handoff.source_agent_id} -> ${handoff.target_agent_id}`,
        status: handoff.status,
        content: renderMeshHandoffDetail(handoff)
      })
    );
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const pluginButton = event.target.closest("[data-marketplace-plugin-open]");
    if (pluginButton && apiClient) {
      const pluginId = pluginButton.getAttribute("data-marketplace-plugin-open");
      if (!pluginId) {
        return;
      }
      await refreshMarketplaceWorkspace(root, apiClient, pluginId);
      return;
    }
    const uninstallButton = event.target.closest("[data-marketplace-uninstall]");
    if (uninstallButton && apiClient) {
      const installationId = uninstallButton.getAttribute("data-marketplace-uninstall");
      if (!installationId) {
        return;
      }
      await apiClient.uninstallMarketplacePlugin(installationId);
      await refreshMarketplaceWorkspace(root, apiClient);
      return;
    }
    const revokeSigningKeyButton = event.target.closest("[data-marketplace-signing-key-revoke]");
    if (revokeSigningKeyButton && apiClient) {
      const keyId = revokeSigningKeyButton.getAttribute("data-marketplace-signing-key-revoke");
      if (!keyId) {
        return;
      }
      await apiClient.revokeMarketplaceSigningKey(keyId);
      await refreshMarketplaceWorkspace(root, apiClient);
      return;
    }
    const assessQualityButton = event.target.closest("[data-marketplace-assess-quality]");
    if (assessQualityButton && apiClient) {
      const versionId = assessQualityButton.getAttribute("data-marketplace-assess-quality");
      if (!versionId) {
        return;
      }
      const marketplaceQualityAssessment = await apiClient.assessMarketplacePluginQuality(versionId);
      const selectedPluginId = appState.selectedMarketplacePlugin?.id ?? null;
      appState = await loadMarketplaceState(apiClient, selectedPluginId);
      appState = {
        ...appState,
        marketplaceQualityAssessment
      };
      mount(root, appState);
      return;
    }
  });
  document.addEventListener("click", async (event) => {
    const ackButton = event.target.closest("[data-observability-incident-ack]");
    if (ackButton && apiClient) {
      const incidentId = ackButton.getAttribute("data-observability-incident-ack");
      if (!incidentId) {
        return;
      }
      await apiClient.acknowledgeObservabilityIncident(incidentId);
      await refreshObservabilityWorkspace(root, apiClient);
      return;
    }
    const chaosRunButton = event.target.closest("[data-observability-chaos-run-open]");
    if (chaosRunButton) {
      const experimentId = chaosRunButton.getAttribute("data-observability-chaos-run-open");
      const dialog = experimentId
        ? document.querySelector(`[data-observability-chaos-run-modal="${experimentId}"]`)
        : null;
      if (dialog?.showModal) {
        dialog.showModal();
      }
      return;
    }
    const rolloutAdvanceButton = event.target.closest("[data-observability-rollout-advance-open]");
    if (rolloutAdvanceButton) {
      const rolloutId = rolloutAdvanceButton.getAttribute("data-observability-rollout-advance-open");
      const dialog = rolloutId
        ? document.querySelector(`[data-observability-rollout-advance-modal="${rolloutId}"]`)
        : null;
      if (dialog?.showModal) {
        dialog.showModal();
      }
      return;
    }
    const rolloutRollbackButton = event.target.closest("[data-observability-rollout-rollback-open]");
    if (rolloutRollbackButton) {
      const rolloutId = rolloutRollbackButton.getAttribute("data-observability-rollout-rollback-open");
      const dialog = rolloutId
        ? document.querySelector(`[data-observability-rollout-rollback-modal="${rolloutId}"]`)
        : null;
      if (dialog?.showModal) {
        dialog.showModal();
      }
      return;
    }
    const openButton = event.target.closest("[data-observability-incident-open]");
    if (!openButton) {
      return;
    }
    const incidentId = openButton.getAttribute("data-observability-incident-open");
    const incident = appState.observabilityIncidents?.find((item) => item.id === incidentId);
    if (!incident) {
      return;
    }
    appState = withDrawer(
      appState,
      openDrawer({
        kind: "observability-incident",
        resourceId: incident.id,
        title: "Incident",
        subtitle: incident.title,
        status: incident.status,
        content: renderIncidentDetail(incident)
      })
    );
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const openSagaButton = event.target.closest("[data-runtime-saga-open]");
    if (openSagaButton && apiClient) {
      const sagaId = openSagaButton.getAttribute("data-runtime-saga-open");
      if (!sagaId) {
        return;
      }
      appState = {
        ...appState,
        selectedRuntimeSaga: await apiClient.getRuntimeSaga(sagaId)
      };
      mount(root, appState);
      return;
    }
    const stepDetailButton = event.target.closest("[data-runtime-saga-step-detail-open]");
    if (!stepDetailButton) {
      return;
    }
    const [sagaId, stepId] = (stepDetailButton.getAttribute("data-runtime-saga-step-detail-open") ?? "").split(":");
    const saga = appState.selectedRuntimeSaga?.id === sagaId
      ? appState.selectedRuntimeSaga
      : appState.runtimeSagas?.find((item) => item.id === sagaId);
    const step = saga?.steps?.find((item) => item.id === stepId);
    appState = withDrawer(
      appState,
      openDrawer({
        kind: "runtime-saga-step",
        resourceId: stepId,
        title: "Saga Step",
        subtitle: step?.action_name ?? "Unknown action",
        status: step?.status ?? "unknown",
        content: renderRuntimeSagaStepDetail(step)
      })
    );
    mount(root, appState);
  });
  document.addEventListener("click", async (event) => {
    const openScenarioButton = event.target.closest("[data-demo-scenario-open]");
    if (openScenarioButton && apiClient) {
      const scenarioId = openScenarioButton.getAttribute("data-demo-scenario-open");
      if (!scenarioId) {
        return;
      }
      await refreshDemoWorkspace(root, apiClient, scenarioId, appState.selectedDemoRun?.id ?? null);
      return;
    }
    const startButton = event.target.closest("[data-demo-run-start]");
    if (startButton && apiClient) {
      const scenarioId = startButton.getAttribute("data-demo-run-start");
      if (!scenarioId) {
        return;
      }
      const run = await apiClient.startDemoRun(scenarioId);
      await refreshDemoWorkspace(root, apiClient, run.scenario_id, run.id);
      return;
    }
    const continueButton = event.target.closest("[data-demo-run-continue]");
    if (continueButton && apiClient) {
      const runId = continueButton.getAttribute("data-demo-run-continue");
      if (!runId) {
        return;
      }
      const run = await apiClient.continueDemoRun(runId);
      await refreshDemoWorkspace(root, apiClient, run.scenario_id, run.id);
      return;
    }
    const cancelButton = event.target.closest("[data-demo-run-cancel]");
    if (!cancelButton || !apiClient) {
      return;
    }
    const runId = cancelButton.getAttribute("data-demo-run-cancel");
    if (!runId) {
      return;
    }
    const run = await apiClient.cancelDemoRun(runId);
    await refreshDemoWorkspace(root, apiClient, run.scenario_id, run.id);
  });
  document.addEventListener("keydown", (event) => {
    const nextDrawer = handleDrawerKeydown(event, appState.drawer);
    if (nextDrawer !== appState.drawer) {
      appState = withDrawer(appState, nextDrawer);
      mount(root, appState);
    }
  });
  document.addEventListener("submit", async (event) => {
    const loginForm = event.target.closest("[data-dev-login-form]");
    if (loginForm && apiClient) {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(loginForm));
      try {
        await apiClient.devLogin({
          email: String(values.email ?? "").trim(),
          display_name: String(values.display_name ?? "").trim() || null,
          roles: [String(values.role ?? "Platform Admin")]
        });
        appState = await loadAppContext({ apiClient, storage: window.localStorage });
        appState = withSystemStatus(appState, await loadSystemStatus({ apiClient }));
        navigate(DEFAULT_ROUTE, root);
      } catch (error) {
        appState = {
          ...appState,
          authStatus: "unauthenticated",
          authError: error?.message ?? "Sign in failed."
        };
        mount(root, appState);
      }
      return;
    }
    const workflowRunForm = event.target.closest("[data-workflow-run-form]");
    if (workflowRunForm && apiClient) {
      event.preventDefault();
      const workflowId = workflowRunForm.getAttribute("data-workflow-id");
      const workflow =
        appState.workflowDefinitions?.find((definition) => definition.id === workflowId) ?? null;
      if (!workflowId || !workflow) {
        return;
      }
      try {
        const run = await apiClient.createWorkflowRun(
          workflowId,
          workflowRunPayloadFromForm(workflowRunForm, workflow)
        );
        appState = await loadWorkflowState(apiClient, run.id, appState.selectedArtifact?.id ?? null);
        appState = {
          ...appState,
          workflowRunResult: run,
          workflowRunError: null
        };
      } catch (error) {
        appState = {
          ...appState,
          workflowRunError: error?.message ?? "Workflow run failed."
        };
      }
      mount(root, appState);
      return;
    }
    const artifactUploadForm = event.target.closest("[data-artifact-upload-form]");
    if (artifactUploadForm && apiClient) {
      event.preventDefault();
      try {
        const artifact = await apiClient.createArtifact(artifactUploadPayloadFromForm(artifactUploadForm));
        appState = await loadWorkflowState(apiClient, appState.selectedWorkflowRun?.id ?? null, artifact.id);
        appState = {
          ...appState,
          workflowArtifactUpload: artifact
        };
      } catch (error) {
        appState = {
          ...appState,
          workflowArtifactAttestationError: error?.message ?? "Artifact upload failed."
        };
      }
      mount(root, appState);
      return;
    }
    const artifactAttestForm = event.target.closest("[data-artifact-attest-form]");
    if (artifactAttestForm && apiClient) {
      event.preventDefault();
      const artifactId = artifactAttestForm.getAttribute("data-artifact-id");
      if (!artifactId) {
        return;
      }
      try {
        const attestation = await apiClient.attestArtifact(
          artifactId,
          artifactAttestationPayloadFromForm(artifactAttestForm)
        );
        const selectedArtifact = await apiClient.getArtifact(artifactId);
        appState = await loadWorkflowState(apiClient, appState.selectedWorkflowRun?.id ?? null, artifactId);
        appState = {
          ...appState,
          selectedArtifact,
          workflowArtifactAttestation: attestation,
          workflowArtifactAttestationError: null
        };
      } catch (error) {
        appState = {
          ...appState,
          workflowArtifactAttestationError: error?.message ?? "Artifact attestation failed."
        };
      }
      mount(root, appState);
      return;
    }
    const demoResetForm = event.target.closest("[data-demo-reset-form]");
    if (demoResetForm && apiClient) {
      event.preventDefault();
      await apiClient.resetDemoEnvironment(demoResetPayloadFromForm(demoResetForm));
      await refreshDemoWorkspace(root, apiClient);
      return;
    }
    const discoveryScheduleForm = event.target.closest("[data-discovery-schedule-form]");
    if (discoveryScheduleForm && apiClient) {
      event.preventDefault();
      const targetId = discoveryScheduleForm.getAttribute("data-target-id");
      if (!targetId) {
        return;
      }
      const values = Object.fromEntries(new FormData(discoveryScheduleForm));
      await apiClient.patchDiscoveryTargetSchedule(targetId, {
        mode: String(values.mode ?? "manual")
      });
      await refreshDiscoveryWorkspace(root, apiClient);
      return;
    }
    const discoveryActionForm = event.target.closest("[data-discovery-action]");
    if (discoveryActionForm && apiClient) {
      event.preventDefault();
      const action = discoveryActionForm.getAttribute("data-discovery-action");
      const findingId = discoveryActionForm.getAttribute("data-finding-id");
      if (!action || !findingId) {
        return;
      }
      const values = Object.fromEntries(new FormData(discoveryActionForm));
      if (action === "assign-owner") {
        await apiClient.assignDiscoveryFindingOwner(findingId, {
          owner_user_id: String(values.owner_user_id ?? "")
        });
      }
      if (action === "register-agent") {
        await apiClient.registerDiscoveryFindingAgent(findingId, {
          owner_user_id: String(values.owner_user_id ?? ""),
          sponsor_user_id: String(values.sponsor_user_id ?? "")
        });
      }
      if (action === "suppress") {
        await apiClient.suppressDiscoveryFinding(findingId, {
          reason: String(values.reason ?? "")
        });
      }
      if (action === "mark-decommissioned") {
        await apiClient.markDiscoveryFindingDecommissioned(findingId);
      }
      await refreshDiscoveryWorkspace(root, apiClient);
      return;
    }
    const discoveryFilterForm = event.target.closest("[data-discovery-finding-filter]");
    if (discoveryFilterForm && apiClient) {
      event.preventDefault();
      const discoveryFindings = await apiClient.listDiscoveryFindings(
        discoveryFindingParamsFromForm(discoveryFilterForm)
      );
      const selectedFindingId =
        discoveryFindings.find((finding) => finding.status !== "suppressed")?.id ??
        discoveryFindings[0]?.id ??
        null;
      appState = {
        ...appState,
        discoveryFindings,
        selectedDiscoveryFinding: selectedFindingId
          ? await apiClient.getDiscoveryFinding(selectedFindingId)
          : null
      };
      mount(root, appState);
      return;
    }
    const policyFilterForm = event.target.closest("[data-policy-filter]");
    if (policyFilterForm && apiClient) {
      event.preventDefault();
      const policies = await apiClient.listPolicies(policyFilterParamsFromForm(policyFilterForm));
      const selectedPolicyId = policies[0]?.id ?? null;
      const selectedPolicy = selectedPolicyId ? await apiClient.getPolicy(selectedPolicyId) : null;
      appState = {
        ...appState,
        policies,
        selectedPolicy,
        policyVersions: selectedPolicy?.versions ?? []
      };
      mount(root, appState);
      return;
    }
    const policyImportForm = event.target.closest("[data-policy-import-form]");
    if (policyImportForm && apiClient) {
      event.preventDefault();
      const result = policyImportForm.querySelector("[data-policy-import-result]");
      if (result) {
        result.textContent = "Importing";
      }
      try {
        const imported = await apiClient.importPolicy(policyImportPayloadFromForm(policyImportForm));
        if (result) {
          result.textContent = imported.policy.id;
        }
        await refreshPolicyWorkspace(root, apiClient, imported.policy.id);
      } catch (error) {
        if (result) {
          result.textContent = error?.message ?? "Import failed";
        }
      }
      return;
    }
    const policyEditorForm = event.target.closest("[data-policy-editor-form]");
    if (policyEditorForm && apiClient) {
      event.preventDefault();
      const policyId = policyEditorForm.getAttribute("data-policy-id");
      if (!policyId) {
        return;
      }
      const payload = policyEditorPayloadFromForm(policyEditorForm);
      const created = await apiClient.savePolicyDraftVersion(policyId, payload);
      await apiClient.lintPolicyVersion(policyId, created.id);
      await refreshPolicyWorkspace(root, apiClient, policyId);
      return;
    }
    const policyBindingCreateForm = event.target.closest("[data-policy-binding-create-form]");
    if (policyBindingCreateForm && apiClient) {
      event.preventDefault();
      const payload = policyBindingPayloadFromForm(policyBindingCreateForm);
      await apiClient.createPolicyBinding(payload);
      await refreshPolicyWorkspace(root, apiClient, payload.policy_id ?? appState.selectedPolicy?.id ?? null);
      return;
    }
    const policyBindingPromoteForm = event.target.closest("[data-policy-binding-promote-form]");
    if (policyBindingPromoteForm && apiClient) {
      event.preventDefault();
      const bindingId = policyBindingPromoteForm.getAttribute("data-binding-id");
      if (!bindingId) {
        return;
      }
      await apiClient.promotePolicyBinding(bindingId, policyPromotePayloadFromForm(policyBindingPromoteForm));
      await refreshPolicyWorkspace(root, apiClient, appState.selectedPolicy?.id ?? null);
      return;
    }
    const policyExceptionForm = event.target.closest("[data-policy-exception-form]");
    if (policyExceptionForm && apiClient) {
      event.preventDefault();
      const bindingId = policyExceptionForm.getAttribute("data-binding-id");
      if (!bindingId) {
        return;
      }
      await apiClient.createPolicyException(bindingId, policyExceptionPayloadFromForm(policyExceptionForm));
      const dialog = document.querySelector(`[data-policy-exception-modal="${bindingId}"]`);
      if (dialog?.close) {
        dialog.close();
      }
      await refreshPolicyWorkspace(root, apiClient, appState.selectedPolicy?.id ?? null);
      return;
    }
    const policySimulatorForm = event.target.closest("[data-policy-simulator-form]");
    if (policySimulatorForm && apiClient) {
      event.preventDefault();
      try {
        const result = await apiClient.simulatePolicyEvaluation(
          policyEvaluationPayloadFromForm(policySimulatorForm)
        );
        const [policyEvaluations, policyEvaluationSummary] = await Promise.all([
          apiClient.listPolicyEvaluations(appState.policyEvaluationFilter ?? {}),
          apiClient.getPolicyEvaluationSummary(appState.policyEvaluationFilter ?? {})
        ]);
        appState = {
          ...appState,
          policyEvaluationError: null,
          policyEvaluationResult: result,
          policyEvaluations,
          policyEvaluationSummary
        };
      } catch (error) {
        appState = {
          ...appState,
          policyEvaluationError: error?.message ?? "Simulation failed"
        };
      }
      mount(root, appState);
      startPolicyEvaluationStream(root, apiClient);
      return;
    }
    const policyEvaluationFilterForm = event.target.closest("[data-policy-evaluation-filter]");
    if (policyEvaluationFilterForm && apiClient) {
      event.preventDefault();
      const params = policyEvaluationFilterParamsFromForm(policyEvaluationFilterForm);
      const [policyEvaluations, policyEvaluationSummary] = await Promise.all([
        apiClient.listPolicyEvaluations(params),
        apiClient.getPolicyEvaluationSummary(params)
      ]);
      appState = {
        ...appState,
        policyEvaluationFilter: params,
        policyEvaluations,
        policyEvaluationSummary,
        selectedPolicyEvaluation: null
      };
      mount(root, appState);
      startPolicyEvaluationStream(root, apiClient);
      return;
    }
    const complianceAuditFilterForm = event.target.closest("[data-compliance-audit-filter]");
    if (complianceAuditFilterForm && apiClient) {
      event.preventDefault();
      await refreshComplianceWorkspace(
        root,
        apiClient,
        auditEventFilterParamsFromForm(complianceAuditFilterForm),
        appState.complianceEvidenceFilters ?? {},
        appState.complianceViolationFilters ?? {}
      );
      return;
    }
    const auditExportForm = event.target.closest("[data-audit-export-form]");
    if (auditExportForm && apiClient) {
      event.preventDefault();
      const exported = await apiClient.exportAuditEvents(auditExportPayloadFromForm(auditExportForm));
      appState = {
        ...appState,
        complianceAuditExport: exported
      };
      mount(root, appState);
      return;
    }
    const evidenceFilterForm = event.target.closest("[data-compliance-evidence-filter]");
    if (evidenceFilterForm && apiClient) {
      event.preventDefault();
      await refreshComplianceWorkspace(
        root,
        apiClient,
        appState.complianceAuditFilters ?? {},
        complianceEvidenceFilterParamsFromForm(evidenceFilterForm),
        appState.complianceViolationFilters ?? {}
      );
      return;
    }
    const evidenceRecomputeForm = event.target.closest("[data-compliance-evidence-recompute]");
    if (evidenceRecomputeForm && apiClient) {
      event.preventDefault();
      const recomputeResult = await apiClient.recomputeComplianceEvidence();
      appState = await loadComplianceState(
        apiClient,
        appState.complianceAuditFilters ?? {},
        appState.complianceEvidenceFilters ?? {},
        appState.complianceViolationFilters ?? {}
      );
      appState = {
        ...appState,
        complianceEvidenceRecompute: recomputeResult
      };
      mount(root, appState);
      return;
    }
    const violationFilterForm = event.target.closest("[data-compliance-violation-filter]");
    if (violationFilterForm && apiClient) {
      event.preventDefault();
      await refreshComplianceWorkspace(
        root,
        apiClient,
        appState.complianceAuditFilters ?? {},
        appState.complianceEvidenceFilters ?? {},
        complianceViolationFilterParamsFromForm(violationFilterForm)
      );
      return;
    }
    const violationResolveForm = event.target.closest("[data-compliance-violation-resolve-form]");
    if (violationResolveForm && apiClient) {
      event.preventDefault();
      const violationId = violationResolveForm.getAttribute("data-violation-id");
      if (!violationId) {
        return;
      }
      await apiClient.patchComplianceViolation(
        violationId,
        complianceViolationPatchPayloadFromForm(violationResolveForm, "resolved")
      );
      await refreshComplianceWorkspace(
        root,
        apiClient,
        appState.complianceAuditFilters ?? {},
        appState.complianceEvidenceFilters ?? {},
        appState.complianceViolationFilters ?? {}
      );
      return;
    }
    const reportCreateForm = event.target.closest("[data-compliance-report-create-form]");
    if (reportCreateForm && apiClient) {
      event.preventDefault();
      const created = await apiClient.createComplianceReport(
        complianceReportPayloadFromForm(reportCreateForm)
      );
      appState = await loadComplianceState(
        apiClient,
        appState.complianceAuditFilters ?? {},
        appState.complianceEvidenceFilters ?? {},
        appState.complianceViolationFilters ?? {}
      );
      appState = {
        ...appState,
        selectedComplianceReport: created
      };
      mount(root, appState);
      return;
    }
    const reportAttestForm = event.target.closest("[data-compliance-report-attest-form]");
    if (reportAttestForm && apiClient) {
      event.preventDefault();
      const reportId = reportAttestForm.getAttribute("data-report-id");
      if (!reportId) {
        return;
      }
      const attestation = await apiClient.attestComplianceReport(
        reportId,
        complianceReportAttestationPayloadFromForm(reportAttestForm)
      );
      const selectedReport = await apiClient.getComplianceReport(reportId);
      appState = await loadComplianceState(
        apiClient,
        appState.complianceAuditFilters ?? {},
        appState.complianceEvidenceFilters ?? {},
        appState.complianceViolationFilters ?? {}
      );
      appState = {
        ...appState,
        complianceReportAttestation: attestation,
        selectedComplianceReport: selectedReport
      };
      mount(root, appState);
      return;
    }
    const trustEventsFilterForm = event.target.closest("[data-trust-events-filter]");
    if (trustEventsFilterForm && apiClient) {
      event.preventDefault();
      await refreshTrustWorkspace(root, apiClient, trustEventParamsFromForm(trustEventsFilterForm));
      return;
    }
    const trustCardIssueForm = event.target.closest("[data-trust-card-issue-form]");
    if (trustCardIssueForm && apiClient) {
      event.preventDefault();
      await apiClient.issueTrustCard(trustCardIssuePayloadFromForm(trustCardIssueForm));
      await refreshTrustWorkspace(root, apiClient, appState.trustEventFilter ?? {});
      return;
    }
    const trustCardRevokeForm = event.target.closest("[data-trust-card-revoke-form]");
    if (trustCardRevokeForm && apiClient) {
      event.preventDefault();
      const cardId = trustCardRevokeForm.getAttribute("data-card-id");
      if (!cardId) {
        return;
      }
      await apiClient.revokeTrustCard(cardId, trustCardRevokePayloadFromForm(trustCardRevokeForm));
      await refreshTrustWorkspace(root, apiClient, appState.trustEventFilter ?? {});
      return;
    }
    const trustThresholdForm = event.target.closest("[data-trust-threshold-form]");
    if (trustThresholdForm && apiClient) {
      event.preventDefault();
      await apiClient.createTrustThreshold(trustThresholdPayloadFromForm(trustThresholdForm));
      await refreshTrustWorkspace(root, apiClient, appState.trustEventFilter ?? {});
      return;
    }
    const trustThresholdPatchForm = event.target.closest("[data-trust-threshold-patch-form]");
    if (trustThresholdPatchForm && apiClient) {
      event.preventDefault();
      const thresholdId = trustThresholdPatchForm.getAttribute("data-threshold-id");
      if (!thresholdId) {
        return;
      }
      await apiClient.patchTrustThreshold(
        thresholdId,
        trustThresholdPatchPayloadFromForm(trustThresholdPatchForm)
      );
      await refreshTrustWorkspace(root, apiClient, appState.trustEventFilter ?? {});
      return;
    }
    const trustHandshakeFilterForm = event.target.closest("[data-trust-handshake-filter]");
    if (trustHandshakeFilterForm && apiClient) {
      event.preventDefault();
      await refreshTrustWorkspace(
        root,
        apiClient,
        appState.trustEventFilter ?? {},
        trustHandshakeParamsFromForm(trustHandshakeFilterForm)
      );
      return;
    }
    const trustHandshakeSimulateForm = event.target.closest("[data-trust-handshake-simulate-form]");
    if (trustHandshakeSimulateForm && apiClient) {
      event.preventDefault();
      const simulation = await apiClient.simulateTrustHandshake(
        trustHandshakePayloadFromForm(trustHandshakeSimulateForm)
      );
      const nextState = await loadTrustState(
        apiClient,
        appState.trustEventFilter ?? {},
        appState.trustHandshakeFilter ?? {}
      );
      appState = {
        ...nextState,
        trustHandshakeSimulation: simulation,
        selectedTrustHandshake: simulation
      };
      mount(root, appState);
      return;
    }
    const meshMessageFilterForm = event.target.closest("[data-mesh-message-filter]");
    if (meshMessageFilterForm && apiClient) {
      event.preventDefault();
      await refreshMeshWorkspace(
        root,
        apiClient,
        meshMessageParamsFromForm(meshMessageFilterForm),
        appState.meshHandoffFilter ?? {}
      );
      return;
    }
    const meshHandoffFilterForm = event.target.closest("[data-mesh-handoff-filter]");
    if (meshHandoffFilterForm && apiClient) {
      event.preventDefault();
      await refreshMeshWorkspace(
        root,
        apiClient,
        appState.meshMessageFilter ?? {},
        meshHandoffParamsFromForm(meshHandoffFilterForm)
      );
      return;
    }
    const mcpServerRegisterForm = event.target.closest("[data-mcp-server-register-form]");
    if (mcpServerRegisterForm && apiClient) {
      event.preventDefault();
      await apiClient.createMcpServer(mcpServerPayloadFromForm(mcpServerRegisterForm));
      await refreshMcpWorkspace(root, apiClient);
      return;
    }
    const mcpFindingFilterForm = event.target.closest("[data-mcp-finding-filter-form]");
    if (mcpFindingFilterForm && apiClient) {
      event.preventDefault();
      await refreshMcpWorkspace(root, apiClient, mcpFindingFilterParamsFromForm(mcpFindingFilterForm));
      return;
    }
    const mcpTrafficFilterForm = event.target.closest("[data-mcp-traffic-filter-form]");
    if (mcpTrafficFilterForm && apiClient) {
      event.preventDefault();
      await refreshMcpWorkspace(
        root,
        apiClient,
        appState.mcpFindingFilter ?? {},
        mcpTrafficFilterParamsFromForm(mcpTrafficFilterForm)
      );
      return;
    }
    const mcpFindingAcceptRiskForm = event.target.closest("[data-mcp-finding-accept-risk-form]");
    if (mcpFindingAcceptRiskForm && apiClient) {
      event.preventDefault();
      const findingId = mcpFindingAcceptRiskForm.getAttribute("data-finding-id");
      if (!findingId) {
        return;
      }
      await apiClient.acceptMcpFindingRisk(
        findingId,
        mcpFindingActionPayloadFromForm(mcpFindingAcceptRiskForm)
      );
      const dialog = document.querySelector(`[data-mcp-accept-risk-modal="${findingId}"]`);
      if (dialog?.close) {
        dialog.close();
      }
      await refreshMcpWorkspace(root, apiClient);
      return;
    }
    const mcpFindingResolveForm = event.target.closest("[data-mcp-finding-resolve-form]");
    if (mcpFindingResolveForm && apiClient) {
      event.preventDefault();
      const findingId = mcpFindingResolveForm.getAttribute("data-finding-id");
      if (!findingId) {
        return;
      }
      await apiClient.resolveMcpFinding(
        findingId,
        mcpFindingActionPayloadFromForm(mcpFindingResolveForm)
      );
      await refreshMcpWorkspace(root, apiClient);
      return;
    }
    const mcpApprovalApproveForm = event.target.closest("[data-mcp-approval-approve-form]");
    if (mcpApprovalApproveForm && apiClient) {
      event.preventDefault();
      const approvalId = mcpApprovalApproveForm.getAttribute("data-approval-id");
      if (!approvalId) {
        return;
      }
      await apiClient.approveMcpApproval(
        approvalId,
        mcpApprovalDecisionPayloadFromForm(mcpApprovalApproveForm)
      );
      const dialog = document.querySelector(`[data-mcp-approval-approve-modal="${approvalId}"]`);
      if (dialog?.close) {
        dialog.close();
      }
      await refreshMcpWorkspace(root, apiClient);
      return;
    }
    const mcpApprovalDenyForm = event.target.closest("[data-mcp-approval-deny-form]");
    if (mcpApprovalDenyForm && apiClient) {
      event.preventDefault();
      const approvalId = mcpApprovalDenyForm.getAttribute("data-approval-id");
      if (!approvalId) {
        return;
      }
      await apiClient.denyMcpApproval(
        approvalId,
        mcpApprovalDecisionPayloadFromForm(mcpApprovalDenyForm)
      );
      const dialog = document.querySelector(`[data-mcp-approval-deny-modal="${approvalId}"]`);
      if (dialog?.close) {
        dialog.close();
      }
      await refreshMcpWorkspace(root, apiClient);
      return;
    }
    const mcpRateLimitForm = event.target.closest("[data-mcp-rate-limit-form]");
    if (mcpRateLimitForm && apiClient) {
      event.preventDefault();
      await apiClient.createMcpRateLimit(mcpRateLimitPayloadFromForm(mcpRateLimitForm));
      await refreshMcpWorkspace(root, apiClient);
      return;
    }
    const marketplacePolicyForm = event.target.closest("[data-marketplace-policy-check-form]");
    if (marketplacePolicyForm && apiClient) {
      event.preventDefault();
      const versionId = marketplacePolicyForm.getAttribute("data-version-id");
      if (!versionId) {
        return;
      }
      const marketplacePolicyResult = await apiClient.checkMarketplacePluginPolicy(
        versionId,
        marketplacePolicyPayloadFromForm(marketplacePolicyForm)
      );
      appState = {
        ...appState,
        marketplacePolicyResult
      };
      mount(root, appState);
      return;
    }
    const marketplaceInstallForm = event.target.closest("[data-marketplace-install-form]");
    if (marketplaceInstallForm && apiClient) {
      event.preventDefault();
      await apiClient.createMarketplaceInstallation(
        marketplaceInstallPayloadFromForm(marketplaceInstallForm)
      );
      await refreshMarketplaceWorkspace(root, apiClient);
      return;
    }
    const marketplaceReviewSubmitForm = event.target.closest("[data-marketplace-submit-review-form]");
    if (marketplaceReviewSubmitForm && apiClient) {
      event.preventDefault();
      const versionId = marketplaceReviewSubmitForm.getAttribute("data-version-id");
      if (!versionId) {
        return;
      }
      await apiClient.submitMarketplacePluginReview(
        versionId,
        marketplaceReviewSubmitPayloadFromForm(marketplaceReviewSubmitForm)
      );
      await refreshMarketplaceWorkspace(root, apiClient);
      return;
    }
    const marketplaceReviewApproveForm = event.target.closest("[data-marketplace-review-approve-form]");
    if (marketplaceReviewApproveForm && apiClient) {
      event.preventDefault();
      const reviewId = marketplaceReviewApproveForm.getAttribute("data-review-id");
      if (!reviewId) {
        return;
      }
      await apiClient.approveMarketplaceReview(
        reviewId,
        marketplaceReviewDecisionPayloadFromForm(marketplaceReviewApproveForm)
      );
      await refreshMarketplaceWorkspace(root, apiClient);
      return;
    }
    const marketplaceReviewRejectForm = event.target.closest("[data-marketplace-review-reject-form]");
    if (marketplaceReviewRejectForm && apiClient) {
      event.preventDefault();
      const reviewId = marketplaceReviewRejectForm.getAttribute("data-review-id");
      if (!reviewId) {
        return;
      }
      await apiClient.rejectMarketplaceReview(
        reviewId,
        marketplaceReviewDecisionPayloadFromForm(marketplaceReviewRejectForm)
      );
      await refreshMarketplaceWorkspace(root, apiClient);
      return;
    }
    const marketplaceSigningKeyForm = event.target.closest("[data-marketplace-signing-key-form]");
    if (marketplaceSigningKeyForm && apiClient) {
      event.preventDefault();
      await apiClient.createMarketplaceSigningKey(
        marketplaceSigningKeyPayloadFromForm(marketplaceSigningKeyForm)
      );
      await refreshMarketplaceWorkspace(root, apiClient);
      return;
    }
    const marketplaceTrustForm = event.target.closest("[data-marketplace-trust-recompute-form]");
    if (marketplaceTrustForm && apiClient) {
      event.preventDefault();
      const versionId = marketplaceTrustForm.getAttribute("data-version-id");
      if (!versionId) {
        return;
      }
      const marketplaceTrustEvent = await apiClient.recomputeMarketplacePluginTrust(
        versionId,
        marketplaceTrustPayloadFromForm(marketplaceTrustForm)
      );
      const selectedPluginId = appState.selectedMarketplacePlugin?.id ?? null;
      const previousEvents = appState.marketplaceTrustEvents ?? [];
      appState = await loadMarketplaceState(apiClient, selectedPluginId);
      appState = {
        ...appState,
        marketplaceTrustEvents: [marketplaceTrustEvent, ...previousEvents]
      };
      mount(root, appState);
      return;
    }
    const observabilitySloForm = event.target.closest("[data-observability-slo-form]");
    if (observabilitySloForm && apiClient) {
      event.preventDefault();
      await apiClient.createObservabilitySlo(observabilitySloPayloadFromForm(observabilitySloForm));
      await refreshObservabilityWorkspace(root, apiClient);
      return;
    }
    const observabilityCostBudgetForm = event.target.closest("[data-observability-cost-budget-form]");
    if (observabilityCostBudgetForm && apiClient) {
      event.preventDefault();
      await apiClient.createObservabilityCostBudget(
        observabilityCostBudgetPayloadFromForm(observabilityCostBudgetForm)
      );
      await refreshObservabilityWorkspace(root, apiClient);
      return;
    }
    const observabilityCostEventForm = event.target.closest("[data-observability-cost-event-form]");
    if (observabilityCostEventForm && apiClient) {
      event.preventDefault();
      await apiClient.createObservabilityCostEvent(
        observabilityCostEventPayloadFromForm(observabilityCostEventForm)
      );
      await refreshObservabilityWorkspace(root, apiClient);
      return;
    }
    const observabilityIncidentForm = event.target.closest("[data-observability-incident-form]");
    if (observabilityIncidentForm && apiClient) {
      event.preventDefault();
      await apiClient.createObservabilityIncident(
        observabilityIncidentPayloadFromForm(observabilityIncidentForm)
      );
      await refreshObservabilityWorkspace(root, apiClient);
      return;
    }
    const observabilityIncidentResolveForm = event.target.closest(
      "[data-observability-incident-resolve-form]"
    );
    if (observabilityIncidentResolveForm && apiClient) {
      event.preventDefault();
      const incidentId = observabilityIncidentResolveForm.getAttribute("data-incident-id");
      if (!incidentId) {
        return;
      }
      await apiClient.resolveObservabilityIncident(
        incidentId,
        observabilityIncidentResolvePayloadFromForm(observabilityIncidentResolveForm)
      );
      await refreshObservabilityWorkspace(root, apiClient);
      return;
    }
    const observabilityChaosExperimentForm = event.target.closest(
      "[data-observability-chaos-experiment-form]"
    );
    if (observabilityChaosExperimentForm && apiClient) {
      event.preventDefault();
      await apiClient.createObservabilityChaosExperiment(
        observabilityChaosExperimentPayloadFromForm(observabilityChaosExperimentForm)
      );
      await refreshObservabilityWorkspace(root, apiClient);
      return;
    }
    const observabilityChaosRunForm = event.target.closest("[data-observability-chaos-run-form]");
    if (observabilityChaosRunForm && apiClient) {
      event.preventDefault();
      const experimentId = observabilityChaosRunForm.getAttribute("data-experiment-id");
      if (!experimentId) {
        return;
      }
      const previousRuns = appState.observabilityChaosRuns ?? [];
      const chaosRun = await apiClient.runObservabilityChaosExperiment(
        experimentId,
        observabilityChaosRunPayloadFromForm(observabilityChaosRunForm)
      );
      const dialog = document.querySelector(`[data-observability-chaos-run-modal="${experimentId}"]`);
      if (dialog?.close) {
        dialog.close();
      }
      appState = await loadObservabilityState(apiClient);
      appState = {
        ...appState,
        observabilityChaosRuns: [chaosRun, ...previousRuns]
      };
      mount(root, appState);
      return;
    }
    const observabilityRolloutForm = event.target.closest("[data-observability-rollout-form]");
    if (observabilityRolloutForm && apiClient) {
      event.preventDefault();
      await apiClient.createObservabilityRollout(
        observabilityRolloutPayloadFromForm(observabilityRolloutForm)
      );
      await refreshObservabilityWorkspace(root, apiClient);
      return;
    }
    const observabilityRolloutAdvanceForm = event.target.closest(
      "[data-observability-rollout-advance-form]"
    );
    if (observabilityRolloutAdvanceForm && apiClient) {
      event.preventDefault();
      const rolloutId = observabilityRolloutAdvanceForm.getAttribute("data-rollout-id");
      if (!rolloutId) {
        return;
      }
      await apiClient.advanceObservabilityRollout(
        rolloutId,
        observabilityRolloutAdvancePayloadFromForm(observabilityRolloutAdvanceForm)
      );
      const dialog = document.querySelector(`[data-observability-rollout-advance-modal="${rolloutId}"]`);
      if (dialog?.close) {
        dialog.close();
      }
      await refreshObservabilityWorkspace(root, apiClient);
      return;
    }
    const observabilityRolloutRollbackForm = event.target.closest(
      "[data-observability-rollout-rollback-form]"
    );
    if (observabilityRolloutRollbackForm && apiClient) {
      event.preventDefault();
      const rolloutId = observabilityRolloutRollbackForm.getAttribute("data-rollout-id");
      if (!rolloutId) {
        return;
      }
      await apiClient.rollbackObservabilityRollout(
        rolloutId,
        observabilityRolloutRollbackPayloadFromForm(observabilityRolloutRollbackForm)
      );
      const dialog = document.querySelector(`[data-observability-rollout-rollback-modal="${rolloutId}"]`);
      if (dialog?.close) {
        dialog.close();
      }
      await refreshObservabilityWorkspace(root, apiClient);
      return;
    }
    const integrationInstanceForm = event.target.closest("[data-integration-instance-form]");
    if (integrationInstanceForm && apiClient) {
      event.preventDefault();
      await apiClient.createIntegrationFrameworkInstance(
        integrationInstancePayloadFromForm(integrationInstanceForm)
      );
      await refreshIntegrationsWorkspace(root, apiClient);
      return;
    }
    const integrationLinkAgentForm = event.target.closest("[data-integration-link-agent-form]");
    if (integrationLinkAgentForm && apiClient) {
      event.preventDefault();
      const instanceId = integrationLinkAgentForm.getAttribute("data-instance-id");
      if (!instanceId) {
        return;
      }
      await apiClient.linkIntegrationFrameworkAgent(
        instanceId,
        integrationAgentLinkPayloadFromForm(integrationLinkAgentForm)
      );
      await refreshIntegrationsWorkspace(root, apiClient);
      return;
    }
    const providerCredentialForm = event.target.closest("[data-provider-credential-form]");
    if (providerCredentialForm && apiClient) {
      event.preventDefault();
      await apiClient.createProviderCredential(
        providerCredentialPayloadFromForm(providerCredentialForm)
      );
      await refreshIntegrationsWorkspace(root, apiClient);
      return;
    }
    const runtimeSessionForm = event.target.closest("[data-runtime-session-form]");
    if (runtimeSessionForm && apiClient) {
      event.preventDefault();
      await apiClient.createRuntimeSession(runtimeSessionPayloadFromForm(runtimeSessionForm));
      await refreshRuntimeWorkspace(root, apiClient);
      return;
    }
    const runtimeActionForm = event.target.closest("[data-runtime-action-form]");
    if (runtimeActionForm && apiClient) {
      event.preventDefault();
      const sessionId = runtimeActionForm.getAttribute("data-session-id");
      if (!sessionId) {
        return;
      }
      await apiClient.createRuntimeAction(sessionId, runtimeActionPayloadFromForm(runtimeActionForm));
      await refreshRuntimeWorkspace(root, apiClient);
      return;
    }
    const runtimeRingRuleForm = event.target.closest("[data-runtime-ring-rule-form]");
    if (runtimeRingRuleForm && apiClient) {
      event.preventDefault();
      await apiClient.createRuntimeRingRule(runtimeRingRulePayloadFromForm(runtimeRingRuleForm));
      await refreshRuntimeWorkspace(root, apiClient);
      return;
    }
    const runtimeSagaForm = event.target.closest("[data-runtime-saga-form]");
    if (runtimeSagaForm && apiClient) {
      event.preventDefault();
      const saga = await apiClient.createRuntimeSaga(runtimeSagaPayloadFromForm(runtimeSagaForm));
      await refreshRuntimeWorkspace(root, apiClient, saga.id);
      return;
    }
    const runtimeSagaStepForm = event.target.closest("[data-runtime-saga-step-form]");
    if (runtimeSagaStepForm && apiClient) {
      event.preventDefault();
      const sagaId = runtimeSagaStepForm.getAttribute("data-saga-id");
      if (!sagaId) {
        return;
      }
      await apiClient.addRuntimeSagaStep(sagaId, runtimeSagaStepPayloadFromForm(runtimeSagaStepForm));
      await refreshRuntimeWorkspace(root, apiClient, sagaId);
      return;
    }
    const runtimeSagaExecuteForm = event.target.closest("[data-runtime-saga-execute-form]");
    if (runtimeSagaExecuteForm && apiClient) {
      event.preventDefault();
      const sagaId = runtimeSagaExecuteForm.getAttribute("data-saga-id");
      if (!sagaId) {
        return;
      }
      await apiClient.executeRuntimeSaga(sagaId, runtimeSagaExecutePayloadFromForm(runtimeSagaExecuteForm));
      await refreshRuntimeWorkspace(root, apiClient, sagaId);
      return;
    }
    const runtimeSagaCancelForm = event.target.closest("[data-runtime-saga-cancel-form]");
    if (runtimeSagaCancelForm && apiClient) {
      event.preventDefault();
      const sagaId = runtimeSagaCancelForm.getAttribute("data-saga-id");
      if (!sagaId) {
        return;
      }
      await apiClient.cancelRuntimeSaga(sagaId, runtimeSagaCancelPayloadFromForm(runtimeSagaCancelForm));
      await refreshRuntimeWorkspace(root, apiClient, sagaId);
      return;
    }
    const runtimeSandboxProfileForm = event.target.closest("[data-runtime-sandbox-profile-form]");
    if (runtimeSandboxProfileForm && apiClient) {
      event.preventDefault();
      await apiClient.createRuntimeSandboxProfile(
        runtimeSandboxProfilePayloadFromForm(runtimeSandboxProfileForm)
      );
      await refreshRuntimeWorkspace(root, apiClient);
      return;
    }
    const runtimeSandboxTestForm = event.target.closest("[data-runtime-sandbox-test-form]");
    if (runtimeSandboxTestForm && apiClient) {
      event.preventDefault();
      const profileId = runtimeSandboxTestForm.getAttribute("data-profile-id");
      if (!profileId) {
        return;
      }
      const decision = await apiClient.testRuntimeSandboxProfile(
        profileId,
        runtimeSandboxTestPayloadFromForm(runtimeSandboxTestForm)
      );
      appState = {
        ...appState,
        runtimeSandboxDecision: decision
      };
      mount(root, appState);
      return;
    }
    const runtimeKillSwitchForm = event.target.closest("[data-runtime-kill-switch-form]");
    if (runtimeKillSwitchForm && apiClient) {
      event.preventDefault();
      await apiClient.triggerRuntimeKillSwitch(runtimeKillSwitchPayloadFromForm(runtimeKillSwitchForm));
      await refreshRuntimeWorkspace(root, apiClient);
      return;
    }
    const bridgeCreateForm = event.target.closest("[data-protocol-bridge-create-form]");
    if (bridgeCreateForm && apiClient) {
      event.preventDefault();
      const bridge = await apiClient.createProtocolBridge(protocolBridgePayloadFromForm(bridgeCreateForm));
      await refreshMeshWorkspace(
        root,
        apiClient,
        appState.meshMessageFilter ?? {},
        appState.meshHandoffFilter ?? {},
        bridge.id
      );
      return;
    }
    const bridgeRouteForm = event.target.closest("[data-protocol-bridge-route-form]");
    if (bridgeRouteForm && apiClient) {
      event.preventDefault();
      const bridgeId = bridgeRouteForm.getAttribute("data-bridge-id");
      if (!bridgeId) {
        return;
      }
      await apiClient.createProtocolBridgeRoute(
        bridgeId,
        protocolBridgeRoutePayloadFromForm(bridgeRouteForm)
      );
      await refreshMeshWorkspace(
        root,
        apiClient,
        appState.meshMessageFilter ?? {},
        appState.meshHandoffFilter ?? {},
        bridgeId
      );
      return;
    }
    const filterForm = event.target.closest("[data-agent-inventory-filter]");
    if (filterForm && apiClient) {
      event.preventDefault();
      const region = document.querySelector("[data-agent-inventory-table-region]");
      if (region) {
        region.innerHTML = '<div class="drawer-state" data-agent-inventory-loading>Loading agents</div>';
      }
      try {
        const agents = await apiClient.listAgents(agentInventoryParamsFromForm(filterForm));
        if (region) {
          region.innerHTML = agents.length
            ? renderAgentInventoryTable(agents)
            : '<div class="empty-state" data-agent-inventory-empty><strong>No agents</strong><span>Register Agent</span></div>';
        }
      } catch (error) {
        if (region) {
          region.innerHTML = `<div class="drawer-state is-error">${error?.message ?? "Unable to load agents"}</div>`;
        }
      }
      return;
    }
    const form = event.target.closest("[data-agent-registration-form]");
    if (!form || !apiClient) {
      return;
    }
    event.preventDefault();
    const result = form.querySelector("[data-agent-registration-result]");
    if (result) {
      result.textContent = "Registering";
    }
    try {
      const payload = registrationPayloadFromForm(form);
      const draft = await apiClient.createAgentRegistrationDraft(payload.draft);
      const identity = await apiClient.createAgentIdentity(draft.id);
      await apiClient.updateAgentRegistrationDraft(draft.id, payload.selections);
      const simulation = await apiClient.simulateAgentRegistrationDraft(draft.id);
      const submitted = await apiClient.submitAgentRegistrationDraft(draft.id);
      if (result) {
        result.textContent = JSON.stringify(
          {
            agent_id: submitted.id,
            status: submitted.status,
            decision: simulation.decision,
            did: identity.identity.did,
            private_key_pem: identity.bootstrap?.private_key_pem ?? null
          },
          null,
          2
        );
      }
    } catch (error) {
      if (result) {
        result.textContent = error?.message ?? "Registration failed";
      }
    }
  });
  window.addEventListener("popstate", () => {
    if (currentPath() !== "/policies") {
      stopPolicyEvaluationStream();
    }
    mount(root);
  });
}

export async function bootstrap({
  root = document.getElementById("app"),
  storage = window.localStorage
} = {}) {
  mount(root, appState);
  const apiClient = createApiClient({
    getTenantContext: () => tenantContext(appState)
  });
  appState = await loadAppContext({ apiClient, storage });
  appState = withDrawer(appState, drawerFromDeepLink(window.location.search));
  mount(root, appState);
  if (appState.authStatus === "authenticated") {
    appState = withSystemStatus(appState, await loadSystemStatus({ apiClient }));
    mount(root, appState);
    if (currentPath() === "/discovery") {
      appState = await loadDiscoveryState(apiClient);
      mount(root, appState);
    }
    if (currentPath() === "/policies") {
      appState = await loadPolicyState(apiClient);
      mount(root, appState);
      startPolicyEvaluationStream(root, apiClient);
    }
    if (currentPath() === "/trust") {
      appState = await loadTrustState(apiClient);
      mount(root, appState);
    }
    if (currentPath() === "/mcp") {
      appState = await loadMcpState(apiClient);
      mount(root, appState);
    }
    if (currentPath() === "/marketplace") {
      appState = await loadMarketplaceState(apiClient);
      mount(root, appState);
    }
    if (currentPath() === "/observability") {
      appState = await loadObservabilityState(apiClient);
      mount(root, appState);
    }
    if (currentPath() === "/compliance") {
      appState = await loadComplianceState(apiClient);
      mount(root, appState);
    }
    if (currentPath() === "/integrations") {
      appState = await loadIntegrationsState(apiClient);
      mount(root, appState);
    }
    if (currentPath() === "/runtime") {
      appState = await loadRuntimeState(apiClient);
      mount(root, appState);
    }
    if (currentPath() === "/demo-lab") {
      appState = await loadDemoState(apiClient);
      mount(root, appState);
    }
    if (currentPath() === "/workflows") {
      appState = await loadWorkflowState(apiClient);
      mount(root, appState);
    }
    if (appState.drawer.open && appState.drawer.kind === "audit-event" && appState.drawer.resourceId) {
      appState = withDrawer(
        appState,
        await loadAuditEventDrawer({ apiClient, eventId: appState.drawer.resourceId })
      );
      mount(root, appState);
    }
  }
  installNavigation(root, apiClient);
  return appState;
}

if (typeof window !== "undefined") {
  bootstrap();
}
