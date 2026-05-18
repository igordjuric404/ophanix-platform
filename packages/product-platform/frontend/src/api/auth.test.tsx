import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../test/test-utils";
import { currentUserQueryKey, useCurrentUser, useDevLogin, useLogout } from "./auth";
import { getApiTenantContext, setApiTenantContext } from "./client";
import type { UserPrincipal } from "./types";

const user: UserPrincipal = {
  id: "user_admin",
  display_name: "Admin",
  email: "admin@example.com",
  organization_id: "org_default",
  roles: ["Platform Admin"]
};

function LogoutProbe() {
  const logout = useLogout();
  return (
    <button onClick={() => void logout.mutateAsync()} type="button">
      Logout
    </button>
  );
}

function LoginProbe() {
  const login = useDevLogin();
  return (
    <button
      onClick={() => void login.mutateAsync({ email: user.email, roles: user.roles })}
      type="button"
    >
      Login
    </button>
  );
}

function CurrentUserProbe() {
  const currentUser = useCurrentUser();
  return <div>{currentUser.data?.email ?? "loading"}</div>;
}

describe("auth cache lifecycle", () => {
  it("clears session and tenant-scoped server state on logout", async () => {
    const calls: RequestInit[] = [];
    vi.stubGlobal("fetch", async (_input: RequestInfo | URL, init?: RequestInit) => {
      calls.push(init ?? {});
      return new Response(null, { status: 204 });
    });

    setApiTenantContext({ organizationId: "org_default", environmentId: "env_default" });
    const { queryClient } = renderWithQueryClient(<LogoutProbe />);
    queryClient.setQueryData(currentUserQueryKey, user);
    queryClient.setQueryData(
      ["tenant-scope", { organizationId: "org_default", environmentId: "env_default" }, "agents"],
      [{ id: "agent_1" }]
    );

    fireEvent.click(screen.getByRole("button", { name: "Logout" }));

    await waitFor(() => expect(queryClient.getQueryData(currentUserQueryKey)).toBeUndefined());
    expect(calls).toHaveLength(1);
    expect((calls[0].headers as Headers).get("X-Organization-ID")).toBeNull();
    expect((calls[0].headers as Headers).get("X-Environment-ID")).toBeNull();
    expect(queryClient.getQueriesData({ queryKey: ["tenant-scope"] })).toHaveLength(0);
    expect(getApiTenantContext()).toEqual({ organizationId: null, environmentId: null });
  });

  it("drops stale tenant data before storing the logged-in user", async () => {
    const calls: RequestInit[] = [];
    vi.stubGlobal(
      "fetch",
      async (_input: RequestInfo | URL, init?: RequestInit) => {
        calls.push(init ?? {});
        return new Response(JSON.stringify({ user }), {
          headers: { "Content-Type": "application/json" },
          status: 200
        });
      }
    );

    setApiTenantContext({ organizationId: "org_default", environmentId: "env_old" });
    const { queryClient } = renderWithQueryClient(<LoginProbe />);
    queryClient.setQueryData(
      ["tenant-scope", { organizationId: "org_default", environmentId: "env_old" }, "policies"],
      [{ id: "policy_old" }]
    );

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => expect(queryClient.getQueryData(currentUserQueryKey)).toEqual(user));
    expect(calls).toHaveLength(1);
    expect((calls[0].headers as Headers).get("X-Organization-ID")).toBeNull();
    expect((calls[0].headers as Headers).get("X-Environment-ID")).toBeNull();
    expect(queryClient.getQueriesData({ queryKey: ["tenant-scope"] })).toHaveLength(0);
    expect(getApiTenantContext()).toEqual({ organizationId: null, environmentId: null });
  });

  it("does not attach stale tenant headers to the current-user request", async () => {
    const calls: RequestInit[] = [];
    vi.stubGlobal("fetch", async (_input: RequestInfo | URL, init?: RequestInit) => {
      calls.push(init ?? {});
      return new Response(JSON.stringify(user), {
        headers: { "Content-Type": "application/json" },
        status: 200
      });
    });

    setApiTenantContext({ organizationId: "org_default", environmentId: "env_old" });
    renderWithQueryClient(<CurrentUserProbe />);

    expect(await screen.findByText(user.email)).toBeInTheDocument();
    expect(calls).toHaveLength(1);
    expect((calls[0].headers as Headers).get("X-Organization-ID")).toBeNull();
    expect((calls[0].headers as Headers).get("X-Environment-ID")).toBeNull();
  });
});
