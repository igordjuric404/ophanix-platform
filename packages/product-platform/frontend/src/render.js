import { DEFAULT_ROUTE, LOGIN_ROUTE, PRODUCT_ROUTES, findRoute, normalizePath, routeGroups } from "./navigation.js";
import { canAccessRoute } from "./permissions.js";
import { createInitialAppState, guardRoute } from "./state.js";
import { renderDrawer } from "./drawers.js";
import { escapeHtml } from "./html.js";

export { escapeHtml };

export function renderPlaceholderPage(route) {
  return `
    <section class="page-heading" data-route-page="${escapeHtml(route.path)}">
      <p class="section-label">${escapeHtml(route.area)}</p>
      <h1>${escapeHtml(route.label)}</h1>
      <p>${escapeHtml(route.description)}</p>
    </section>
    <section class="placeholder-grid" aria-label="${escapeHtml(route.label)} workspace">
      <article class="workspace-panel">
        <h2>Primary Workspace</h2>
        <p>Feature-specific content for ${escapeHtml(route.label)} will render inside this stable shell.</p>
      </article>
      <article class="workspace-panel">
        <h2>Operational Context</h2>
        <p>Environment, health, permissions, and shared drawers stay consistent across this route.</p>
      </article>
    </section>
  `;
}

export function renderNotFoundPage(pathname) {
  return `
    <section class="page-heading" data-route-page="not-found">
      <p class="section-label">Route</p>
      <h1>Page Not Found</h1>
      <p>No product section is registered for ${escapeHtml(pathname)}.</p>
    </section>
  `;
}

export function renderAuthRequiredPage() {
  return `
    <section class="page-heading" data-route-page="${LOGIN_ROUTE}" data-auth-required>
      <p class="section-label">Authentication</p>
      <h1>Sign In Required</h1>
      <p>The product shell is ready, but an authenticated platform session is required before loading tenant data.</p>
    </section>
  `;
}

export function renderAccessDeniedPage(pathname) {
  return `
    <section class="page-heading" data-route-page="access-denied" data-access-denied>
      <p class="section-label">Access</p>
      <h1>Access Denied</h1>
      <p>Your current role does not include the permission required for ${escapeHtml(pathname)}.</p>
    </section>
  `;
}

export function renderTenantSelector(state) {
  const environments = state.environments ?? [];
  const selectedId = state.selectedEnvironment?.id ?? "";
  const disabled = state.authStatus !== "authenticated" || environments.length === 0;
  const options =
    environments.length > 0
      ? environments
          .map(
            (environment) => `
              <option value="${escapeHtml(environment.id)}" ${environment.id === selectedId ? "selected" : ""}>
                ${escapeHtml(environment.name)}
              </option>
            `
          )
          .join("")
      : '<option value="">No environment</option>';

  return `
    <label class="tenant-context">
      <span class="context-label">Environment</span>
      <select class="context-button" data-environment-selector ${disabled ? "disabled" : ""}>
        ${options}
      </select>
    </label>
  `;
}

export function renderCurrentUser(state) {
  if (state.authStatus === "loading") {
    return '<span class="user-chip">Loading session</span>';
  }
  if (state.authStatus === "unauthenticated") {
    return '<span class="user-chip is-warning">Signed out</span>';
  }
  if (state.authStatus === "error") {
    return '<span class="user-chip is-warning">Context warning</span>';
  }
  return `<span class="user-chip">${escapeHtml(state.currentUser?.display_name ?? "User")}</span>`;
}

