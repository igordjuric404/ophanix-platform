import assert from "node:assert/strict";
import test from "node:test";

import { createApiClient } from "../src/apiClient.js";
import {
  marketplaceInstallPayloadFromValues,
  marketplacePolicyPayloadFromValues,
  marketplaceReviewDecisionPayloadFromValues,
  marketplaceReviewSubmitPayloadFromValues,
  marketplaceSigningKeyPayloadFromValues,
  marketplaceTrustPayloadFromValues,
  renderMarketplaceCatalogPanel,
  renderMarketplaceInstallWizard,
  renderMarketplacePage,
  renderMarketplacePluginDetail,
  renderMarketplaceQualitySummary,
  renderMarketplaceReviewQueue,
  renderMarketplaceSigningKeysPanel,
  renderMarketplaceTrustHistory
} from "../src/marketplace.js";

const plugin = {
  id: "plug_1",
  organization_id: "org_default",
  name: "support-triage-assistant",
  description: "Routes support requests to governed support agents.",
  publisher: "Ophanix Labs",
  plugin_type: "agent",
  status: "available",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
  versions: [
    {
      id: "plugver_1",
      plugin_id: "plug_1",
      version: "1.0.0",
      manifest: { name: "support-triage-assistant" },
      package_ref: "local://plugins/support-triage-assistant/1.0.0",
      signature_status: "signed",
      quality_score: 0,
      trust_tier: "unrated",
      required_capabilities: ["tickets:read", "tickets:route"],
      permissions: ["agent.invoke", "audit.write"],
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:00:00Z"
    }
  ]
};

const deniedPolicyResult = {
  id: "plugpol_1",
  plugin_version_id: "plugver_1",
  result: "deny",
  findings: [
    {
      code: "signature_required",
      message: "Plugin must have a valid signature before installation.",
      severity: "blocking",
      field: "signature_status",
      details: { signature_status: "unsigned" }
    }
  ],
  created_at: "2026-05-01T00:01:00Z"
};

const installation = {
  id: "pluginst_1",
  plugin_version_id: "plugver_1",
  plugin_name: "support-triage-assistant",
  version: "1.0.0",
  environment_id: "env_default",
  target_agent_id: null,
  target_agent_name: null,
  status: "installed",
  installed_by: "user_admin",
  installed_at: "2026-05-01T00:02:00Z",
  uninstalled_at: null
};

const review = {
  id: "plugrev_1",
  plugin_version_id: "plugver_1",
  plugin_name: "support-triage-assistant",
  version: "1.0.0",
  status: "pending",
  reviewer_id: null,
  findings: [{ code: "manual_review", message: "Needs reviewer approval" }],
  decision_reason: null,
  created_at: "2026-05-01T00:03:00Z",
  decided_at: null
};

const signingKey = {
  id: "plugkey_1",
  organization_id: "org_default",
  name: "Demo Marketplace Key",
  public_key: "demo-secret",
  status: "active",
  created_by: "user_admin",
  created_at: "2026-05-01T00:04:00Z",
  revoked_at: null
};

const trustEvent = {
  id: "plugtrust_1",
  plugin_version_id: "plugver_1",
  source_event_id: "usage_rollup_1",
  delta: 170,
  reason: "usage_adoption,reliability",
  score_before: 500,
  score_after: 670,
  trust_tier: "trusted",
  created_at: "2026-05-01T00:05:00Z"
};

test("component catalog renders plugin rows", () => {
  const html = renderMarketplaceCatalogPanel({ plugins: [plugin], selectedPluginId: plugin.id });

  assert.match(html, /data-marketplace-plugin-row="plug_1"/);
  assert.match(html, /support-triage-assistant/);
  assert.match(html, /Ophanix Labs/);
  assert.match(html, /signed/);
});

