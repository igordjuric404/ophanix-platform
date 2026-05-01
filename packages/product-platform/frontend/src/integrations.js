import { escapeHtml } from "./html.js";

export function renderIntegrationsPage(state) {
  const frameworks = state?.integrationFrameworks ?? [];
  return `
    <section class="page-heading" data-route-page="/integrations">
      <p class="section-label">Ecosystem</p>
      <h1>Integrations</h1>
      <p>Framework adapters, setup snippets, connector instances, and linked agents.</p>
    </section>
    <section class="integrations-workspace" aria-label="Integrations workspace">
      ${renderFrameworkCatalog({ frameworks })}
    </section>
  `;
}

export function renderFrameworkCatalog({ frameworks = [] } = {}) {
  const rows = frameworks
    .map(
      (framework) => `
        <tr data-integration-framework-row="${escapeHtml(framework.id)}">
          <td><strong>${escapeHtml(framework.name)}</strong><small>${escapeHtml(framework.description)}</small></td>
          <td>${renderSupportBadge(framework.status)}</td>
          <td>${renderVersionTags(framework.supported_versions ?? [])}</td>
          <td><code>${escapeHtml(framework.example_path ?? "none")}</code></td>
          <td><code>${escapeHtml(framework.setup_snippet ?? "none")}</code></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel integration-frameworks" data-integration-frameworks>
      <header class="panel-header">
        <div>
          <p class="section-label">Frameworks</p>
          <h2>Supported Frameworks</h2>
        </div>
      </header>
      ${
        frameworks.length
          ? `<table class="data-table">
              <thead><tr><th>Framework</th><th>Support</th><th>Versions</th><th>Example</th><th>Setup</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-integration-framework-empty><strong>No frameworks</strong><span>Seed the framework catalog</span></div>'
      }
    </article>
  `;
}

export function renderSupportBadge(status) {
  const normalized = String(status ?? "scaffold").trim() || "scaffold";
  return `<span class="status-pill integration-support-badge" data-integration-support="${escapeHtml(normalized)}">${escapeHtml(statusLabel(normalized))}</span>`;
}

function renderVersionTags(versions) {
  if (!versions.length) {
    return '<span class="muted">none</span>';
  }
  return `<div class="tag-list">${versions.map((version) => `<span>${escapeHtml(version)}</span>`).join("")}</div>`;
}

function statusLabel(status) {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
