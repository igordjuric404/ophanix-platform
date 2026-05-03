import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { MarketplacePage, marketplacePolicyPayloadFromValues } from "./MarketplacePage";

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
  result: "allowed",
  findings: [],
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
    window.localStorage.setItem("ophanix.selectedEnvironmentId", "env_default");
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
    expect(requests.some((request) => request.url.endsWith("/installations"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/submit-review"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/assess-quality"))).toBe(true);
    expect(requests.some((request) => request.url.endsWith("/recompute-trust"))).toBe(true);
  });

  it("normalizes policy payload lists and booleans", () => {
    expect(
      marketplacePolicyPayloadFromValues({
        require_signature: "on",
        allowed_plugin_types: "integration, agent",
        allowed_capabilities: " claims.lookup "
      })
    ).toEqual({
      require_signature: true,
      require_review_approval: false,
      allowed_plugin_types: ["integration", "agent"],
      allowed_capabilities: ["claims.lookup"],
      allowed_organizations: null
    });
  });
});

function mockMarketplaceFetch() {
  const requests: Array<{ url: string; method: string; body?: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      const path = new URL(url, "http://localhost").pathname;
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      requests.push({ url: path, method, body });

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
      if (path === "/api/v1/marketplace/installations" && method === "POST") {
        return json({ ...installation, id: "install_2" }, 201);
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
