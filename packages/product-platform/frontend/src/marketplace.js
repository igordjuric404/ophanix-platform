import { escapeHtml } from "./html.js";

export function renderMarketplacePage(state) {
  const plugins = state?.marketplacePlugins ?? [];
  const selectedPlugin = state?.selectedMarketplacePlugin ?? plugins[0] ?? null;
  const installations = state?.marketplaceInstallations ?? [];
  const policyResult = state?.marketplacePolicyResult ?? null;
  const reviews = state?.marketplaceReviews ?? [];
  const signingKeys = state?.marketplaceSigningKeys ?? [];
  const qualityAssessment = state?.marketplaceQualityAssessment ?? null;
  const trustEvents = state?.marketplaceTrustEvents ?? [];
  const selectedEnvironmentId = state?.selectedEnvironment?.id ?? "env_default";
  const selectedVersion = selectedPlugin?.versions?.[0] ?? null;
  return `
    <section class="page-heading" data-route-page="/marketplace">
      <p class="section-label">Ecosystem</p>
      <h1>Marketplace</h1>
      <p>Agent and integration catalog, evaluations, install flow, and attestations.</p>
    </section>
    <section class="marketplace-workspace" aria-label="Marketplace workspace">
      ${renderMarketplaceCatalogPanel({ plugins, selectedPluginId: selectedPlugin?.id ?? null })}
      ${renderMarketplacePluginDetail({ plugin: selectedPlugin, policyResult })}
      ${renderMarketplaceInstallWizard({ plugin: selectedPlugin, policyResult, selectedEnvironmentId })}
      ${renderMarketplaceInstalledPanel({ installations })}
      ${renderMarketplaceReviewQueue({ reviews })}
      ${renderMarketplaceSigningKeysPanel({ signingKeys })}
      ${renderMarketplaceQualityPanel({ version: selectedVersion, assessment: qualityAssessment })}
      ${renderMarketplaceTrustHistory({ version: selectedVersion, events: trustEvents })}
    </section>
  `;
}

