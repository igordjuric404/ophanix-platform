import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { SystemStatusIndicator } from "./SystemStatusIndicator";

describe("SystemStatusIndicator", () => {
  it("renders degraded dependency status with version details", async () => {
    vi.stubGlobal("fetch", async (url: string) => {
      if (url.endsWith("/system/dependencies")) {
        return json([{ name: "worker", status: "degraded", details: "queue idle" }]);
      }
      if (url.endsWith("/version")) {
        return json({ build_sha: "test-sha", environment: "test" });
      }
      return json({});
    });

    renderWithQueryClient(<SystemStatusIndicator />);

    expect(await screen.findByText("Degraded")).toBeInTheDocument();
    expect(screen.getByText("API build: test-sha")).toBeInTheDocument();
    expect(screen.getByText("worker")).toBeInTheDocument();
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

