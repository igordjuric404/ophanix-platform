import { escapeHtml } from "./html.js";

export function renderTrustPage(state) {
  const scores = state?.trustScores ?? [];
  const events = state?.trustEvents ?? [];
  const rules = state?.trustRules ?? [];
  const cards = state?.trustCards ?? [];
  const thresholds = state?.trustThresholds ?? [];
  const handshakes = state?.trustHandshakes ?? [];
  const selectedCard = state?.selectedTrustCard ?? cards[0] ?? null;
  const selectedHandshake = state?.selectedTrustHandshake ?? handshakes[0] ?? null;
  return `
    <section class="page-heading" data-route-page="/trust">
      <p class="section-label">Governance</p>
      <h1>Trust</h1>
      <p>Trust score trends, dimensions, tiers, changes, and explainability.</p>
    </section>
    <section class="trust-workspace" aria-label="Trust workspace">
      ${renderTrustOverviewCards(scores)}
      ${renderTrustLeaderboard(scores)}
      ${renderTrustScoreTrend(events)}
      ${renderTrustScoreEvents({ events, dimensionFilter: state?.trustEventFilter?.dimension ?? "" })}
      ${renderTrustCardsPanel({
        cards,
        selectedCard,
        verification: state?.trustCardVerification ?? null
      })}
      ${renderTrustThresholdsPanel(thresholds)}
      ${renderTrustHandshakesPanel({
        handshakes,
        selectedHandshake,
        filters: state?.trustHandshakeFilter ?? {},
        simulation: state?.trustHandshakeSimulation ?? null
      })}
      ${renderTrustRulesPanel(rules)}
    </section>
  `;
}

export function renderTrustOverviewCards(scores = []) {
  const average = scores.length
    ? Math.round(scores.reduce((total, score) => total + Number(score.score ?? 0), 0) / scores.length)
    : 0;
  const trustedCount = scores.filter((score) =>
    ["trusted", "verified_partner"].includes(score.tier)
  ).length;
  return `
    <section class="trust-summary" data-trust-summary>
      ${summaryCard("Average Score", String(average || "n/a"))}
      ${summaryCard("Trusted Agents", String(trustedCount))}
      ${summaryCard("Signals", String(scores.reduce((total, score) => total + dimensionSignals(score), 0)))}
    </section>
  `;
}

