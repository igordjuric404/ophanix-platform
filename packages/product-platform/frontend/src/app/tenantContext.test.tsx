import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAgents } from "../api/agents";
import { apiClient, setApiTenantContext } from "../api/client";
import { exportAuditEvents, useComplianceMutation } from "../api/compliance";
import { createFrameworkInstance, useIntegrationMutation } from "../api/integrations";
import { createProtocolBridge, useMeshMutation } from "../api/mesh";
import { importPolicy, usePolicyMutation } from "../api/policies";
import { TenantQueryScopeProvider, useTenantQueryScope } from "../api/queryScope";
import { recalculateTrust, useTrustMutation } from "../api/trust";
import type { UserPrincipal } from "../api/types";
import { selectedEnvironmentStorageKeyFor } from "../lib/storage";
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

function DomainMutationProbe() {
  const [status, setStatus] = useState("idle");
  const integrationMutation = useIntegrationMutation();
  const policyMutation = usePolicyMutation();
  const complianceMutation = useComplianceMutation();
  const trustMutation = useTrustMutation();
  const meshMutation = useMeshMutation();

  async function runMutations() {
    await Promise.all([
      integrationMutation.mutateAsync((tenantContext) =>
        createFrameworkInstance(
          {
            config: {},
            integration_id: "openai_agents",
            name: "Route scoped connector",
            status: "active"
          },
          tenantContext
        )
      ),
      policyMutation.mutateAsync((tenantContext) =>
        importPolicy(
          {
            body_format: "yaml",
            body_text: "rules: []",
            name: "Route scoped policy",
            scope: "agent"
          },
          tenantContext
        )
      ),
      complianceMutation.mutateAsync((tenantContext) =>
        exportAuditEvents({ format: "json" }, tenantContext)
      ),
      trustMutation.mutateAsync((tenantContext) => recalculateTrust({}, tenantContext)),
      meshMutation.mutateAsync((tenantContext) =>
        createProtocolBridge(
          {
            bridge_type: "mcp",
            config: {},
            name: "Route scoped bridge",
            status: "configured"
          },
          tenantContext
        )
      )
    ]);
    setStatus("done");
  }

  return (
    <>
      <button onClick={() => void runMutations()} type="button">
        Run domain mutations
      </button>
      <span>{status}</span>
    </>
  );
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
    expect(
      window.localStorage.getItem(
        selectedEnvironmentStorageKeyFor({
          organizationId: "org_default",
          userId: "user_1"
        })
      )
    ).toBe("env_prod");

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

  it("prefers selected environment storage scoped by user and organization", async () => {
    window.localStorage.setItem("ophanix.selectedEnvironmentId", "env_prod");
    window.localStorage.setItem(
      selectedEnvironmentStorageKeyFor({ organizationId: "org_default", userId: "user_1" }),
      "env_default"
    );
    vi.stubGlobal("fetch", async (url: string) => {
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

    expect(await screen.findByText("Development")).toBeInTheDocument();
    expect(screen.queryByText("Production")).not.toBeInTheDocument();
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

  it("passes the route tenant scope through domain mutation hooks", async () => {
    const mutationCalls: Array<{ environmentId: string | null; organizationId: string | null }> =
      [];
    setApiTenantContext({ organizationId: "org_default", environmentId: "env_stale" });
    vi.stubGlobal("fetch", async (_url: string, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      mutationCalls.push({
        environmentId: headers.get("X-Environment-ID"),
        organizationId: headers.get("X-Organization-ID")
      });
      return json({ id: "mutation_result", policy: { id: "policy_result" } });
    });

    renderWithQueryClient(
      <TenantQueryScopeProvider
        context={{ organizationId: "org_default", environmentId: "env_route" }}
      >
        <DomainMutationProbe />
      </TenantQueryScopeProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "Run domain mutations" }));

    expect(await screen.findByText("done")).toBeInTheDocument();
    expect(mutationCalls).toHaveLength(5);
    expect(mutationCalls).toEqual(
      mutationCalls.map(() => ({
        environmentId: "env_route",
        organizationId: "org_default"
      }))
    );
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
