import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter
} from "@tanstack/react-router";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { LoginScreen } from "./LoginScreen";

function loginTestRouter() {
  const rootRoute = createRootRoute({ component: Outlet });
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: LoginScreen
  });
  return createRouter({
    history: createMemoryHistory({ initialEntries: ["/"] }),
    routeTree: rootRoute.addChildren([indexRoute])
  });
}

describe("LoginScreen", () => {
  it("posts the local dev-login request with the default admin email", async () => {
    const calls: Array<[string, RequestInit]> = [];
    const fetchMock: typeof fetch = async (url, init) => {
      calls.push([String(url), init ?? {}]);
      return (
        new Response(
          JSON.stringify({
            access_token: "token",
            token_type: "bearer",
            expires_at: 1,
            user: {
              id: "user_1",
              email: "admin@example.com",
              display_name: "admin",
              roles: ["Platform Admin"]
            }
          }),
          {
            headers: { "Content-Type": "application/json" },
            status: 200
          }
        )
      );
    };
    vi.stubGlobal("fetch", fetchMock);

    const router = loginTestRouter();
    await router.load();

    renderWithQueryClient(<RouterProvider router={router} />);
    fireEvent.click(await screen.findByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    const [url, init] = calls[0];
    expect(url).toBe("/api/v1/auth/dev-login");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body as string)).toEqual({
      email: "admin@example.com",
      roles: ["Platform Admin"]
    });
  });
});
