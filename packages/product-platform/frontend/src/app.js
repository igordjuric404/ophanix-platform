import { DEFAULT_ROUTE, findRoute, normalizePath } from "./navigation.js";
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

export function installNavigation(root = document.getElementById("app"), apiClient = null) {
  document.addEventListener("click", (event) => {
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
