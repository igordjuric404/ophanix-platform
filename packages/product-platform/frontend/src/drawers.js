import { escapeHtml } from "./html.js";

export const DRAWER_KINDS = {
  AUDIT_EVENT: "audit-event",
  POLICY_DECISION: "policy-decision",
  AGENT_SNAPSHOT: "agent-snapshot",
  TRUST_CHANGE: "trust-change",
  MCP_CALL: "mcp-call",
  RUNTIME_ACTION: "runtime-action",
  WORKFLOW_RUN: "workflow-run",
  APPROVAL_REQUEST: "approval-request"
};

export const DEFAULT_DRAWER_TABS = [
  { id: "overview", label: "Overview" },
  { id: "evidence", label: "Evidence" },
  { id: "related", label: "Related" }
];

export function createClosedDrawerState() {
  return {
    open: false,
    kind: null,
    resourceId: null,
    title: "",
    subtitle: "",
    status: "",
    activeTab: "overview",
    tabs: DEFAULT_DRAWER_TABS,
    state: "empty",
    content: "",
    error: null,
    actions: [],
    backStack: []
  };
}

export function openDrawer(options = {}) {
  return {
    ...createClosedDrawerState(),
    open: true,
    kind: options.kind ?? DRAWER_KINDS.AUDIT_EVENT,
    resourceId: options.resourceId ?? null,
    title: options.title ?? "Detail",
    subtitle: options.subtitle ?? "",
    status: options.status ?? "Open",
    activeTab: options.activeTab ?? "overview",
    tabs: options.tabs ?? DEFAULT_DRAWER_TABS,
    state: options.state ?? "ready",
    content: options.content ?? "",
    error: options.error ?? null,
    actions: options.actions ?? [],
    backStack: options.backStack ?? []
  };
}

export function closeDrawer() {
  return createClosedDrawerState();
}

export function replaceDrawerContent(currentDrawer, nextDrawer) {
  return {
    ...nextDrawer,
    backStack: [snapshotDrawer(currentDrawer), ...(currentDrawer.backStack ?? [])]
  };
}

export function backDrawer(drawer) {
  const [previous, ...remaining] = drawer.backStack ?? [];
  if (!previous) {
    return drawer;
  }
  return {
    ...previous,
    backStack: remaining
  };
}

export function renderDrawer(drawer = createClosedDrawerState()) {
  if (!drawer.open) {
    return "";
  }
  const titleId = "detail-drawer-title";
  const descriptionId = "detail-drawer-description";
  return `
    <aside class="drawer-backdrop" data-drawer-open>
      <section
        class="detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="${titleId}"
        aria-describedby="${descriptionId}"
      >
        <header class="drawer-header">
          <div>
            <p class="section-label">${escapeHtml(drawer.kind)}</p>
            <h2 id="${titleId}">${escapeHtml(drawer.title)}</h2>
            <p id="${descriptionId}">${escapeHtml(drawer.subtitle)}</p>
          </div>
          <div class="drawer-header-actions">
            ${
              drawer.backStack?.length
                ? '<button class="drawer-back" type="button" data-drawer-back>Back</button>'
                : ""
            }
            <button class="drawer-close" type="button" data-drawer-close aria-label="Close detail drawer">×</button>
          </div>
        </header>
        <div class="drawer-toolbar">
          <span class="drawer-status">${escapeHtml(drawer.status)}</span>
          <nav class="drawer-tabs" aria-label="Detail tabs">
            ${renderDrawerTabs(drawer)}
          </nav>
        </div>
        <div class="drawer-actions">
          ${renderDrawerActions(drawer.actions)}
        </div>
        <div class="drawer-body">
          ${renderDrawerBody(drawer)}
        </div>
      </section>
    </aside>
  `;
}

export function renderDrawerTabs(drawer) {
  return drawer.tabs
    .map(
      (tab) => `
        <button
          class="drawer-tab${tab.id === drawer.activeTab ? " is-active" : ""}"
          type="button"
          data-drawer-tab="${escapeHtml(tab.id)}"
          ${tab.id === drawer.activeTab ? 'aria-current="page"' : ""}
        >
          ${escapeHtml(tab.label)}
        </button>
      `
    )
    .join("");
}

export function renderDrawerActions(actions) {
  if (!actions.length) {
    return '<span class="drawer-action-placeholder">No actions</span>';
  }
  return actions
    .map(
      (action) => `
        <a class="drawer-action" href="${escapeHtml(action.href)}">${escapeHtml(action.label)}</a>
      `
    )
    .join("");
}

export function renderDrawerBody(drawer) {
  if (drawer.state === "loading") {
    return '<div class="drawer-state" data-drawer-loading>Loading detail</div>';
  }
  if (drawer.state === "empty") {
    return '<div class="drawer-state" data-drawer-empty>No detail selected</div>';
  }
  if (drawer.state === "error") {
    return `<div class="drawer-state is-error" data-drawer-error>${escapeHtml(
      drawer.error ?? "Unable to load detail"
    )}</div>`;
  }
  return drawer.content || '<div class="drawer-state" data-drawer-empty>No content</div>';
}

export function drawerDeepLink(drawer) {
  if (!drawer.open || !drawer.kind || !drawer.resourceId) {
    return "";
  }
  const params = new URLSearchParams();
  params.set("drawer", drawer.kind);
  params.set("id", drawer.resourceId);
  if (drawer.activeTab) {
    params.set("tab", drawer.activeTab);
  }
  return `?${params.toString()}`;
}

export function drawerFromDeepLink(search) {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const kind = params.get("drawer");
  const resourceId = params.get("id");
  if (!kind || !resourceId) {
    return createClosedDrawerState();
  }
  return openDrawer({
    kind,
    resourceId,
    title: "Loading detail",
    subtitle: resourceId,
    status: "Loading",
    activeTab: params.get("tab") ?? "overview",
    state: "loading"
  });
}

export function handleDrawerKeydown(event, drawer) {
  if (drawer.open && event.key === "Escape") {
    event.preventDefault?.();
    return closeDrawer();
  }
  return drawer;
}

export function focusTargetForDrawer(drawer) {
  return drawer.open ? "[data-drawer-close]" : ".content-region";
}

function snapshotDrawer(drawer) {
  return {
    ...drawer,
    backStack: []
  };
}