export function renderTrustLeaderboard(scores = []) {
  const rows = scores
    .map(
      (score) => `
        <tr data-trust-score-row="${escapeHtml(score.agent_id)}">
          <td><strong>${escapeHtml(score.agent_name ?? score.agent_id)}</strong><small>${escapeHtml(score.agent_id)}</small></td>
          <td><span class="score-meter"><span style="width: ${scoreWidth(score.score)}%"></span></span><strong>${escapeHtml(String(score.score))}</strong></td>
          <td><span class="status-pill">${escapeHtml(score.tier)}</span></td>
          <td>${escapeHtml(score.calculated_at)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel trust-leaderboard" data-trust-leaderboard>
      <header class="panel-header">
        <div>
          <p class="section-label">Leaderboard</p>
          <h2>Agent Trust Scores</h2>
        </div>
        <button type="button" class="primary-action" data-trust-recalculate>Recalculate</button>
      </header>
      ${
        scores.length
          ? `<table class="data-table">
              <thead>
                <tr><th>Agent</th><th>Score</th><th>Tier</th><th>Calculated</th></tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-trust-leaderboard-empty><strong>No scores</strong><span>Recalculate</span></div>'
      }
    </article>
  `;
}

export function renderTrustScoreTrend(events = []) {
  const ordered = [...events].reverse().slice(-8);
  return `
    <article class="workspace-panel trust-trend" data-trust-score-trend>
      <header class="panel-header">
        <div>
          <p class="section-label">Trend</p>
          <h2>Score Movement</h2>
        </div>
      </header>
      ${
        ordered.length
          ? `<ol class="trend-list">${ordered
              .map(
                (event) => `
                  <li>
                    <span>${escapeHtml(event.dimension)}</span>
                    <strong>${escapeHtml(formatDelta(event.delta))}</strong>
                    <small>${escapeHtml(String(event.score_after))}</small>
                  </li>
                `
              )
              .join("")}</ol>`
          : '<div class="empty-state"><strong>No score movement</strong><span>Awaiting signals</span></div>'
      }
    </article>
  `;
}

export function renderTrustScoreEvents({ events = [], dimensionFilter = "" } = {}) {
  const filtered = dimensionFilter
    ? events.filter((event) => event.dimension === dimensionFilter)
    : events;
  const rows = filtered
    .map(
      (event) => `
        <tr data-trust-event-row="${escapeHtml(event.id)}">
          <td><strong>${escapeHtml(event.agent_name ?? event.agent_id)}</strong><small>${escapeHtml(event.agent_id)}</small></td>
          <td>${escapeHtml(event.dimension)}</td>
          <td>${escapeHtml(formatDelta(event.delta))}</td>
          <td>${escapeHtml(event.reason)}</td>
          <td>${event.source_event_id ? `<button type="button" data-related-event-id="${escapeHtml(event.source_event_id)}">${escapeHtml(event.source_event_id)}</button>` : "none"}</td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel trust-events" data-trust-score-events>
      <header class="panel-header">
        <div>
          <p class="section-label">Events</p>
          <h2>Score Events</h2>
        </div>
      </header>
      <form class="filter-bar" data-trust-events-filter>
        <label>
          <span>Dimension</span>
          <select name="dimension">
            <option value="">Any</option>
            ${["policy_compliance", "security_posture", "resource_efficiency", "output_quality", "collaboration_health"]
              .map(
                (dimension) => `
                  <option value="${escapeHtml(dimension)}" ${dimension === dimensionFilter ? "selected" : ""}>${escapeHtml(dimension)}</option>
                `
              )
              .join("")}
          </select>
        </label>
        <button type="submit">Filter</button>
      </form>
      ${
        filtered.length
          ? `<table class="data-table">
              <thead>
                <tr><th>Agent</th><th>Dimension</th><th>Delta</th><th>Reason</th><th>Source</th></tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-trust-events-empty><strong>No events</strong><span>Adjust filters</span></div>'
      }
    </article>
  `;
}

export function renderTrustRulesPanel(rules = []) {
  return `
    <article class="workspace-panel trust-rules" data-trust-rules>
      <header class="panel-header">
        <div>
          <p class="section-label">Rules</p>
          <h2>Signal Mapping</h2>
        </div>
      </header>
      <ul class="compact-list">
        ${rules
          .map(
            (rule) => `
              <li data-trust-rule-row="${escapeHtml(rule.id)}">
                <span>${escapeHtml(rule.event_type)}</span>
                <strong>${escapeHtml(rule.dimension)} ${escapeHtml(formatDelta(rule.delta))}</strong>
              </li>
            `
          )
          .join("") || '<li><span>No rules</span><strong>Seed defaults</strong></li>'}
      </ul>
    </article>
  `;
}

export function renderTrustCardsPanel({ cards = [], selectedCard = null, verification = null } = {}) {
  const rows = cards
    .map(
      (card) => `
        <tr data-trust-card-row="${escapeHtml(card.id)}">
          <td><strong>${escapeHtml(card.card?.name ?? card.agent_id)}</strong><small>${escapeHtml(card.agent_id)}</small></td>
          <td>${escapeHtml(card.issuer)}</td>
          <td><span class="status-pill">${escapeHtml(card.status)}</span></td>
          <td>${escapeHtml(card.valid_until)}</td>
          <td class="row-actions">
            <button type="button" data-trust-card-verify="${escapeHtml(card.id)}">Verify</button>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel trust-cards" data-trust-card-inventory>
      <header class="panel-header">
        <div>
          <p class="section-label">Trust Cards</p>
          <h2>Card Inventory</h2>
        </div>
      </header>
      <form class="filter-bar" data-trust-card-issue-form>
        <label>
          <span>Agent</span>
          <input name="agent_id" required placeholder="agent_">
        </label>
        <label>
          <span>Issuer</span>
          <input name="issuer" value="ophanix-demo-issuer" required>
        </label>
        <button type="submit">Issue</button>
      </form>
      ${
        cards.length
          ? `<table class="data-table">
              <thead>
                <tr><th>Agent</th><th>Issuer</th><th>Status</th><th>Valid Until</th><th>Actions</th></tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-trust-cards-empty><strong>No trust cards</strong><span>Issue card</span></div>'
      }
      ${renderTrustCardDetail({ card: selectedCard, verification })}
    </article>
  `;
}

export function renderTrustThresholdsPanel(thresholds = []) {
  const rows = thresholds
    .map(
      (threshold) => `
        <tr data-trust-threshold-row="${escapeHtml(threshold.id)}">
          <td><strong>${escapeHtml(threshold.threshold_type)}</strong><small>${escapeHtml(threshold.target_type)} ${escapeHtml(threshold.target_id ?? "default")}</small></td>
          <td>${escapeHtml(String(threshold.min_score))}</td>
          <td><span class="status-pill">${escapeHtml(threshold.required_tier)}</span></td>
          <td>${escapeHtml(threshold.enabled ? "enabled" : "disabled")}</td>
          <td>
            <form class="inline-form compact-inline-form" data-trust-threshold-patch-form data-threshold-id="${escapeHtml(threshold.id)}">
              <input name="min_score" type="number" min="0" max="1000" value="${escapeHtml(String(threshold.min_score))}" required>
              <select name="required_tier">
                ${["untrusted", "probationary", "standard", "trusted", "verified_partner"]
                  .map((tier) => `<option value="${escapeHtml(tier)}" ${tier === threshold.required_tier ? "selected" : ""}>${escapeHtml(tier)}</option>`)
                  .join("")}
              </select>
              <label class="checkbox-label"><input type="checkbox" name="enabled" ${threshold.enabled ? "checked" : ""}> Enabled</label>
              <button type="submit">Save</button>
            </form>
          </td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel trust-thresholds" data-trust-thresholds>
      <header class="panel-header">
        <div>
          <p class="section-label">Thresholds</p>
          <h2>Protected Actions</h2>
        </div>
      </header>
      <form class="filter-bar" data-trust-threshold-form>
        <label>
          <span>Type</span>
          <input name="threshold_type" required placeholder="handoff">
        </label>
        <label>
          <span>Target</span>
          <input name="target_type" value="environment" required>
        </label>
        <label>
          <span>Target ID</span>
          <input name="target_id" placeholder="optional">
        </label>
        <label>
          <span>Score</span>
          <input name="min_score" type="number" min="0" max="1000" value="700" required>
        </label>
        <label>
          <span>Tier</span>
          <select name="required_tier">
            <option value="standard">standard</option>
            <option value="trusted">trusted</option>
            <option value="verified_partner">verified_partner</option>
            <option value="probationary">probationary</option>
            <option value="untrusted">untrusted</option>
          </select>
        </label>
        <button type="submit">Create</button>
      </form>
      ${
        thresholds.length
          ? `<table class="data-table">
              <thead>
                <tr><th>Threshold</th><th>Score</th><th>Tier</th><th>Status</th><th>Edit</th></tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-trust-thresholds-empty><strong>No thresholds</strong><span>Seed defaults</span></div>'
      }
    </article>
  `;
}

export function renderTrustHandshakesPanel({
  handshakes = [],
  selectedHandshake = null,
  filters = {},
  simulation = null
} = {}) {
  const rows = handshakes
    .map(
      (handshake) => `
        <tr data-trust-handshake-row="${escapeHtml(handshake.id)}">
          <td><strong>${escapeHtml(handshake.source_agent_id)}</strong><small>to ${escapeHtml(handshake.target_agent_id)}</small></td>
          <td>${escapeHtml(handshake.purpose)}</td>
          <td><span class="status-pill">${escapeHtml(handshake.result)}</span></td>
          <td>${escapeHtml(handshake.reason)}</td>
          <td>${escapeHtml(String(handshake.required_score))}</td>
          <td><button type="button" data-handshake-detail-open="${escapeHtml(handshake.id)}">Details</button></td>
        </tr>
      `
    )
    .join("");
  return `
    <article class="workspace-panel trust-handshakes" data-trust-handshakes>
      <header class="panel-header">
        <div>
          <p class="section-label">Handshakes</p>
          <h2>Peer Attempts</h2>
        </div>
      </header>
      <form class="filter-bar" data-trust-handshake-filter>
        <label>
          <span>Source</span>
          <input name="source_agent_id" value="${escapeHtml(filters.source_agent_id ?? "")}">
        </label>
        <label>
          <span>Target</span>
          <input name="target_agent_id" value="${escapeHtml(filters.target_agent_id ?? "")}">
        </label>
        <label>
          <span>Result</span>
          <select name="result">
            <option value="">Any</option>
            <option value="allowed" ${filters.result === "allowed" ? "selected" : ""}>allowed</option>
            <option value="denied" ${filters.result === "denied" ? "selected" : ""}>denied</option>
          </select>
        </label>
        <button type="submit">Filter</button>
      </form>
      <form class="filter-bar" data-trust-handshake-simulate-form>
        <label>
          <span>Source</span>
          <input name="source_agent_id" required placeholder="agent_source">
        </label>
        <label>
          <span>Target</span>
          <input name="target_agent_id" required placeholder="agent_target">
        </label>
        <label>
          <span>Type</span>
          <input name="threshold_type" value="handoff" required>
        </label>
        <label>
          <span>Capabilities</span>
          <input name="required_capabilities" placeholder="claims:read,tools:run">
        </label>
        <label class="checkbox-label"><input type="checkbox" name="require_trust_card"> Card</label>
        <label class="checkbox-label"><input type="checkbox" name="require_active_credential"> Credential</label>
        <button type="submit">Simulate</button>
      </form>
      ${
        simulation
          ? `<p class="inline-status" data-trust-handshake-simulation>${escapeHtml(simulation.result)} ${escapeHtml(simulation.reason)}</p>`
          : ""
      }
      ${
        handshakes.length
          ? `<table class="data-table">
              <thead>
                <tr><th>Peers</th><th>Purpose</th><th>Result</th><th>Reason</th><th>Required</th><th>Detail</th></tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>`
          : '<div class="empty-state" data-trust-handshakes-empty><strong>No handshakes</strong><span>Run simulation</span></div>'
      }
      ${selectedHandshake ? renderHandshakeDetail(selectedHandshake) : ""}
    </article>
  `;
}

export function renderHandshakeDetail(handshake) {
  const metadata = JSON.stringify(handshake.metadata ?? {}, null, 2);
  return `
    <section class="handshake-detail" data-handshake-detail="${escapeHtml(handshake.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Handshake Detail</p>
          <h3>${escapeHtml(handshake.source_agent_id)} -> ${escapeHtml(handshake.target_agent_id)}</h3>
        </div>
        <span class="status-pill">${escapeHtml(handshake.result)}</span>
      </header>
      <dl class="metadata-grid">
        <dt>Reason</dt><dd>${escapeHtml(handshake.reason)}</dd>
        <dt>Required</dt><dd>${escapeHtml(String(handshake.required_score))} ${escapeHtml(handshake.required_tier)}</dd>
        <dt>Source Score</dt><dd>${escapeHtml(String(handshake.source_score))}</dd>
        <dt>Target Score</dt><dd>${escapeHtml(String(handshake.target_score))}</dd>
      </dl>
      <pre class="json-preview">${escapeHtml(metadata)}</pre>
    </section>
  `;
}

export function renderTrustCardDetail({ card = null, verification = null } = {}) {
  if (!card) {
    return '<div class="empty-state" data-trust-card-detail-empty><strong>No card selected</strong><span>Issue or select a card</span></div>';
  }
  const payload = JSON.stringify(card.card ?? {}, null, 2);
  return `
    <section class="trust-card-detail" data-trust-card-detail="${escapeHtml(card.id)}">
      <header class="panel-header">
        <div>
          <p class="section-label">Card Detail</p>
          <h3>${escapeHtml(card.card?.name ?? card.agent_id)}</h3>
        </div>
        <span class="status-pill">${escapeHtml(card.status)}</span>
      </header>
      ${card.status === "revoked" ? '<p class="inline-warning" data-trust-card-revoked>Revoked</p>' : ""}
      ${
        verification
          ? `<p class="inline-status" data-trust-card-verification>${escapeHtml(verification.verified ? "Verified" : "Invalid")} ${escapeHtml(verification.reason)}</p>`
          : ""
      }
      <dl class="metadata-grid">
        <dt>DID</dt><dd>${escapeHtml(card.card?.agent_did ?? "unknown")}</dd>
        <dt>Score</dt><dd>${escapeHtml(String(card.card?.metadata?.trust_score ?? Math.round(Number(card.card?.trust_score ?? 0) * 1000)))}</dd>
        <dt>Signature</dt><dd>${escapeHtml(card.signature.slice(0, 18))}</dd>
      </dl>
      <pre class="json-preview">${escapeHtml(payload)}</pre>
      <form class="inline-form" data-trust-card-revoke-form data-card-id="${escapeHtml(card.id)}">
        <label>
          <span>Reason</span>
          <input name="reason" required>
        </label>
        <button type="submit">Revoke</button>
      </form>
    </section>
  `;
}

export function renderCurrentTrustCardPanel(currentTrustCard = null) {
  if (!currentTrustCard?.card) {
    return `
      <div class="empty-state" data-current-trust-card-empty>
        <strong>No current card</strong>
        <span>${escapeHtml(currentTrustCard?.warning ?? "Issue trust card")}</span>
      </div>
    `;
  }
  return `
    <section data-current-trust-card>
      ${renderTrustCardDetail({ card: currentTrustCard.card })}
    </section>
  `;
}

export function renderAgentTrustTab({
  trustScore = null,
  trustEvents = [],
  currentTrustCard = null
} = {}) {
  if (!trustScore) {
    return '<div class="empty-state" data-agent-trust-empty><strong>No trust score</strong><span>Recalculate</span></div>';
  }
  return `
    <div class="agent-trust-tab" data-agent-trust-tab>
      <dl class="metadata-grid">
        <dt>Score</dt><dd>${escapeHtml(String(trustScore.score))}</dd>
        <dt>Tier</dt><dd>${escapeHtml(trustScore.tier)}</dd>
        <dt>Calculated</dt><dd>${escapeHtml(trustScore.calculated_at)}</dd>
      </dl>
      ${renderCurrentTrustCardPanel(currentTrustCard)}
      ${renderTrustScoreTrend(trustEvents)}
      ${renderTrustScoreEvents({ events: trustEvents })}
    </div>
  `;
}

export function trustEventParamsFromForm(form) {
  return trustEventParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function trustEventParamsFromValues(values) {
  return {
    dimension: String(values.dimension ?? "")
  };
}

export function trustCardIssuePayloadFromForm(form) {
  const values = Object.fromEntries(new FormData(form));
  return {
    agent_id: String(values.agent_id ?? ""),
    issuer: String(values.issuer ?? "ophanix-demo-issuer")
  };
}

export function trustCardRevokePayloadFromForm(form) {
  const values = Object.fromEntries(new FormData(form));
  return {
    reason: String(values.reason ?? "")
  };
}

export function trustThresholdPayloadFromForm(form) {
  return trustThresholdPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function trustThresholdPayloadFromValues(values) {
  return {
    threshold_type: String(values.threshold_type ?? ""),
    target_type: String(values.target_type ?? "environment"),
    target_id: blankToNull(values.target_id),
    min_score: Number(values.min_score ?? 0),
    required_tier: String(values.required_tier ?? "standard"),
    enabled: values.enabled !== "off"
  };
}

export function trustThresholdPatchPayloadFromForm(form) {
  const values = Object.fromEntries(new FormData(form));
  return {
    min_score: Number(values.min_score ?? 0),
    required_tier: String(values.required_tier ?? "standard"),
    enabled: Boolean(form.elements.enabled?.checked)
  };
}

export function trustHandshakeParamsFromForm(form) {
  return trustHandshakeParamsFromValues(Object.fromEntries(new FormData(form)));
}

export function trustHandshakeParamsFromValues(values) {
  return {
    source_agent_id: String(values.source_agent_id ?? ""),
    target_agent_id: String(values.target_agent_id ?? ""),
    result: String(values.result ?? "")
  };
}

export function trustHandshakePayloadFromForm(form) {
  const values = Object.fromEntries(new FormData(form));
  return {
    source_agent_id: String(values.source_agent_id ?? ""),
    target_agent_id: String(values.target_agent_id ?? ""),
    purpose: String(values.purpose ?? "handoff"),
    threshold_type: String(values.threshold_type ?? "handoff"),
    target_type: String(values.target_type ?? "environment"),
    target_id: blankToNull(values.target_id),
    required_capabilities: String(values.required_capabilities ?? "")
      .split(",")
      .map((capability) => capability.trim())
      .filter(Boolean),
    require_trust_card: Boolean(form.elements.require_trust_card?.checked),
    require_active_credential: Boolean(form.elements.require_active_credential?.checked)
  };
}

function summaryCard(label, value) {
  return `
    <article class="workspace-panel">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </article>
  `;
}

function dimensionSignals(score) {
  const dimensions = Object.values(score.dimensions ?? {});
  return dimensions.reduce((total, dimension) => total + Number(dimension.signal_count ?? 0), 0);
}

function scoreWidth(score) {
  return Math.max(0, Math.min(100, Math.round(Number(score ?? 0) / 10)));
}

function formatDelta(delta) {
  const value = Number(delta ?? 0);
  return `${value > 0 ? "+" : ""}${value}`;
}

function blankToNull(value) {
  const stripped = String(value ?? "").trim();
  return stripped || null;
}
