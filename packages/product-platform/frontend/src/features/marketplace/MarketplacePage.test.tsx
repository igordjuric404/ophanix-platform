import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { setApiTenantContext } from "../../api/client";
import { renderWithQueryClient } from "../../test/test-utils";
import {
  MarketplacePage,
  marketplaceImportPayloadFromValues,
  marketplacePolicyAllowsInstall,
  marketplacePolicyPayloadFromValues,
  marketplaceTrustPayloadFromValues
} from "./MarketplacePage";

const plugin = {
  id: "plug_1",
  organization_id: "org_default",
  name: "Claims Assistant",
  description: "Claims workflow governance pack",
  publisher: "Ophanix",
  plugin_type: "integration",
  status: "available",
  created_at: "2026-05-01T00:00:00Z",
  updated_at: "2026-05-01T00:00:00Z",
  versions: [
    {
      id: "plugver_1",
      plugin_id: "plug_1",
      version: "1.0.0",
      manifest: {
        name: "Claims Assistant",
        version: "1.0.0",
        plugin_type: "integration"
      },
      package_ref: "registry://claims-assistant",
      signature_status: "signed",
      quality_score: 0.91,
      trust_tier: "trusted",
      required_capabilities: ["claims.lookup"],
      permissions: ["mcp.invoke"],
      created_at: "2026-05-01T00:00:00Z",
      updated_at: "2026-05-01T00:00:00Z"
    },
    {
      id: "plugver_2",
      plugin_id: "plug_1",
      version: "2.0.0",
      manifest: {
        name: "Claims Assistant",
        version: "2.0.0",
        plugin_type: "integration"
      },
      package_ref: "registry://claims-assistant/v2",
      signature_status: "signed",
      quality_score: 0.97,
      trust_tier: "trusted",
      required_capabilities: ["claims.lookup", "claims.update"],
      permissions: ["mcp.invoke", "claims.write"],
      created_at: "2026-05-02T00:00:00Z",
      updated_at: "2026-05-02T00:00:00Z"
    }
  ]
};

const installation = {
  id: "install_1",
  plugin_version_id: "plugver_1",
  plugin_name: "Claims Assistant",
  version: "1.0.0",
  environment_id: "env_default",
  target_agent_id: "agent_1",
  target_agent_name: "Claims Agent",
  status: "installed",
  installed_by: "user_1",
  installed_at: "2026-05-01T01:00:00Z",
  uninstalled_at: null
};

const review = {
  id: "review_1",
  plugin_version_id: "plugver_1",
  plugin_name: "Claims Assistant",
  version: "1.0.0",
  status: "pending",
  reviewer_id: null,
  findings: [{ code: "manual_review", message: "Manual review requested" }],
  decision_reason: null,
  created_at: "2026-05-01T01:00:00Z",
  decided_at: null
};

const signingKey = {
  id: "sign_1",
  organization_id: "org_default",
  name: "Marketplace Root",
  public_key: "pk_test",
  status: "active",
  created_by: "user_1",
  created_at: "2026-05-01T01:00:00Z",
  revoked_at: null
};

const policyResult = {
  id: "polres_1",
  plugin_version_id: "plugver_1",
  result: "allow",
  findings: [],
  policy_input: {
    require_signature: true,
    require_artifact_evidence: true,
    require_review_approval: false
  },
  created_at: "2026-05-01T02:00:00Z"
};

const assessment = {
  id: "qual_1",
  plugin_version_id: "plugver_1",
  score: 0.94,
  dimensions: { tests: 0.9, docs: 1 },
  findings: [],
  created_at: "2026-05-01T03:00:00Z"
};

const trustEvent = {
  id: "trust_1",
  plugin_version_id: "plugver_1",
  delta: 8,
  reason: "positive adoption",
  score_before: 820,
  score_after: 828,
  trust_tier: "trusted",
  source_event_id: null,
  created_at: "2026-05-01T04:00:00Z"
};

