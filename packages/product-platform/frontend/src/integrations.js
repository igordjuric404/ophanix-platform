import { escapeHtml } from "./html.js";

export function renderIntegrationsPage(state = {}) {
  const frameworks = state.integrationFrameworks ?? [];
  const instances = state.integrationFrameworkInstances ?? [];
  const linkedAgents = state.integrationFrameworkAgents ?? [];
  const credentials = state.providerCredentials ?? [];
  const healthChecks = state.integrationHealthChecks ?? [];
  const agents = state.agents ?? state.integrationAgents ?? [];
  return `
    <section class="page-heading" data-route-page="/integrations">
      <p class="section-label">Ecosystem</p>
      <h1>Integrations</h1>
      <p>Framework adapters, provider credentials, connector health, and linked agents.</p>
    </section>
    <section class="integrations-workspace" aria-label="Integrations workspace">
      ${renderFrameworkCatalogTable({ frameworks })}
      ${renderSetupSnippets({ frameworks })}
      ${renderConnectorInstanceForm({ frameworks })}
      ${renderConnectorInstancesTable({ instances })}
      ${renderLinkedAgentsTable({ linkedAgents, instances, agents })}
      ${renderProviderCredentialForm()}
      ${renderProviderCredentialsTable({ credentials })}
      ${renderHealthChecksTable({ healthChecks })}
    </section>
  `;
}

