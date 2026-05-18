import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { SystemStatusIndicator } from "./SystemStatusIndicator";

describe("SystemStatusIndicator", () => {
  it("renders degraded dependency status with version details", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", async (url: string) => {
      calls.push(String(url));
      if (url.endsWith("/system/dependencies")) {
        return json([{ name: "worker", required: true, status: "degraded", details: "queue idle" }]);
      }
      if (url.endsWith("/version")) {
        return json({ build_sha: "test-sha", environment: "test" });
      }
      return json({});
    });

    renderWithQueryClient(<SystemStatusIndicator />);

    expect(await screen.findByText("Degraded")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "System status" });
    fireEvent.click(button);

    expect(screen.getByRole("dialog", { name: "System status" })).toBeInTheDocument();
    expect(screen.getByText("API build: test-sha")).toBeInTheDocument();
    expect(screen.getByText("worker")).toBeInTheDocument();
    expect(calls).toContain("/version");
    expect(calls).not.toContain("/api/v1/version");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(button).toHaveFocus();
  });

  it("renders a warning when status endpoints cannot be loaded", async () => {
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(JSON.stringify({ detail: "status unavailable" }), {
          headers: { "Content-Type": "application/json" },
          status: 503
        })
    );

    renderWithQueryClient(<SystemStatusIndicator />);

    expect(await screen.findByText("Warning")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "System status" }));

    expect(screen.getByText("System status could not be fully loaded.")).toBeInTheDocument();
    expect(screen.getByText("API build: unknown")).toBeInTheDocument();
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
