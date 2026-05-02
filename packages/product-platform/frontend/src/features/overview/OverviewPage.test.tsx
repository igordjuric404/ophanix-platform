import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { OverviewPage } from "./OverviewPage";

describe("OverviewPage", () => {
  it("loads version and dependency data through TanStack Query", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/auth/me")) {
          return new Response(
            JSON.stringify({
              id: "user_1",
              email: "admin@example.com",
              display_name: "admin",
              roles: ["Platform Admin"]
            }),
            { headers: { "Content-Type": "application/json" }, status: 200 }
          );
        }
        if (url.endsWith("/system/dependencies")) {
          return new Response(
            JSON.stringify([
              { name: "database", status: "healthy", details: "sqlite ready" },
              { name: "worker", status: "degraded", details: "queue idle" }
            ]),
            { headers: { "Content-Type": "application/json" }, status: 200 }
          );
        }
        if (url.endsWith("/version")) {
          return new Response(
            JSON.stringify({
              build_sha: "test-sha",
              environment: "test"
            }),
            { headers: { "Content-Type": "application/json" }, status: 200 }
          );
        }
        return new Response(JSON.stringify({ detail: "not found" }), {
          headers: { "Content-Type": "application/json" },
          status: 404
        });
      }) as unknown as typeof fetch
    );

    renderWithQueryClient(<OverviewPage />);

    expect(await screen.findByText("System dependencies")).toBeInTheDocument();
    expect(screen.getByText("database")).toBeInTheDocument();
    expect(screen.getByText("test-sha")).toBeInTheDocument();
  });
});

