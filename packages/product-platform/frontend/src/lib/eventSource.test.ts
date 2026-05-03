import { describe, expect, it } from "vitest";

import { eventStreamUrl } from "./eventSource";

describe("eventStreamUrl", () => {
  it("preserves non-empty query params for stream subscriptions", () => {
    expect(
      eventStreamUrl(
        "/policy-evaluations/stream",
        {
          decision: "deny",
          mode: "live",
          environment_id: "env_default",
          empty: "",
          skipped: null
        },
        "/api/v1"
      )
    ).toBe("/api/v1/policy-evaluations/stream?decision=deny&mode=live&environment_id=env_default");
  });
});
