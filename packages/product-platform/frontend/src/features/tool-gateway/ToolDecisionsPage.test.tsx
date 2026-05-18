import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { ToolDecisionsPage } from "./ToolDecisionsPage";

const allowedAction = {
  id: "toolrun_allowed",
  organization_id: "org_demo",
  environment_id: "env_demo",
  request_id: "req-allowed",
  correlation_id: "corr-allowed",
  agent_id: "agent_claims",
  credential_id: "cred_1",
  tool_id: "tool_claims",
  permission_id: "perm_1",
  decision_id: "decision_allowed",
  action_status: "completed",
  reason_code: "allowed",
  upstream_status_code: 200,
  latency_ms: 18.5,
  payload_summary: { claim_id: "claim_123" },
  response_summary: { body: { claim_status: "open" }, redaction_applied: false },
  redaction_applied: false,
  error_code: null,
  created_at: "2026-05-01T12:00:00+00:00",
  updated_at: "2026-05-01T12:00:01+00:00"
};

const deniedAction = {
  ...allowedAction,
  id: "toolrun_denied",
  request_id: "req-denied",
  correlation_id: "corr-denied",
  permission_id: null,
  decision_id: "decision_denied",
  action_status: "denied",
  reason_code: "permission_missing",
  upstream_status_code: null,
  latency_ms: null,
  payload_summary: { claim_id: "claim_456" },
  response_summary: null,
  created_at: "2026-05-01T11:00:00+00:00",
  updated_at: "2026-05-01T11:00:01+00:00"
};

const deniedDetail = {
  ...deniedAction,
  events: [
    {
      id: "toolrunevt_denied",
      runtime_action_id: "toolrun_denied",
      event_type: "tool.runtime.denied",
      event_summary: { reason_code: "permission_missing" },
      created_at: "2026-05-01T11:00:01+00:00"
    }
  ]
};

const redactedDetail = {
  ...allowedAction,
  id: "toolrun_redacted",
  request_id: "req-redacted",
  redaction_applied: true,
  response_summary: {
    body: { claim_status: "open", token: "[redacted]" },
    redaction_applied: true
  },
  events: [
    {
      id: "toolrunevt_completed",
      runtime_action_id: "toolrun_redacted",
      event_type: "tool.runtime.completed",
      event_summary: { upstream_status_code: 200 },
      created_at: "2026-05-01T12:00:01+00:00"
    }
  ]
};

