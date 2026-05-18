import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAgents } from "../api/agents";
import { apiClient, setApiTenantContext } from "../api/client";
import { TenantQueryScopeProvider, useTenantQueryScope } from "../api/queryScope";
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

function AgentsProbe() {
  const agentsQuery = useAgents();
  return <span>{agentsQuery.data?.[0]?.name ?? "Loading agents"}</span>;
}

function TenantScopeProbe() {
  const scope = useTenantQueryScope();
  return <span>{scope.context.environmentId ?? "No environment"}</span>;
}

describe("useTenantSelection", () => {
  beforeEach(() => {
    window.localStorage.clear();
    setApiTenantContext({ organizationId: null, environmentId: null });
  });

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

  it("partitions server-state query cache by tenant scope", async () => {
    const calls: Array<{ environmentId: string | null }> = [];
    vi.stubGlobal("fetch", async (_url: string, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      const environmentId = headers.get("X-Environment-ID");
      calls.push({ environmentId });

      return json([
        {
          id: `agent_${environmentId ?? "none"}`,
          name: environmentId === "env_prod" ? "Production Agent" : "Development Agent",
          status: "active"
        }
      ]);
    });

    setApiTenantContext({ organizationId: "org_default", environmentId: "env_default" });
    const { queryClient } = renderWithQueryClient(<AgentsProbe />);

    expect(await screen.findByText("Development Agent")).toBeInTheDocument();

    await act(async () => {
      setApiTenantContext({ organizationId: "org_default", environmentId: "env_prod" });
    });

    expect(await screen.findByText("Production Agent")).toBeInTheDocument();
    expect(calls.map((call) => call.environmentId)).toEqual(["env_default", "env_prod"]);
    expect(queryClient.getQueriesData({ queryKey: ["tenant-scope"] })).toHaveLength(2);
  });

  it("lets the route tenant provider override stale global context during render", () => {
    setApiTenantContext({ organizationId: "org_default", environmentId: "env_stale" });

    renderWithQueryClient(
      <TenantQueryScopeProvider
        context={{ organizationId: "org_default", environmentId: "env_route" }}
      >
        <TenantScopeProbe />
      </TenantQueryScopeProvider>
    );

    expect(screen.getByText("env_route")).toBeInTheDocument();
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
