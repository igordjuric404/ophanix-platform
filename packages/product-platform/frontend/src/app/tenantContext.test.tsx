import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import type { UserPrincipal } from "../api/types";
import { renderWithQueryClient } from "../test/test-utils";
import { useTenantSelection } from "./tenantContext";

const user: UserPrincipal = {
  id: "user_1",
  email: "admin@example.com",
  display_name: "admin",
  roles: ["Platform Admin"],
  organization_id: "org_default"
};

function TenantProbe() {
  const tenant = useTenantSelection(user);
  return (
    <div>
      <span>{tenant.selectedOrganization?.name ?? "No organization"}</span>
      <span>{tenant.selectedEnvironment?.name ?? "No environment"}</span>
    </div>
  );
}

describe("useTenantSelection", () => {
  it("uses stored environment preference and sends tenant headers through the API client", async () => {
    window.localStorage.setItem("ophanix.selectedEnvironmentId", "env_prod");
    const calls: Array<[string, RequestInit]> = [];
    vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
      calls.push([url, init ?? {}]);
      if (url.endsWith("/organizations")) {
        return json([{ id: "org_default", name: "Ophanix Demo" }]);
      }
      if (url.endsWith("/environments")) {
        return json([
          { id: "env_default", organization_id: "org_default", name: "Development" },
          { id: "env_prod", organization_id: "org_default", name: "Production" }
        ]);
      }
      return json({ ok: true });
    });

    renderWithQueryClient(<TenantProbe />);

    expect(await screen.findByText("Ophanix Demo")).toBeInTheDocument();
    expect(screen.getByText("Production")).toBeInTheDocument();

    calls.length = 0;
    await apiClient.request("/agents");

    await waitFor(() => expect(calls.length).toBe(1));
    const [, init] = calls[0];
    expect((init.headers as Headers).get("X-Organization-ID")).toBe("org_default");
    expect((init.headers as Headers).get("X-Environment-ID")).toBe("env_prod");
  });
});

function json(body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
      status: 200
    })
  );
}

