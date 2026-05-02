import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { RequireAuth } from "./RequireAuth";

describe("RequireAuth", () => {
  it("renders children for an authenticated user", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              id: "user_1",
              email: "admin@example.com",
              display_name: "admin",
              roles: ["Platform Admin"]
            }),
            {
              headers: { "Content-Type": "application/json" },
              status: 200
            }
          )
      )
    );

    renderWithQueryClient(
      <RequireAuth>{(user) => <div>Welcome {user.email}</div>}</RequireAuth>
    );

    expect(await screen.findByText("Welcome admin@example.com")).toBeInTheDocument();
  });

  it("renders the unauthenticated fallback on 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Authentication is required." }), {
            headers: { "Content-Type": "application/json" },
            status: 401
          })
      )
    );

    renderWithQueryClient(
      <RequireAuth unauthenticatedFallback={<div>Login required</div>}>
        {() => <div>Secret</div>}
      </RequireAuth>
    );

    expect(await screen.findByText("Login required")).toBeInTheDocument();
  });
});