describe("ToolDecisionsPage", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/tool-gateway/decisions");
  });

  it("renders allowed and denied runtime action rows", async () => {
    mockToolRuntimeFetch([allowedAction, deniedAction]);

    renderWithQueryClient(<ToolDecisionsPage />);

    expect(await screen.findByText("Tool Gateway Decisions")).toBeInTheDocument();
    const rows = await screen.findAllByTestId("tool-runtime-action-row");
    expect(rows).toHaveLength(2);
    expect(screen.getByText("req-allowed")).toBeInTheDocument();
    expect(screen.getByText("req-denied")).toBeInTheDocument();
    expect(screen.getByText("permission missing")).toBeInTheDocument();
    expect(screen.getByText("18.5ms")).toBeInTheDocument();
  });

  it("renders a stable loading state", () => {
    let resolveResponse: (response: Response) => void = () => undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveResponse = resolve;
          })
      )
    );

    renderWithQueryClient(<ToolDecisionsPage />);

    expect(screen.getByTestId("tool-runtime-loading")).toBeInTheDocument();
    expect(screen.getByText("Loading decisions")).toBeInTheDocument();
    resolveResponse(json([]));
  });

  it("renders a recoverable API error state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ message: "backend unavailable" }, 500))
    );

    renderWithQueryClient(<ToolDecisionsPage />);

    expect(await screen.findByText("Unable to load tool decisions")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("paginates with limit and offset query parameters", async () => {
    const calls = mockToolRuntimeFetch(
      Array.from({ length: 25 }, (_, index) => ({
        ...allowedAction,
        id: `toolrun_${index}`,
        request_id: `req-${index}`
      }))
    );

    renderWithQueryClient(<ToolDecisionsPage />);

    expect(await screen.findByText("req-0")).toBeInTheDocument();
    const pager = screen.getByTestId("tool-runtime-pagination");
    fireEvent.click(within(pager).getByRole("button", { name: "Next" }));

    await waitFor(() =>
      expect(calls.some((call) => call === "/api/v1/tool-runtime/actions?limit=25&offset=25")).toBe(
        true
      )
    );
  });

  it("applies the status filter to the API query", async () => {
    const calls = mockToolRuntimeFetch([allowedAction, deniedAction]);

    renderWithQueryClient(<ToolDecisionsPage />);

    expect(await screen.findByText("req-allowed")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "denied" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() =>
      expect(calls.some((call) => call.includes("action_status=denied"))).toBe(true)
    );
  });

  it("applies the tool filter to the API query", async () => {
    const calls = mockToolRuntimeFetch([allowedAction]);

    renderWithQueryClient(<ToolDecisionsPage />);

    expect(await screen.findByText("req-allowed")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Tool ID"), { target: { value: "tool_claims" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() =>
      expect(calls.some((call) => call.includes("tool_id=tool_claims"))).toBe(true)
    );
  });

  it("applies the correlation filter to the API query", async () => {
    const calls = mockToolRuntimeFetch([allowedAction]);

    renderWithQueryClient(<ToolDecisionsPage />);

    expect(await screen.findByText("req-allowed")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Correlation"), { target: { value: "corr-allowed" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() =>
      expect(calls.some((call) => call.includes("correlation_id=corr-allowed"))).toBe(true)
    );
  });

  it("reset clears filters and pagination", async () => {
    const calls = mockToolRuntimeFetch(
      Array.from({ length: 25 }, (_, index) => ({
        ...allowedAction,
        id: `toolrun_reset_${index}`,
        request_id: `req-reset-${index}`
      }))
    );

    renderWithQueryClient(<ToolDecisionsPage />);

    expect(await screen.findByText("req-reset-0")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "denied" } });
    fireEvent.change(screen.getByLabelText("Tool ID"), { target: { value: "tool_claims" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() => expect(window.location.search).toContain("action_status=denied"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(window.location.search).toContain("offset=25"));

    fireEvent.click(screen.getByRole("button", { name: "Reset" }));

    await waitFor(() => expect(window.location.search).toBe(""));
    expect(screen.getByLabelText("Status")).toHaveValue("");
    expect(screen.getByLabelText("Tool ID")).toHaveValue("");
    expect(calls.at(-1)).toBe("/api/v1/tool-runtime/actions?limit=25&offset=0");
  });

  it("restores filter state from the URL", async () => {
    const calls = mockToolRuntimeFetch([deniedAction]);
    window.history.replaceState(
      null,
      "",
      "/tool-gateway/decisions?action_status=denied&correlation_id=corr-denied&tool_id=tool_claims&offset=25"
    );

    renderWithQueryClient(<ToolDecisionsPage />);

    expect(await screen.findByText("req-denied")).toBeInTheDocument();
    expect(screen.getByLabelText("Status")).toHaveValue("denied");
    expect(screen.getByLabelText("Correlation")).toHaveValue("corr-denied");
    expect(screen.getByLabelText("Tool ID")).toHaveValue("tool_claims");
    expect(calls[0]).toContain("action_status=denied");
    expect(calls[0]).toContain("correlation_id=corr-denied");
    expect(calls[0]).toContain("tool_id=tool_claims");
    expect(calls[0]).toContain("offset=25");
  });

  it("opens a detail drawer with denied reason code", async () => {
    mockToolRuntimeFetch([deniedAction], { toolrun_denied: deniedDetail });

    renderWithQueryClient(<ToolDecisionsPage />);

    const row = (await screen.findByText("req-denied")).closest("tr") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Open" }));

    const drawer = await screen.findByRole("dialog");
    expect(await within(drawer).findByText("permission missing")).toBeInTheDocument();
    expect(await within(drawer).findByText("decision_denied")).toBeInTheDocument();
  });

  it("shows the runtime event timeline in the drawer", async () => {
    mockToolRuntimeFetch([deniedAction], { toolrun_denied: deniedDetail });

    renderWithQueryClient(<ToolDecisionsPage />);

    const row = (await screen.findByText("req-denied")).closest("tr") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Open" }));

    const drawer = await screen.findByRole("dialog");
    expect(await within(drawer).findByText("tool.runtime.denied")).toBeInTheDocument();
  });

  it("renders agent and tool links in the drawer", async () => {
    mockToolRuntimeFetch([deniedAction], { toolrun_denied: deniedDetail });

    renderWithQueryClient(<ToolDecisionsPage />);

    const row = (await screen.findByText("req-denied")).closest("tr") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Open" }));

    const drawer = await screen.findByRole("dialog");
    expect(await within(drawer).findByRole("link", { name: "agent_claims" })).toHaveAttribute(
      "href",
      "/agents?agent_id=agent_claims"
    );
    expect(await within(drawer).findByRole("link", { name: "tool_claims" })).toHaveAttribute(
      "href",
      "/tool-gateway/decisions?tool_id=tool_claims"
    );
  });

  it("marks redacted responses in the drawer", async () => {
    mockToolRuntimeFetch(
      [{ ...allowedAction, id: "toolrun_redacted", request_id: "req-redacted" }],
      {
        toolrun_redacted: redactedDetail
      }
    );

    renderWithQueryClient(<ToolDecisionsPage />);

    const row = (await screen.findByText("req-redacted")).closest("tr") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Open" }));

    const drawer = await screen.findByRole("dialog");
    expect(await within(drawer).findByText("Redacted")).toBeInTheDocument();
    expect(await within(drawer).findByText(/\[redacted\]/)).toBeInTheDocument();
  });
});

function mockToolRuntimeFetch(
  actions: Array<Record<string, unknown>>,
  details: Record<string, Record<string, unknown>> = {}
) {
  const calls: string[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
    const parsed = new URL(String(input), "http://test.local");
    const path = `${parsed.pathname}${parsed.search}`;
    calls.push(path);
    if (parsed.pathname.startsWith("/api/v1/tool-runtime/actions/")) {
      const actionId = decodeURIComponent(parsed.pathname.split("/").at(-1) ?? "");
      return json(details[actionId] ?? { ...(actions[0] ?? {}), events: [] });
    }
    if (path.startsWith("/api/v1/tool-runtime/actions")) {
      return json(actions);
    }
    return json({});
  });
  return calls;
}

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}