export function renderFrameworkCatalogTable({ frameworks = [] } = {}) {
  const rows = frameworks
    .map(
      (framework) => `
        <tr data-integration-framework-row="${escapeHtml(framework.id)}">
          <td><strong>${escapeHtml(framework.name)}</strong><small>${escapeHtml(framework.description)}</small></td>
          <td>${renderFrameworkSupportBadge(framework.status)}</td>
          <td>${escapeHtml((framework.supported_versions ?? []).join(", ") || "none")}</td>
          <td><code>${escapeHtml(framework.example_path ?? "none")}</code></td>
          <td><code data-integration-setup-snippet="${escapeHtml(framework.id)}">${escapeHtml(framework.setup_snippet ?? "none")}</code></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel integration-frameworks" data-integration-frameworks data-integration-framework-catalog>
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

export function renderFrameworkCatalog({ frameworks = [] } = {}) {
  return renderFrameworkCatalogTable({ frameworks });
}

export function renderFrameworkSupportBadge(status) {
  const normalized = String(status ?? "scaffold").trim() || "scaffold";
  return `<span class="status-pill integration-support-badge integration-support-${escapeHtml(normalized)}" data-integration-support="${escapeHtml(normalized)}">${escapeHtml(statusLabel(normalized))}</span>`;
}

export function renderSupportBadge(status) {
  return renderFrameworkSupportBadge(status);
}

function renderSetupSnippets({ frameworks = [] } = {}) {
  return `
    <article class="workspace-panel integration-setup" data-integration-setup>
      <h2>Setup Snippets</h2>
      ${
        frameworks.length
          ? `<table class="data-table">
              <thead><tr><th>Framework</th><th>Snippet</th><th>Docs</th></tr></thead>
              <tbody>
                ${frameworks
                  .map(
                    (framework) => `
                      <tr>
                        <td>${escapeHtml(framework.name)}</td>
                        <td><code data-integration-setup-snippet="${escapeHtml(framework.id)}">${escapeHtml(framework.setup_snippet ?? "")}</code></td>
                        <td>${framework.setup_doc_url ? `<a href="${escapeHtml(framework.setup_doc_url)}">Open</a>` : "n/a"}</td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state"><strong>No snippets</strong><span>Catalog is empty</span></div>'
      }
    </article>
  `;
}

export function renderConnectorInstanceForm({ frameworks = [] } = {}) {
  return `
    <article class="workspace-panel integration-instance-create" data-integration-instance-create>
      <h2>Connector Instance</h2>
      <form class="filter-bar" data-integration-instance-form>
        <label>
          Framework
          <select name="integration_id" required>
            ${frameworks
              .map((framework) => `<option value="${escapeHtml(framework.id)}">${escapeHtml(framework.name)}</option>`)
              .join("")}
          </select>
        </label>
        <label>Name<input name="name" required></label>
        <label>Status<input name="status" value="active"></label>
        <label>Config<textarea name="config_json" required rows="2">{}</textarea></label>
        <button type="submit">Create</button>
      </form>
    </article>
  `;
}

export function renderConnectorInstancesTable({ instances = [] } = {}) {
  return `
    <article class="workspace-panel integration-instances" data-integration-instances>
      <h2>Connector Instances</h2>
      ${
        instances.length
          ? `<table class="data-table">
              <thead><tr><th>Name</th><th>Framework</th><th>Status</th><th>Config</th></tr></thead>
              <tbody>
                ${instances
                  .map(
                    (instance) => `
                      <tr data-integration-instance-row="${escapeHtml(instance.id)}">
                        <td><strong>${escapeHtml(instance.name)}</strong><small>${escapeHtml(instance.id)}</small></td>
                        <td>${escapeHtml(instance.integration_name ?? instance.integration_id)}</td>
                        <td><span class="status-pill">${escapeHtml(instance.status)}</span></td>
                        <td><code>${escapeHtml(JSON.stringify(maskConfig(instance.config ?? {})))}</code></td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-integration-instance-empty><strong>No instances</strong><span>Create a connector</span></div>'
      }
    </article>
  `;
}

export function renderLinkedAgentsTable({ linkedAgents = [], instances = [], agents = [] } = {}) {
  const firstInstanceId = instances[0]?.id ?? "";
  return `
    <article class="workspace-panel integration-linked-agents" data-integration-linked-agents>
      <h2>Linked Agents</h2>
      ${
        firstInstanceId
          ? `<form class="filter-bar" data-integration-link-agent-form data-instance-id="${escapeHtml(firstInstanceId)}">
              <label>Agent
                <select name="agent_id" required>
                  ${agents
                    .map((agent) => `<option value="${escapeHtml(agent.id)}">${escapeHtml(agent.name ?? agent.id)}</option>`)
                    .join("")}
                </select>
              </label>
              <label>Framework ref<input name="framework_agent_ref" required></label>
              <label>SDK version<input name="sdk_version"></label>
              <button type="submit">Link</button>
            </form>`
          : ""
      }
      ${
        linkedAgents.length
          ? `<table class="data-table">
              <thead><tr><th>Agent</th><th>Connector</th><th>Ref</th><th>Telemetry</th><th>Policy</th><th></th></tr></thead>
              <tbody>
                ${linkedAgents
                  .map(
                    (link) => `
                      <tr data-integration-linked-agent-row="${escapeHtml(link.id)}">
                        <td><strong>${escapeHtml(link.agent_name ?? link.agent_id)}</strong><small>${escapeHtml(link.agent_id)}</small></td>
                        <td>${escapeHtml(link.integration_name ?? link.integration_instance_id)}</td>
                        <td><code>${escapeHtml(link.framework_agent_ref)}</code><small>${escapeHtml(link.sdk_version ?? "")}</small></td>
                        <td><span class="status-pill">${escapeHtml(link.telemetry_status)}</span></td>
                        <td><span class="status-pill">${escapeHtml(link.policy_coverage_status)}</span></td>
                        <td><button type="button" data-integration-unlink-agent="${escapeHtml(link.id)}">Unlink</button></td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-integration-linked-agent-empty><strong>No linked agents</strong><span>Link a connector</span></div>'
      }
    </article>
  `;
}

export function renderProviderCredentialForm() {
  return `
    <article class="workspace-panel integration-credential-create" data-provider-credential-create>
      <h2>Provider Credential</h2>
      <form class="filter-bar" data-provider-credential-form>
        <label>Name<input name="name" required></label>
        <label>Provider type<input name="provider_type" value="model_provider" required></label>
        <label>Secret<input type="password" name="secret_value" required autocomplete="off"></label>
        <button type="submit">Add</button>
      </form>
    </article>
  `;
}

export function renderProviderCredentialsTable({ credentials = [] } = {}) {
  return `
    <article class="workspace-panel integration-credentials" data-provider-credentials>
      <h2>Provider Credentials</h2>
      ${
        credentials.length
          ? `<table class="data-table">
              <thead><tr><th>Name</th><th>Provider</th><th>Secret</th><th>Status</th><th></th></tr></thead>
              <tbody>
                ${credentials
                  .map(
                    (credential) => `
                      <tr data-provider-credential-row="${escapeHtml(credential.id)}">
                        <td><strong>${escapeHtml(credential.name)}</strong><small>${escapeHtml(credential.id)}</small></td>
                        <td>${escapeHtml(credential.provider_type)}</td>
                        <td><code>${escapeHtml(credential.masked_secret ?? "********")}</code></td>
                        <td><span class="status-pill">${escapeHtml(credential.status)}</span></td>
                        <td><button type="button" data-provider-credential-test="${escapeHtml(credential.id)}">Test</button></td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-provider-credential-empty><strong>No credentials</strong><span>Add a provider key</span></div>'
      }
    </article>
  `;
}

export function renderHealthChecksTable({ healthChecks = [] } = {}) {
  return `
    <article class="workspace-panel integration-health" data-integration-health>
      <h2>Health Checks</h2>
      ${
        healthChecks.length
          ? `<table class="data-table">
              <thead><tr><th>Target</th><th>Status</th><th>Latency</th><th>Message</th><th>Remediation</th></tr></thead>
              <tbody>
                ${healthChecks
                  .map(
                    (check) => `
                      <tr data-integration-health-row="${escapeHtml(check.id)}">
                        <td>${escapeHtml(check.target_type)}<small>${escapeHtml(check.target_id)}</small></td>
                        <td><span class="status-pill">${escapeHtml(check.status)}</span></td>
                        <td>${check.latency_ms ?? "n/a"}</td>
                        <td>${escapeHtml(check.message ?? "")}</td>
                        <td data-health-remediation>${escapeHtml(remediationFor(check))}</td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : '<div class="empty-state" data-integration-health-empty><strong>No health checks</strong><span>Run a provider test</span></div>'
      }
    </article>
  `;
}

export function integrationInstancePayloadFromValues(values = {}) {
  return {
    integration_id: requiredString(values.integration_id, "integration_id"),
    name: requiredString(values.name, "name"),
    status: optionalString(values.status) || "active",
    config: parseJsonObject(values.config_json, "config_json")
  };
}

export function integrationInstancePayloadFromForm(form) {
  return integrationInstancePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function integrationAgentLinkPayloadFromValues(values = {}) {
  return {
    agent_id: requiredString(values.agent_id, "agent_id"),
    framework_agent_ref: requiredString(values.framework_agent_ref, "framework_agent_ref"),
    sdk_version: optionalString(values.sdk_version)
  };
}

export function integrationAgentLinkPayloadFromForm(form) {
  return integrationAgentLinkPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function providerCredentialPayloadFromValues(values = {}) {
  return {
    name: requiredString(values.name, "name"),
    provider_type: requiredString(values.provider_type, "provider_type"),
    secret_value: requiredString(values.secret_value, "secret_value")
  };
}

export function providerCredentialPayloadFromForm(form) {
  return providerCredentialPayloadFromValues(Object.fromEntries(new FormData(form)));
}

function requiredString(value, fieldName) {
  const trimmed = optionalString(value);
  if (!trimmed) {
    throw new Error(`${fieldName} is required.`);
  }
  return trimmed;
}

function optionalString(value) {
  return String(value ?? "").trim();
}

function parseJsonObject(value, fieldName) {
  try {
    const parsed = JSON.parse(String(value ?? "{}"));
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      throw new Error("not object");
    }
    return parsed;
  } catch (error) {
    throw new Error(`${fieldName} must be a JSON object.`);
  }
}

function maskConfig(config) {
  const masked = {};
  for (const [key, value] of Object.entries(config)) {
    masked[key] = key.toLowerCase().includes("secret") || key.toLowerCase().includes("token")
      ? "********"
      : value;
  }
  return masked;
}

function remediationFor(check) {
  if (check.status === "healthy") {
    return "No action needed";
  }
  if (check.target_type === "provider_credential") {
    return "Check secret reference and provider configuration";
  }
  return "Review connector configuration and retry";
}

function statusLabel(status) {
  return status
    .split("_")
    .map((part, index) => (index === 0 ? part.charAt(0).toUpperCase() + part.slice(1) : part))
    .join(" ");
}
