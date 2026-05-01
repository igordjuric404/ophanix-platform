import { DEFAULT_ROUTE, findRoute, normalizePath } from "./navigation.js";
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
  policyBindingPayloadFromForm,
  policyEditorPayloadFromForm,
  policyExceptionPayloadFromForm,
  policyFilterParamsFromForm,
  policyImportPayloadFromForm,
  policyPromotePayloadFromForm
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
  createLoadingState,
  loadAppContext,
  loadSystemStatus,
  tenantContext,
  updateSelectedEnvironment,
  withDrawer,
  withSystemStatus
} from "./state.js";

let appState = createLoadingState();

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
  const [policies, policyBindings, policyExceptions, agents] = await Promise.all([
    apiClient.listPolicies(),
    apiClient.listPolicyBindings(),
    apiClient.listPolicyExceptions(),
    apiClient.listAgents()
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
    policyBindingTargets: { agents }
  };
}

async function refreshPolicyWorkspace(root, apiClient, selectedPolicyId = null) {
  appState = await loadPolicyState(apiClient, selectedPolicyId);
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

export function installNavigation(root = document.getElementById("app"), apiClient = null) {
  document.addEventListener("click", async (event) => {
    const link = event.target.closest("[data-route]");
    if (!link) {
      return;
    }
    const targetPath = link.getAttribute("data-route");
    if (!targetPath || !findRoute(targetPath)) {
      return;
    }
    event.preventDefault();
    navigate(targetPath, root);
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
  document.addEventListener("keydown", (event) => {
    const nextDrawer = handleDrawerKeydown(event, appState.drawer);
    if (nextDrawer !== appState.drawer) {
      appState = withDrawer(appState, nextDrawer);
      mount(root, appState);
    }
  });
  document.addEventListener("submit", async (event) => {
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
  window.addEventListener("popstate", () => mount(root));
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
    }
    if (currentPath() === "/trust") {
      appState = await loadTrustState(apiClient);
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