test("component route renders catalog detail install and installed panels", () => {
  const html = renderMarketplacePage({
    marketplacePlugins: [plugin],
    selectedMarketplacePlugin: plugin,
    marketplaceInstallations: [installation],
    marketplaceReviews: [review],
    marketplaceSigningKeys: [signingKey],
    marketplaceTrustEvents: [trustEvent],
    selectedEnvironment: { id: "env_default" }
  });

  assert.match(html, /data-route-page="\/marketplace"/);
  assert.match(html, /data-marketplace-catalog/);
  assert.match(html, /data-marketplace-detail="plug_1"/);
  assert.match(html, /data-marketplace-install-wizard="plugver_1"/);
  assert.match(html, /data-marketplace-installation-row="pluginst_1"/);
  assert.match(html, /data-marketplace-review-row="plugrev_1"/);
  assert.match(html, /data-marketplace-signing-key-row="plugkey_1"/);
  assert.match(html, /data-marketplace-trust-event-row="plugtrust_1"/);
});

test("component plugin detail shows manifest permissions and versions", () => {
  const html = renderMarketplacePluginDetail({ plugin });

  assert.match(html, /agent.invoke/);
  assert.match(html, /tickets:route/);
  assert.match(html, /data-marketplace-version-row="plugver_1"/);
  assert.match(html, /data-marketplace-manifest/);
});

test("component install wizard shows required capabilities", () => {
  const html = renderMarketplaceInstallWizard({ plugin, selectedEnvironmentId: "env_default" });

  assert.match(html, /tickets:read, tickets:route/);
  assert.match(html, /data-marketplace-policy-check-form/);
  assert.match(html, /data-marketplace-install-gates/);
  assert.match(html, /data-marketplace-install-form/);
});

test("component denied plugin displays policy finding", () => {
  const html = renderMarketplaceInstallWizard({
    plugin,
    policyResult: deniedPolicyResult,
    selectedEnvironmentId: "env_default"
  });

  assert.match(html, /data-marketplace-policy-findings/);
  assert.match(html, /signature_required/);
  assert.match(html, /Plugin must have a valid signature/);
  assert.match(html, /<button type="submit" disabled>Install<\/button>/);
});

test("component quality findings render", () => {
  const html = renderMarketplaceQualitySummary({
    assessment: {
      id: "plugqa_1",
      plugin_version_id: "plugver_1",
      score: 58,
      dimensions: {},
      findings: [
        {
          code: "low_documentation",
          message: "Add README, examples, API docs, and changelog before broad installation."
        }
      ],
      created_at: "2026-05-01T00:03:00Z"
    }
  });

  assert.match(html, /data-marketplace-quality-summary="plugqa_1"/);
  assert.match(html, /data-marketplace-quality-findings/);
  assert.match(html, /low_documentation/);
});

test("component review queue actions require reason", () => {
  const html = renderMarketplaceReviewQueue({ reviews: [review] });

  assert.match(html, /data-marketplace-review-row="plugrev_1"/);
  assert.match(html, /data-marketplace-review-approve-form/);
  assert.match(html, /data-marketplace-review-reject-form/);
  assert.match(html, /name="decision_reason" placeholder="Reason" required/);
});

test("component signing key table renders status", () => {
  const html = renderMarketplaceSigningKeysPanel({ signingKeys: [signingKey] });

  assert.match(html, /data-marketplace-signing-key-form/);
  assert.match(html, /data-marketplace-signing-key-row="plugkey_1"/);
  assert.match(html, /Demo Marketplace Key/);
  assert.match(html, /active/);
  assert.match(html, /data-marketplace-signing-key-revoke="plugkey_1"/);
});

test("component plugin trust tab shows event history", () => {
  const html = renderMarketplaceTrustHistory({
    version: plugin.versions[0],
    events: [trustEvent]
  });

  assert.match(html, /data-marketplace-trust/);
  assert.match(html, /data-marketplace-trust-recompute-form/);
  assert.match(html, /data-marketplace-trust-event-row="plugtrust_1"/);
  assert.match(html, /usage_adoption,reliability/);
  assert.match(html, /trusted/);
});

test("payload helpers normalize policy and install forms", () => {
  assert.deepEqual(
    marketplacePolicyPayloadFromValues({
      require_signature: "on",
      require_review_approval: "on",
      allowed_plugin_types: "agent, integration",
      allowed_capabilities: "tickets:read, tickets:route"
    }),
    {
      require_signature: true,
      require_review_approval: true,
      allowed_plugin_types: ["agent", "integration"],
      allowed_capabilities: ["tickets:read", "tickets:route"]
    }
  );
  assert.deepEqual(
    marketplaceInstallPayloadFromValues({
      plugin_version_id: " plugver_1 ",
      environment_id: " env_default ",
      target_agent_id: ""
    }),
    {
      plugin_version_id: "plugver_1",
      environment_id: "env_default",
      target_agent_id: null
    }
  );
});

