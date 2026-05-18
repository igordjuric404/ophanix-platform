import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../test/test-utils";
import { currentUserQueryKey, useDevLogin, useLogout } from "./auth";
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

describe("auth cache lifecycle", () => {
  it("clears session and tenant-scoped server state on logout", async () => {
    vi.stubGlobal("fetch", async () => new Response(null, { status: 204 }));

    setApiTenantContext({ organizationId: "org_default", environmentId: "env_default" });
    const { queryClient } = renderWithQueryClient(<LogoutProbe />);
    queryClient.setQueryData(currentUserQueryKey, user);
    queryClient.setQueryData(
      ["tenant-scope", { organizationId: "org_default", environmentId: "env_default" }, "agents"],
      [{ id: "agent_1" }]
    );

    fireEvent.click(screen.getByRole("button", { name: "Logout" }));

    await waitFor(() => expect(queryClient.getQueryData(currentUserQueryKey)).toBeUndefined());
    expect(queryClient.getQueriesData({ queryKey: ["tenant-scope"] })).toHaveLength(0);
    expect(getApiTenantContext()).toEqual({ organizationId: null, environmentId: null });
  });

  it("drops stale tenant data before storing the logged-in user", async () => {
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(JSON.stringify({ user }), {
          headers: { "Content-Type": "application/json" },
          status: 200
        })
    );

    setApiTenantContext({ organizationId: "org_default", environmentId: "env_old" });
    const { queryClient } = renderWithQueryClient(<LoginProbe />);
    queryClient.setQueryData(
      ["tenant-scope", { organizationId: "org_default", environmentId: "env_old" }, "policies"],
      [{ id: "policy_old" }]
    );

    fireEvent.click(screen.getByRole("button", { name: "Login" }));

    await waitFor(() => expect(queryClient.getQueryData(currentUserQueryKey)).toEqual(user));
    expect(queryClient.getQueriesData({ queryKey: ["tenant-scope"] })).toHaveLength(0);
    expect(getApiTenantContext()).toEqual({ organizationId: null, environmentId: null });
  });
});
