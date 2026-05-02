import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DetailDrawerProvider, useDetailDrawer } from "../../app/drawerContext";
import { renderWithQueryClient } from "../../test/test-utils";

function DrawerHarness({ eventId = "evt_1" }: { eventId?: string }) {
  const drawer = useDetailDrawer();
  return (
    <button onClick={() => void drawer.openAuditEvent(eventId)} type="button">
      Open audit event
    </button>
  );
}

describe("DetailDrawer", () => {
  it("opens, renders audit metadata and raw evidence, then closes", async () => {
    mockAuditFetch();

    renderWithQueryClient(
      <DetailDrawerProvider>
        <DrawerHarness />
      </DetailDrawerProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "Open audit event" }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("audit.event")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Evidence" }));
    expect(screen.getByText(/"reason": "baseline"/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close detail drawer" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("renders policy decision fields for policy audit events", async () => {
    mockAuditFetch({
      evt_1: {
        id: "evt_1",
        event_type: "policy.decision",
        policy_id: "pol_1",
        decision: "deny",
        payload_json: { matched_rule: "no-pii", reason: "PII blocked" }
      }
    });

    renderWithQueryClient(
      <DetailDrawerProvider>
        <DrawerHarness />
      </DetailDrawerProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "Open audit event" }));

    expect(await screen.findByText("no-pii")).toBeInTheDocument();
    expect(screen.getByText("no-pii")).toBeInTheDocument();
    expect(screen.getByText("PII blocked")).toBeInTheDocument();
  });

  it("navigates related events and returns with the drawer back action", async () => {
    mockAuditFetch({
      evt_1: {
        id: "evt_1",
        event_type: "policy.decision",
        policy_id: "pol_1",
        decision: "allow",
        correlation_id: "corr_1",
        payload_json: { reason: "first" }
      },
      evt_2: {
        id: "evt_2",
        event_type: "runtime.action",
        resource_id: "sess_1",
        correlation_id: "corr_1",
        payload_json: { action: "tool.call", ring: "ring_1", sandbox_status: "allowed" }
      }
    });

    renderWithQueryClient(
      <DetailDrawerProvider>
        <DrawerHarness />
      </DetailDrawerProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "Open audit event" }));
    fireEvent.click(await screen.findByRole("button", { name: "Related" }));
    fireEvent.click(screen.getByText("evt_2"));

    expect(await screen.findByText("tool.call")).toBeInTheDocument();
    expect(window.location.search).toBe("?drawer=audit-event&id=evt_2");

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(await screen.findByRole("heading", { name: "Policy Decision" })).toBeInTheDocument();
    expect(screen.getByText("pol_1")).toBeInTheDocument();
    expect(window.location.search).toBe("?drawer=audit-event&id=evt_1");
  });

  it("renders an error state when audit detail loading fails", async () => {
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(JSON.stringify({ detail: "Audit event missing" }), {
          headers: { "Content-Type": "application/json" },
          status: 404
        })
    );

    renderWithQueryClient(
      <DetailDrawerProvider>
        <DrawerHarness />
      </DetailDrawerProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "Open audit event" }));

    expect(await screen.findByText("Audit event missing")).toBeInTheDocument();
  });
});

function mockAuditFetch(events: Record<string, Record<string, unknown>> = {}) {
  const eventMap = {
    evt_1: {
      id: "evt_1",
      event_type: "audit.event",
      source_component: "test",
      correlation_id: "corr_1",
      payload_json: { reason: "baseline" },
      created_at: "2026-05-02T00:00:00Z"
    },
    evt_2: {
      id: "evt_2",
      event_type: "policy.decision",
      policy_id: "pol_2",
      decision: "allow",
      correlation_id: "corr_1",
      payload_json: { matched_rule: "allow-safe", reason: "safe" },
      created_at: "2026-05-02T00:01:00Z"
    },
    ...events
  };

  vi.stubGlobal("fetch", async (url: string) => {
    if (url.includes("/verify")) {
      return json({ valid: true, checked_count: 1 });
    }
    if (url.includes("/audit/events?")) {
      return json(Object.values(eventMap));
    }
    const eventId = url.split("/").pop() ?? "";
    return json(eventMap[eventId as keyof typeof eventMap]);
  });
}

function json(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
      status
    })
  );
}