describe("MarketplacePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("ophanix.selectedEnvironmentId", "stale_env");
    setApiTenantContext({ organizationId: "org_default", environmentId: "env_review" });
  });

  it("renders catalog, detail, installs, reviews, signing keys, and trust controls", async () => {
    mockMarketplaceFetch();

    renderWithQueryClient(<MarketplacePage />);

    expect(await screen.findByRole("heading", { name: "Plugin Catalog" })).toBeInTheDocument();
    expect((await screen.findAllByText("Claims Assistant")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Marketplace Root")).toBeInTheDocument();
    expect(await screen.findByText("Claims Agent")).toBeInTheDocument();
    expect(screen.getAllByText("trusted").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/claims.lookup/).length).toBeGreaterThan(0);
  });

  it("submits marketplace workflow actions with normalized payloads", async () => {
    const requests = mockMarketplaceFetch();

    renderWithQueryClient(<MarketplacePage />);

    await screen.findAllByText("Claims Assistant");

    fireEvent.click(screen.getByRole("checkbox", { name: "Require Signature" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Require Artifact Evidence" }));
    fireEvent.change(screen.getByLabelText("Allowed Types"), {
      target: { value: "integration, agent" }
    });
    fireEvent.click(screen.getByRole("button", { name: /Check Policy/ }));
    expect(await screen.findByText("Policy compatibility checked")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Target Agent"), { target: { value: "agent_1" } });
    fireEvent.click(screen.getByRole("button", { name: "Install" }));
    expect(await screen.findByText("Plugin installation created")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Submit Review" }));
    expect(await screen.findByText("Plugin review submitted")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Assess Quality/ }));
    expect(await screen.findByText("Quality assessment completed")).toBeInTheDocument();
    expect(screen.getByText("0.94")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Recompute Trust/ }));
    expect(await screen.findByText("Plugin trust recomputed")).toBeInTheDocument();
    expect(screen.getByText("positive adoption")).toBeInTheDocument();

    const reviewRow = document.querySelector('[data-marketplace-review-row="review_1"]');
    expect(reviewRow).not.toBeNull();
    fireEvent.change(within(reviewRow as HTMLElement).getByLabelText("approved reason"), {
      target: { value: "Looks good" }
    });
    fireEvent.click(within(reviewRow as HTMLElement).getByRole("button", { name: "Approve" }));
    expect(await screen.findByText("Review approved")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Key Name"), { target: { value: "Release Key" } });
    fireEvent.change(screen.getByLabelText("Public Key"), { target: { value: "pk_release" } });
    fireEvent.click(screen.getByRole("button", { name: /Add Key/ }));
    expect(await screen.findByText("Signing key registered")).toBeInTheDocument();

    expect(requests.some((request) => request.url.endsWith("/check-policy"))).toBe(true);
    const installRequest = requests.find(
      (request) => request.url.endsWith("/installations") && request.method === "POST"
    );
    expect(installRequest?.body).toMatchObject({
      environment_id: "env_review",
      plugin_version_id: "plugver_1"
    });
    expect(installRequest?.environmentId).toBe("env_review");
    expect(installRequest?.organizationId).toBe("org_default");
    expect(requests.some((request) => request.url.endsWith("/submit-review"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/assess-quality"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/recompute-trust"))).toBe(true);
  });

  it("targets the selected plugin version for version-scoped actions", async () => {
    const requests = mockMarketplaceFetch();

    renderWithQueryClient(<MarketplacePage />);

    const versionRow = await screen.findByText("2.0.0");
    const row = versionRow.closest("tr");
    expect(row).not.toBeNull();
    fireEvent.click(within(row as HTMLElement).getByRole("button", { name: "Select" }));

    fireEvent.click(screen.getByRole("checkbox", { name: "Require Signature" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Require Artifact Evidence" }));
    fireEvent.click(screen.getByRole("button", { name: /Check Policy/ }));
    expect(await screen.findByText("Policy compatibility checked")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Install" }));
    expect(await screen.findByText("Plugin installation created")).toBeInTheDocument();

    expect(requests.some((request) => request.url.endsWith("/plugver_2/check-policy"))).toBe(true);
    const installRequest = requests.find(
      (request) => request.url.endsWith("/installations") && request.method === "POST"
    );
    expect(installRequest?.body).toMatchObject({
      plugin_version_id: "plugver_2"
    });
  });

  it("normalizes policy payload lists and booleans", () => {
    expect(
      marketplacePolicyPayloadFromValues({
        require_signature: "on",
        require_artifact_evidence: "on",
        allowed_plugin_types: "integration, agent",
        allowed_capabilities: " claims.lookup "
      })
    ).toEqual({
      require_signature: true,
      require_review_approval: false,
      require_artifact_evidence: true,
      allowed_plugin_types: ["integration", "agent"],
      allowed_capabilities: ["claims.lookup"],
      allowed_organizations: null
    });

    expect(() =>
      marketplaceImportPayloadFromValues({
        manifest_json: "[]"
      })
    ).toThrow("Manifest JSON must be a JSON object.");
  });

  it("test_marketplace_ui_accepts_allow_policy_result", async () => {
    mockMarketplaceFetch();

    renderWithQueryClient(<MarketplacePage />);

    await screen.findAllByText("Claims Assistant");

    fireEvent.click(screen.getByRole("checkbox", { name: "Require Signature" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Require Artifact Evidence" }));
    fireEvent.click(screen.getByRole("button", { name: /Check Policy/ }));

    expect(await screen.findByText("Policy compatibility checked")).toBeInTheDocument();
    expect(marketplacePolicyAllowsInstall(policyResult, plugin.versions[0])).toBe(true);
    expect(screen.getByRole("button", { name: "Install" })).toBeEnabled();

    const gates = document.querySelector("[data-marketplace-install-gates]");
    expect(gates).not.toBeNull();
    expect(within(gates as HTMLElement).getAllByText("pass").length).toBeGreaterThanOrEqual(3);
  });

  it("rejects invalid numeric marketplace trust payload fields instead of using zero", () => {
    expect(() =>
      marketplaceTrustPayloadFromValues({
        adoption_trend: "steady",
        daily_active_users: "5",
        days_since_update: "1",
        error_count: "0",
        incident_count: "0",
        total_invocations: "50"
      })
    ).toThrow("Adoption Trend must be a valid number.");

    expect(() =>
      marketplaceTrustPayloadFromValues({
        adoption_trend: "0.1",
        daily_active_users: "5.5",
        days_since_update: "1",
        error_count: "0",
        incident_count: "0",
        total_invocations: "50"
      })
    ).toThrow("Daily Active Users must be a valid integer.");
  });
});

function mockMarketplaceFetch() {
  const requests: Array<{
    body?: unknown;
    environmentId: string | null;
    method: string;
    organizationId: string | null;
    url: string;
  }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      const path = new URL(url, "http://localhost").pathname;
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      const headers = init?.headers as Headers | undefined;
      requests.push({
        body,
        environmentId: headers?.get("X-Environment-ID") ?? null,
        method,
        organizationId: headers?.get("X-Organization-ID") ?? null,
        url: path
      });

      if (path === "/api/v1/marketplace/plugins" && method === "GET") {
        return json([plugin]);
      }
      if (path === "/api/v1/marketplace/plugins/plug_1" && method === "GET") {
        return json(plugin);
      }
      if (path === "/api/v1/marketplace/installations" && method === "GET") {
        return json([installation]);
      }
      if (path === "/api/v1/marketplace/reviews" && method === "GET") {
        return json([review]);
      }
      if (path === "/api/v1/marketplace/signing-keys" && method === "GET") {
        return json([signingKey]);
      }
      if (path === "/api/v1/marketplace/plugins/plugver_1/check-policy" && method === "POST") {
        return json(policyResult, 201);
      }
      if (path === "/api/v1/marketplace/plugins/plugver_2/check-policy" && method === "POST") {
        return json({ ...policyResult, plugin_version_id: "plugver_2" }, 201);
      }
      if (path === "/api/v1/marketplace/installations" && method === "POST") {
        return json(
          {
            ...installation,
            id: "install_2",
            plugin_version_id: body?.plugin_version_id ?? installation.plugin_version_id
          },
          201
        );
      }
      if (path === "/api/v1/marketplace/plugins/plugver_1/submit-review" && method === "POST") {
        return json({ ...review, id: "review_2" }, 201);
      }
      if (path === "/api/v1/marketplace/plugins/plugver_1/assess-quality" && method === "POST") {
        return json(assessment, 201);
      }
      if (path === "/api/v1/marketplace/plugins/plugver_1/recompute-trust" && method === "POST") {
        return json(trustEvent, 201);
      }
      if (path === "/api/v1/marketplace/reviews/review_1/approve" && method === "POST") {
        return json({ ...review, status: "approved", decision_reason: "Looks good" });
      }
      if (path === "/api/v1/marketplace/signing-keys" && method === "POST") {
        return json({ ...signingKey, id: "sign_2", name: "Release Key" }, 201);
      }
      if (path === "/api/v1/marketplace/plugins/import" && method === "POST") {
        return json({ ...plugin, id: "plug_2", name: "Imported Plugin" }, 201);
      }

      return json({ detail: `Unhandled ${method} ${path}` }, 404);
    })
  );
  return requests;
}

function json(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