export function renderSystemStatus(state) {
  const systemStatus = state.systemStatus ?? { status: "warning", dependencies: [], message: "Unknown" };
  const label =
    systemStatus.status === "healthy"
      ? "Healthy"
      : systemStatus.status === "degraded"
        ? "Degraded"
        : "Warning";
  const dependencies = systemStatus.dependencies ?? [];
  const version = systemStatus.version;
  const dependencyRows =
    dependencies.length > 0
      ? dependencies
          .map(
            (dependency) => `
              <li>
                <span>${escapeHtml(dependency.name)}</span>
                <strong>${escapeHtml(dependency.status)}</strong>
              </li>
            `
          )
          .join("")
      : "<li><span>No dependencies</span><strong>n/a</strong></li>";

  return `
    <details class="status-menu status-${escapeHtml(systemStatus.status)}">
      <summary>${label}</summary>
      <div class="status-popover" role="tooltip">
        <p>${escapeHtml(systemStatus.message)}</p>
        <p>${escapeHtml(version?.app ?? "API")} ${escapeHtml(version?.version ?? "unknown")}</p>
        <ul>${dependencyRows}</ul>
      </div>
    </details>
  `;
}

export function renderNotificationCenter(state) {
  const notifications = state.notifications ?? [];
  return `
    <details class="notification-menu">
      <summary aria-label="Notifications">${notifications.length}</summary>
      <div class="notification-popover">
        <h2>Notifications</h2>
        <p>${notifications.length === 0 ? "No notifications" : `${notifications.length} notifications`}</p>
      </div>
    </details>
  `;
}

export function renderSideNav(currentPath, state = createInitialAppState()) {
  const normalized = normalizePath(currentPath);
  return routeGroups()
    .map(
      (group) => `
        <section class="nav-group" aria-label="${escapeHtml(group.area)}">
          <h2>${escapeHtml(group.area)}</h2>
          ${group.routes
            .map((route) => {
              const isActive = route.path === normalized;
              const isAllowed =
                state.authStatus !== "authenticated" || canAccessRoute(route.path, state.currentUser);
              if (!isAllowed) {
                return `
                  <span class="nav-link is-disabled" data-route-disabled="${escapeHtml(route.path)}" aria-disabled="true">
                    <span>${escapeHtml(route.label)}</span>
                  </span>
                `;
              }
              return `
                <a
                  class="nav-link${isActive ? " is-active" : ""}"
                  href="${escapeHtml(route.path)}"
                  data-route="${escapeHtml(route.path)}"
                  ${isActive ? 'aria-current="page"' : ""}
                >
                  <span>${escapeHtml(route.label)}</span>
                </a>
              `;
            })
            .join("")}
        </section>
      `
    )
    .join("");
}

export function renderShell({ currentPath = DEFAULT_ROUTE, state = createInitialAppState() } = {}) {
  const guarded = guardRoute(currentPath, state);
  const normalized = guarded.path;
  const route = normalized === LOGIN_ROUTE ? null : findRoute(normalized);
  const content =
    normalized === LOGIN_ROUTE
      ? renderAuthRequiredPage()
      : guarded.reason === "forbidden"
        ? renderAccessDeniedPage(normalized)
      : route
        ? renderPlaceholderPage(route)
        : renderNotFoundPage(normalized);

  return `
    <div class="app-shell" data-app-shell>
      <aside class="side-nav" aria-label="Product navigation">
        <a class="brand-mark" href="${DEFAULT_ROUTE}" data-route="${DEFAULT_ROUTE}" aria-label="Ophanix Overview">
          <span class="brand-symbol">O</span>
          <span>
            <strong>Ophanix</strong>
            <small>Governance Platform</small>
          </span>
        </a>
        <nav>${renderSideNav(normalized, state)}</nav>
      </aside>
      <div class="main-shell">
        <header class="top-bar">
          ${renderTenantSelector(state)}
          <label class="search-box">
            <span class="visually-hidden">Search product data</span>
            <input type="search" placeholder="Search agents, policies, tools, events">
          </label>
          <div class="header-actions" aria-label="Global actions">
            ${renderCurrentUser(state)}
            ${renderSystemStatus(state)}
            ${renderNotificationCenter(state)}
          </div>
        </header>
        <main class="content-region" tabindex="-1">
          ${content}
        </main>
      </div>
      ${renderDrawer(state.drawer)}
    </div>
  `;
}

export function renderRouteSummary() {
  return PRODUCT_ROUTES.map((route) => `${route.path} ${route.label}`).join("\n");
}
