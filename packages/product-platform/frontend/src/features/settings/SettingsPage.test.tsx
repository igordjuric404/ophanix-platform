import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TenantQueryScopeProvider } from "../../api/queryScope";
import { CurrentUserProvider } from "../../app/userContext";
import { renderWithQueryClient } from "../../test/test-utils";
import { SettingsPage } from "./SettingsPage";

describe("SettingsPage", () => {
  beforeEach(() => {
    mockSettingsFetch();
  });

  it("renders concrete admin controls instead of a placeholder", async () => {
    renderSettingsPage(["Platform Admin"]);

    expect(await screen.findByText("Setup Checklist")).toBeInTheDocument();
    expect(screen.getByText("Organization And Environments")).toBeInTheDocument();
    expect(screen.getByText("API Keys")).toBeInTheDocument();
    expect(screen.getByText("Identity And Roles")).toBeInTheDocument();
    expect(screen.queryByText("Ready for feature migration")).not.toBeInTheDocument();
  });

  it("creates environments, creates API keys, and revokes existing keys", async () => {
    const calls = mockSettingsFetch();
    renderSettingsPage(["Platform Admin"]);

    expect(await screen.findByText("Existing key")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Create environment" }));
    fireEvent.click(screen.getByRole("button", { name: "Create API key" }));
    fireEvent.click(screen.getByRole("button", { name: "Revoke" }));

    await waitFor(() => {
      expect(calls).toContainEqual(
        expect.objectContaining({ method: "POST", path: "/api/v1/environments" })
      );
      expect(calls).toContainEqual(
        expect.objectContaining({ method: "POST", path: "/api/v1/api-keys" })
      );
      expect(calls).toContainEqual(
        expect.objectContaining({ method: "DELETE", path: "/api/v1/api-keys/key_existing" })
      );
    });
  });

  it("disables mutation controls for users without admin permissions", async () => {
    renderSettingsPage(["Viewer"]);

    expect(await screen.findByText("Setup Checklist")).toBeInTheDocument();
    expect(await screen.findByText("Existing key")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create environment" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Create API key" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Revoke" })).toBeDisabled();
  });
});

function renderSettingsPage(roles: string[]) {
  return renderWithQueryClient(
    <CurrentUserProvider
      user={{
        id: "user_test",
        email: "user@example.com",
        display_name: "Test User",
        roles
      }}
    >
      <TenantQueryScopeProvider
        context={{ organizationId: "org_default", environmentId: "env_default" }}
      >
        <SettingsPage />
      </TenantQueryScopeProvider>
    </CurrentUserProvider>
  );
}

function mockSettingsFetch() {
  const calls: Array<{ method: string; path: string; body?: unknown }> = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const parsed = new URL(String(input), "http://test.local");
    const path = `${parsed.pathname}${parsed.search}`;
    const method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ method, path, body });

    if (path === "/version") {
      return json({ app_name: "Ophanix Test Platform", version: "0.1.0" });
    }
    if (path === "/api/v1/system/dependencies") {
      return json([{ name: "database", status: "healthy", required: true }]);
    }
    if (path === "/api/v1/api-keys" && method === "GET") {
      return json([
        {
          id: "key_existing",
          organization_id: "org_default",
          name: "Existing key",
          scopes: ["job:run"],
          kind: "ci",
          environment_ids: ["env_default"],
          expires_at: null,
          last_used_at: null,
          revoked_at: null,
          created_at: 1770000000
        }
      ]);
    }
    if (path === "/api/v1/environments" && method === "POST") {
      return json({
        id: "env_staging",
        organization_id: "org_default",
        name: "Staging",
        slug: "staging",
        type: "staging",
        created_at: "2026-05-19T00:00:00+00:00"
      });
    }
    if (path === "/api/v1/api-keys" && method === "POST") {
      return json(
        {
          key: {
            id: "key_new",
            organization_id: "org_default",
            name: body?.name ?? "Workflow key",
            scopes: body?.scopes ?? ["job:run"],
            kind: body?.kind ?? "ci",
            environment_ids: body?.environment_ids ?? ["env_default"],
            expires_at: null,
            last_used_at: null,
            revoked_at: null,
            created_at: 1770000001
          },
          secret: "opx_key_new_redacted"
        },
        201
      );
    }
    if (path === "/api/v1/api-keys/key_existing" && method === "DELETE") {
      return new Response(null, { status: 204 });
    }
    return json({});
  });
  return calls;
}

function json(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
      status
    })
  );
}
