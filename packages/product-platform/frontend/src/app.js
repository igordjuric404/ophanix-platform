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
  replaceDrawerContent
} from "./drawers.js";
import { renderShell } from "./render.js";
import { discoveryFindingParamsFromForm } from "./discovery.js";
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