test("payload helpers normalize review signing and trust forms", () => {
  assert.deepEqual(
    marketplaceReviewSubmitPayloadFromValues({
      code: " readiness ",
      message: " Looks ready "
    }),
    {
      findings: [{ code: "readiness", message: "Looks ready" }]
    }
  );
  assert.deepEqual(
    marketplaceReviewDecisionPayloadFromValues({ decision_reason: " Approved after checks " }),
    { decision_reason: "Approved after checks" }
  );
  assert.deepEqual(
    marketplaceSigningKeyPayloadFromValues({ name: " Demo ", public_key: " secret " }),
    { name: "Demo", public_key: "secret" }
  );
  assert.deepEqual(
    marketplaceTrustPayloadFromValues({
      daily_active_users: "1000",
      total_invocations: "10000",
      error_count: "20",
      incident_count: "0",
      adoption_trend: "0.6",
      source_event_id: " usage_rollup_1 "
    }),
    {
      daily_active_users: 1000,
      total_invocations: 10000,
      error_count: 20,
      incident_count: 0,
      days_since_update: 0,
      adoption_trend: 0.6,
      source_event_id: "usage_rollup_1"
    }
  );
});

test("api client marketplace endpoints use expected paths", async () => {
  const calls = [];
  const api = createApiClient({
    fetchImpl: async (url, options = {}) => {
      calls.push({ url, method: options.method ?? "GET" });
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "content-type": "application/json" }
      });
    }
  });

  await api.listMarketplacePlugins();
  await api.getMarketplacePlugin("plug_1");
  await api.checkMarketplacePluginPolicy("plugver_1", { require_signature: true });
  await api.submitMarketplacePluginReview("plugver_1", { findings: [] });
  await api.listMarketplaceReviews({ status: "pending" });
  await api.approveMarketplaceReview("plugrev_1", { decision_reason: "ready" });
  await api.rejectMarketplaceReview("plugrev_2", { decision_reason: "missing docs" });
  await api.createMarketplaceSigningKey({ name: "Demo", public_key: "secret" });
  await api.listMarketplaceSigningKeys();
  await api.revokeMarketplaceSigningKey("plugkey_1");
  await api.assessMarketplacePluginQuality("plugver_1");
  await api.recomputeMarketplacePluginTrust("plugver_1", { daily_active_users: 1000 });
  await api.createMarketplaceInstallation({ plugin_version_id: "plugver_1", environment_id: "env_default" });
  await api.listMarketplaceInstallations();
  await api.uninstallMarketplacePlugin("pluginst_1");

  assert.deepEqual(calls, [
    { url: "/api/v1/marketplace/plugins", method: "GET" },
    { url: "/api/v1/marketplace/plugins/plug_1", method: "GET" },
    { url: "/api/v1/marketplace/plugins/plugver_1/check-policy", method: "POST" },
    { url: "/api/v1/marketplace/plugins/plugver_1/submit-review", method: "POST" },
    { url: "/api/v1/marketplace/reviews?status=pending", method: "GET" },
    { url: "/api/v1/marketplace/reviews/plugrev_1/approve", method: "POST" },
    { url: "/api/v1/marketplace/reviews/plugrev_2/reject", method: "POST" },
    { url: "/api/v1/marketplace/signing-keys", method: "POST" },
    { url: "/api/v1/marketplace/signing-keys", method: "GET" },
    { url: "/api/v1/marketplace/signing-keys/plugkey_1/revoke", method: "POST" },
    { url: "/api/v1/marketplace/plugins/plugver_1/assess-quality", method: "POST" },
    { url: "/api/v1/marketplace/plugins/plugver_1/recompute-trust", method: "POST" },
    { url: "/api/v1/marketplace/installations", method: "POST" },
    { url: "/api/v1/marketplace/installations", method: "GET" },
    { url: "/api/v1/marketplace/installations/pluginst_1/uninstall", method: "POST" }
  ]);
});
