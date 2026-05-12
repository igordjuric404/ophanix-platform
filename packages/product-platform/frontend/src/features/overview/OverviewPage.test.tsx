import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { OverviewPage } from "./OverviewPage";

describe("OverviewPage", () => {
  it("loads version and dependency data through TanStack Query", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(String(url));
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
              { name: "database", required: true, status: "healthy", details: "postgresql ready" },
              { name: "worker", required: true, status: "degraded", details: "queue idle" }
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
    expect(calls).toContain("/version");
    expect(calls).not.toContain("/api/v1/version");
  });

  it("shows a refresh overlay while refetching overview data", async () => {
    let dependencyCalls = 0;
    let resolveRefresh = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/auth/me")) {
          return json({
            id: "user_1",
            email: "admin@example.com",
            display_name: "admin",
            roles: ["Platform Admin"]
          });
        }
        if (url.endsWith("/system/dependencies")) {
          dependencyCalls += 1;
          if (dependencyCalls > 1) {
            await new Promise<void>((resolve) => {
              resolveRefresh = resolve;
            });
          }
          return json([{ name: "database", required: true, status: "healthy" }]);
        }
        if (url.endsWith("/version")) {
          return json({ build_sha: "test-sha", environment: "test" });
        }
        return json({ ok: true }, 404);
      }) as unknown as typeof fetch
    );

    renderWithQueryClient(<OverviewPage />);

    expect(await screen.findByText("System dependencies")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    expect(screen.getByRole("status")).toHaveTextContent("Refreshing overview");
    resolveRefresh();

    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });
});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status
  });
}