export function renderMarketplaceCatalogPanel({ plugins = [], selectedPluginId = null } = {}) {
  const rows = plugins
    .map((plugin) => {
      const latest = plugin.versions?.[0];
      return `
        <tr data-marketplace-plugin-row="${escapeHtml(plugin.id)}">
          <td><strong>${escapeHtml(plugin.name)}</strong><small>${escapeHtml(plugin.description)}</small></td>
          <td>${escapeHtml(plugin.publisher)}</td>
          <td><span class="status-pill">${escapeHtml(plugin.plugin_type)}</span></td>
          <td>${escapeHtml(latest?.version ?? "none")}</td>
          <td><span class="status-pill">${escapeHtml(latest?.signature_status ?? "unknown")}</span></td>
          <td>
            <button
              type="button"
              data-marketplace-plugin-open="${escapeHtml(plugin.id)}"
              ${plugin.id === selectedPluginId ? "disabled" : ""}
            >Details</button>
          </td>
        </tr>
      `;
    })
    .join("");
  return `
    <article class="workspace-panel marketplace-catalog" data-marketplace-catalog>
      <header class="panel-header">
        <div>
          <p class="section-label">Catalog</p>
          <h2>Plugin Catalog</h2>
        </div>
      </header>
      ${
        plugins.length
          ? `<table class="data-table">
              <thead><tr><th>Plugin</th><th>Publisher</th><th>Type</th><th>Version</th><th>Signature</th><th>Action</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-marketplace-catalog-empty><strong>No plugins</strong><span>Import manifests</span></div>'
      }
    </article>
  `;
}

export function renderMarketplacePluginDetail({ plugin = null, policyResult = null } = {}) {
  if (!plugin) {
    return `
      <article class="workspace-panel marketplace-detail" data-marketplace-detail-empty>
        <h2>Plugin Detail</h2>
        <p>No plugin selected.</p>
      </article>
    `;
  }
  const version = plugin.versions?.[0] ?? null;
  const versionRows = (plugin.versions ?? [])
    .map(
      (item) => `
        <tr data-marketplace-version-row="${escapeHtml(item.id)}">
          <td>${escapeHtml(item.version)}</td>
          <td><span class="status-pill">${escapeHtml(item.signature_status)}</span></td>
          <td>${escapeHtml(item.trust_tier)}</td>
          <td>${escapeHtml(String(item.quality_score ?? 0))}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel marketplace-detail" data-marketplace-detail="${escapeHtml(plugin.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Plugin Detail</p>
          <h2>${escapeHtml(plugin.name)}</h2>
        </div>
        <span class="status-pill">${escapeHtml(plugin.status)}</span>
      </header>
      <dl class="detail-list">
        <div><dt>Publisher</dt><dd>${escapeHtml(plugin.publisher)}</dd></div>
        <div><dt>Type</dt><dd>${escapeHtml(plugin.plugin_type)}</dd></div>
        <div><dt>Package</dt><dd>${escapeHtml(version?.package_ref ?? "none")}</dd></div>
        <div><dt>Policy</dt><dd>${escapeHtml(policyResult?.result ?? "not_checked")}</dd></div>
      </dl>
      ${
        version
          ? `<div class="marketplace-governance-actions">
              <form class="inline-actions" data-marketplace-submit-review-form data-version-id="${escapeHtml(version.id)}">
                <input type="hidden" name="code" value="manual_review">
                <input name="message" value="Manual review requested" required>
                <button type="submit">Submit Review</button>
              </form>
              <button type="button" data-marketplace-assess-quality="${escapeHtml(version.id)}">Assess Quality</button>
            </div>`
          : ""
      }
      <h3>Permissions</h3>
      ${renderTagList(version?.permissions ?? [], "No permissions declared")}
      <h3>Required Capabilities</h3>
      ${renderTagList(version?.required_capabilities ?? [], "No capabilities declared")}
      <h3>Versions</h3>
      <table class="data-table">
        <thead><tr><th>Version</th><th>Signature</th><th>Trust</th><th>Quality</th></tr></thead>
        <tbody>${versionRows}</tbody>
      </table>
      <h3>Manifest</h3>
      <pre data-marketplace-manifest>${escapeHtml(JSON.stringify(version?.manifest ?? {}, null, 2))}</pre>
    </article>
  `;
}

export function renderMarketplaceInstallWizard({
  plugin = null,
  policyResult = null,
  selectedEnvironmentId = "env_default"
} = {}) {
  const version = plugin?.versions?.[0] ?? null;
  const denied = policyResult?.result === "deny";
  const findings = policyResult?.findings ?? [];
  if (!plugin || !version) {
    return `
      <article class="workspace-panel marketplace-install" data-marketplace-install-empty>
        <h2>Install</h2>
        <p>Select a plugin version before installation.</p>
      </article>
    `;
  }
  return `
    <article class="workspace-panel marketplace-install" data-marketplace-install-wizard="${escapeHtml(version.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Install</p>
          <h2>Install Wizard</h2>
        </div>
        <span class="status-pill">${escapeHtml(policyResult?.result ?? "not_checked")}</span>
      </header>
      <form class="bridge-form-grid" data-marketplace-policy-check-form data-version-id="${escapeHtml(version.id)}">
        <label class="checkbox-row"><input name="require_signature" type="checkbox" checked><span>Require signature</span></label>
        <label class="checkbox-row"><input name="require_review_approval" type="checkbox" checked><span>Require review approval</span></label>
        <label><span>Allowed Types</span><input name="allowed_plugin_types" value="${escapeHtml(plugin.plugin_type)}"></label>
        <label><span>Allowed Capabilities</span><input name="allowed_capabilities" value="${escapeHtml((version.required_capabilities ?? []).join(", "))}"></label>
        <button type="submit">Check Policy</button>
      </form>
      ${renderMarketplaceInstallGates({ version, policyResult })}
      ${
        findings.length
          ? `<ul class="finding-list" data-marketplace-policy-findings>${findings
              .map((finding) => `<li><strong>${escapeHtml(finding.code)}</strong><span>${escapeHtml(finding.message)}</span></li>`)
              .join("")}</ul>`
          : '<p data-marketplace-policy-empty>No blocking findings from the latest policy check.</p>'
      }
      <form class="bridge-form-grid" data-marketplace-install-form>
        <input type="hidden" name="plugin_version_id" value="${escapeHtml(version.id)}">
        <label><span>Environment</span><input name="environment_id" value="${escapeHtml(selectedEnvironmentId)}" required></label>
        <label><span>Target Agent</span><input name="target_agent_id"></label>
        <button type="submit" ${denied ? "disabled" : ""}>Install</button>
      </form>
    </article>
  `;
}

export function renderMarketplaceInstallGates({ version = null, policyResult = null } = {}) {
  if (!version) {
    return "";
  }
  const reviewRequired = Boolean(version.manifest?.review_required);
  const reviewDenied = (policyResult?.findings ?? []).some((finding) => finding.code === "review_not_approved");
  const signatureDenied = (policyResult?.findings ?? []).some((finding) => finding.code === "signature_required");
  const trustBlocked = ["unrated", "experimental"].includes(version.trust_tier);
  const gates = [
    {
      label: "Signature",
      status: signatureDenied ? "blocked" : version.signature_status,
      message: signatureDenied ? "A valid signature is required." : "Signature status is visible before install."
    },
    {
      label: "Review",
      status: reviewDenied ? "blocked" : reviewRequired ? "required" : "optional",
      message: reviewDenied
        ? "Marketplace review approval is required."
        : reviewRequired
          ? "Reviewer approval is expected before install."
          : "Review is not required by this manifest."
    },
    {
      label: "Trust",
      status: trustBlocked ? "watch" : version.trust_tier,
      message: `Current trust tier is ${version.trust_tier}.`
    },
    {
      label: "Quality",
      status: String(version.quality_score ?? 0),
      message: `Latest quality score is ${version.quality_score ?? 0}.`
    }
  ];
  return `
    <ul class="marketplace-gate-list" data-marketplace-install-gates>
      ${gates
        .map(
          (gate) => `
            <li>
              <strong>${escapeHtml(gate.label)}</strong>
              <span class="status-pill">${escapeHtml(gate.status)}</span>
              <small>${escapeHtml(gate.message)}</small>
            </li>
          `
        )
        .join("")}
    </ul>
  `;
}

export function renderMarketplaceInstalledPanel({ installations = [] } = {}) {
  const rows = installations
    .map(
      (installation) => `
        <tr data-marketplace-installation-row="${escapeHtml(installation.id)}">
          <td><strong>${escapeHtml(installation.plugin_name)}</strong><small>${escapeHtml(installation.version)}</small></td>
          <td>${escapeHtml(installation.environment_id)}</td>
          <td>${escapeHtml(installation.target_agent_name ?? installation.target_agent_id ?? "environment")}</td>
          <td><span class="status-pill">${escapeHtml(installation.status)}</span></td>
          <td>${escapeHtml(installation.installed_at)}</td>
          <td>
            <button
              type="button"
              data-marketplace-uninstall="${escapeHtml(installation.id)}"
              ${installation.status !== "installed" ? "disabled" : ""}
            >Uninstall</button>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel marketplace-installed" data-marketplace-installed>
      <header class="panel-header">
        <div>
          <p class="section-label">Installed</p>
          <h2>Installed Plugins</h2>
        </div>
      </header>
      ${
        installations.length
          ? `<table class="data-table">
              <thead><tr><th>Plugin</th><th>Environment</th><th>Target</th><th>Status</th><th>Installed</th><th>Action</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-marketplace-installed-empty><strong>No installations</strong><span>Install approved plugins</span></div>'
      }
    </article>
  `;
}

export function renderMarketplaceQualitySummary({ assessment = null } = {}) {
  if (!assessment) {
    return '<div class="empty-state" data-marketplace-quality-empty><strong>No quality assessment</strong><span>Run assessment</span></div>';
  }
  const findings = assessment.findings ?? [];
  return `
    <section data-marketplace-quality-summary="${escapeHtml(assessment.id)}">
      <div class="metric-grid">
        <div><span>Score</span><strong>${escapeHtml(String(assessment.score))}</strong></div>
        <div><span>Findings</span><strong>${escapeHtml(String(findings.length))}</strong></div>
      </div>
      ${
        findings.length
          ? `<ul class="finding-list" data-marketplace-quality-findings>${findings
              .map((finding) => `<li><strong>${escapeHtml(finding.code)}</strong><span>${escapeHtml(finding.message)}</span></li>`)
              .join("")}</ul>`
          : '<p data-marketplace-quality-clean>No quality warnings.</p>'
      }
    </section>
  `;
}

export function renderMarketplaceQualityPanel({ version = null, assessment = null } = {}) {
  return `
    <article class="workspace-panel marketplace-quality" data-marketplace-quality-tab>
      <header class="panel-header">
        <div>
          <p class="section-label">Quality</p>
          <h2>Quality Signals</h2>
        </div>
        ${
          version
            ? `<button type="button" data-marketplace-assess-quality="${escapeHtml(version.id)}">Assess</button>`
            : ""
        }
      </header>
      ${renderMarketplaceQualitySummary({ assessment })}
    </article>
  `;
}

export function renderMarketplaceReviewQueue({ reviews = [] } = {}) {
  const rows = reviews
    .map(
      (review) => `
        <tr data-marketplace-review-row="${escapeHtml(review.id)}">
          <td><strong>${escapeHtml(review.plugin_name ?? review.plugin_version_id)}</strong><small>${escapeHtml(review.version ?? "")}</small></td>
          <td><span class="status-pill">${escapeHtml(review.status)}</span></td>
          <td>${escapeHtml(review.reviewer_id ?? "unassigned")}</td>
          <td>${escapeHtml(review.decision_reason ?? "pending")}</td>
          <td>
            <form class="inline-actions" data-marketplace-review-approve-form data-review-id="${escapeHtml(review.id)}">
              <input name="decision_reason" placeholder="Reason" required>
              <button type="submit">Approve</button>
            </form>
            <form class="inline-actions" data-marketplace-review-reject-form data-review-id="${escapeHtml(review.id)}">
              <input name="decision_reason" placeholder="Reason" required>
              <button type="submit">Reject</button>
            </form>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel marketplace-reviews" data-marketplace-reviews>
      <header class="panel-header">
        <div>
          <p class="section-label">Reviews</p>
          <h2>Review Queue</h2>
        </div>
      </header>
      ${
        reviews.length
          ? `<table class="data-table">
              <thead><tr><th>Plugin</th><th>Status</th><th>Reviewer</th><th>Decision</th><th>Actions</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-marketplace-reviews-empty><strong>No reviews</strong><span>Submit a plugin version</span></div>'
      }
    </article>
  `;
}

export function renderMarketplaceSigningKeysPanel({ signingKeys = [] } = {}) {
  const rows = signingKeys
    .map(
      (key) => `
        <tr data-marketplace-signing-key-row="${escapeHtml(key.id)}">
          <td><strong>${escapeHtml(key.name)}</strong><small>${escapeHtml(key.public_key)}</small></td>
          <td><span class="status-pill">${escapeHtml(key.status)}</span></td>
          <td>${escapeHtml(key.created_by)}</td>
          <td>${escapeHtml(key.revoked_at ?? "active")}</td>
          <td>
            <button
              type="button"
              data-marketplace-signing-key-revoke="${escapeHtml(key.id)}"
              ${key.status !== "active" ? "disabled" : ""}
            >Revoke</button>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel marketplace-signing-keys" data-marketplace-signing-keys>
      <header class="panel-header">
        <div>
          <p class="section-label">Signing</p>
          <h2>Signing Keys</h2>
        </div>
      </header>
      <form class="bridge-form-grid" data-marketplace-signing-key-form>
        <label><span>Name</span><input name="name" required></label>
        <label><span>Public Key</span><input name="public_key" required></label>
        <button type="submit">Add Key</button>
      </form>
      ${
        signingKeys.length
          ? `<table class="data-table">
              <thead><tr><th>Key</th><th>Status</th><th>Created By</th><th>Revoked</th><th>Action</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-marketplace-signing-keys-empty><strong>No keys</strong><span>Add a signing key</span></div>'
      }
    </article>
  `;
}

export function renderMarketplaceTrustHistory({ version = null, events = [] } = {}) {
  const rows = events
    .map(
      (event) => `
        <tr data-marketplace-trust-event-row="${escapeHtml(event.id)}">
          <td><strong>${escapeHtml(event.reason)}</strong><small>${escapeHtml(event.source_event_id ?? "manual")}</small></td>
          <td>${escapeHtml(String(event.delta))}</td>
          <td>${escapeHtml(String(event.score_before))} -> ${escapeHtml(String(event.score_after))}</td>
          <td><span class="status-pill">${escapeHtml(event.trust_tier)}</span></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel marketplace-trust" data-marketplace-trust>
      <header class="panel-header">
        <div>
          <p class="section-label">Trust</p>
          <h2>Usage Trust</h2>
        </div>
      </header>
      ${
        version
          ? `<form class="bridge-form-grid" data-marketplace-trust-recompute-form data-version-id="${escapeHtml(version.id)}">
              <label><span>Daily Active Users</span><input name="daily_active_users" type="number" min="0" value="1000"></label>
              <label><span>Total Invocations</span><input name="total_invocations" type="number" min="0" value="10000"></label>
              <label><span>Error Count</span><input name="error_count" type="number" min="0" value="20"></label>
              <label><span>Incident Count</span><input name="incident_count" type="number" min="0" value="0"></label>
              <label><span>Adoption Trend</span><input name="adoption_trend" type="number" step="0.1" value="0.6"></label>
              <label><span>Source Event</span><input name="source_event_id" value="manual_usage_rollup"></label>
              <button type="submit">Recompute Trust</button>
            </form>`
          : ""
      }
      ${
        events.length
          ? `<table class="data-table">
              <thead><tr><th>Reason</th><th>Delta</th><th>Score</th><th>Tier</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-marketplace-trust-empty><strong>No trust events</strong><span>Recompute usage trust</span></div>'
      }
    </article>
  `;
}

export function marketplacePolicyPayloadFromValues(values) {
  return {
    require_signature: Boolean(values.require_signature),
    require_review_approval: Boolean(values.require_review_approval),
    allowed_plugin_types: commaList(values.allowed_plugin_types),
    allowed_capabilities: commaList(values.allowed_capabilities)
  };
}

export function marketplacePolicyPayloadFromForm(form) {
  return marketplacePolicyPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function marketplaceInstallPayloadFromValues(values) {
  return {
    plugin_version_id: String(values.plugin_version_id ?? "").trim(),
    environment_id: String(values.environment_id ?? "").trim(),
    target_agent_id: optionalString(values.target_agent_id)
  };
}

export function marketplaceInstallPayloadFromForm(form) {
  return marketplaceInstallPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function marketplaceReviewSubmitPayloadFromValues(values) {
  const code = optionalString(values.code) ?? "manual_review";
  const message = optionalString(values.message) ?? "Manual review requested";
  return {
    findings: [
      {
        code,
        message
      }
    ]
  };
}

export function marketplaceReviewSubmitPayloadFromForm(form) {
  return marketplaceReviewSubmitPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function marketplaceReviewDecisionPayloadFromValues(values) {
  return {
    decision_reason: optionalString(values.decision_reason)
  };
}

export function marketplaceReviewDecisionPayloadFromForm(form) {
  return marketplaceReviewDecisionPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function marketplaceSigningKeyPayloadFromValues(values) {
  return {
    name: String(values.name ?? "").trim(),
    public_key: String(values.public_key ?? "").trim()
  };
}

export function marketplaceSigningKeyPayloadFromForm(form) {
  return marketplaceSigningKeyPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function marketplaceTrustPayloadFromValues(values) {
  return {
    daily_active_users: integerValue(values.daily_active_users),
    total_invocations: integerValue(values.total_invocations),
    error_count: integerValue(values.error_count),
    incident_count: integerValue(values.incident_count),
    days_since_update: integerValue(values.days_since_update),
    adoption_trend: numberValue(values.adoption_trend),
    source_event_id: optionalString(values.source_event_id)
  };
}

export function marketplaceTrustPayloadFromForm(form) {
  return marketplaceTrustPayloadFromValues(Object.fromEntries(new FormData(form)));
}

function renderTagList(items, emptyText) {
  if (!items.length) {
    return `<p>${escapeHtml(emptyText)}</p>`;
  }
  return `<div class="tag-list">${items.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>`;
}

function commaList(value) {
  const raw = String(value ?? "").trim();
  if (!raw) {
    return null;
  }
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function optionalString(value) {
  const normalized = String(value ?? "").trim();
  return normalized || null;
}

function integerValue(value) {
  const parsed = Number.parseInt(String(value ?? "0"), 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

function numberValue(value) {
  const parsed = Number.parseFloat(String(value ?? "0"));
  return Number.isFinite(parsed) ? parsed : 0;
}
