import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DetailDrawerProvider } from "../../app/drawerContext";
import { renderWithQueryClient } from "../../test/test-utils";
import { CompliancePage } from "./CompliancePage";

const policyEvent = {
  id: "evt_policy",
  organization_id: "org_default",
  environment_id: "env_default",
  event_type: "policy.decision",
  source_component: "policy-engine",
  actor_type: "user",
  actor_id: "user_admin",
  agent_id: "agent_1",
  resource_type: "policy_evaluation",
  resource_id: "peval_1",
  decision: "deny",
  severity: "warning",
  correlation_id: "corr-1",
  policy_id: "policy_1",
  policy_version_id: "pver_1",
  payload_json: { matched_rule: "deny_delete", reason: "blocked" },
  created_at: "2026-05-01T00:00:00+00:00"
};

const runtimeEvent = {
  ...policyEvent,
  id: "evt_runtime",
  event_type: "runtime.action",
  source_component: "runtime-control",
  resource_type: "runtime_action",
  resource_id: "raction_1",
  decision: "allow",
  severity: "info",
  created_at: "2026-05-01T00:00:01+00:00"
};

const framework = {
  id: "cf_soc2_org_default",
  organization_id: "org_default",
  name: "SOC 2",
  version: "2026",
  description: "Trust services",
  status: "active",
  created_at: "2026-05-01T00:00:00+00:00"
};

const control = {
  id: "ctrl_soc2_cc6_6_org_default",
  framework_id: framework.id,
  framework_name: "SOC 2",
  control_code: "CC6.6",
  title: "Policy Enforcement",
  description: "Policy decisions are recorded.",
  required_evidence_types: ["policy_decision"],
  owner_user_id: "user_admin"
};

const evidence = {
  id: "evid_policy",
  organization_id: "org_default",
  environment_id: "env_default",
  control_id: control.id,
  control_code: "CC6.6",
  source_type: "audit_event",
  source_id: "evt_policy",
  title: "policy_decision evidence from policy.decision",
  summary: "policy-engine recorded policy.decision decision=deny",
  freshness_at: "2026-05-01T00:00:00+00:00",
  status: "fresh",
  created_at: "2026-05-01T00:00:00+00:00"
};

const violation = {
  id: "cviol_1",
  organization_id: "org_default",
  environment_id: "env_default",
  control_id: control.id,
  control_code: "CC6.6",
  agent_id: "agent_1",
  severity: "critical",
  status: "open",
  reason: "blocked by policy",
  source_type: "audit_event",
  source_id: "evt_policy",
  source_event_id: "evt_policy",
  resolution_reason: null,
  created_at: "2026-05-01T00:00:00+00:00",
  updated_at: "2026-05-01T00:00:00+00:00"
};

const report = {
  id: "crep_1",
  organization_id: "org_default",
  environment_id: "env_default",
  framework_id: framework.id,
  framework_name: "SOC 2",
  name: "SOC 2 Evidence Report",
  status: "generated",
  date_from: "2026-01-01",
  date_to: "2026-12-31",
  generated_by: "user_admin",
  artifact_uri: "compliance-report://crep_1.md",
  summary: { evidence_count: 1, open_violation_count: 1 },
  created_at: "2026-05-01T00:00:00+00:00",
  updated_at: "2026-05-01T00:00:00+00:00",
  generated_at: "2026-05-01T00:00:00+00:00",
  evidence_item_ids: ["evid_policy"],
  attestation_count: 0,
  rendered_markdown: "# SOC 2 Evidence Report\n\n## Evidence\n"
};

const reportArtifact = {
  id: "art_report_1",
  organization_id: "org_default",
  environment_id: "env_default",
  artifact_type: "compliance.report",
  name: "crep_1.md",
  content_type: "text/markdown",
  storage_uri: "local-artifact://org_default/env_default/art_report_1/crep_1.md",
  checksum: "sha256-report",
  size_bytes: 1024,
  created_by: "user_admin",
  created_at: "2026-05-01T00:00:00+00:00",
  links: [
    {
      id: "alink_report_1",
      artifact_id: "art_report_1",
      target_type: "compliance_report",
      target_id: "crep_1",
      link_type: "report",
      created_at: "2026-05-01T00:00:00+00:00"
    }
  ]
};

describe("CompliancePage", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/compliance");
    mockComplianceFetch();
  });

  it("renders audit explorer, controls, evidence, violations, and reports", async () => {
    renderWithQueryClient(
      <DetailDrawerProvider>
        <CompliancePage />
      </DetailDrawerProvider>
    );

    expect(await screen.findByText("Audit Events")).toBeInTheDocument();
    expect((await screen.findAllByText("policy.decision")).length).toBeGreaterThan(0);
    expect(screen.getByText("Hash Verification")).toBeInTheDocument();
    expect(screen.getByText("Correlation Timeline")).toBeInTheDocument();
    expect(screen.getByText("Framework Controls")).toBeInTheDocument();
    expect(screen.getAllByText("CC6.6").length).toBeGreaterThan(0);
    expect(screen.getByText("Mapped Evidence")).toBeInTheDocument();
    expect(screen.getByText("policy_decision evidence from policy.decision")).toBeInTheDocument();
    expect(screen.getByText("Violation Queue")).toBeInTheDocument();
    expect(screen.getByText("blocked by policy")).toBeInTheDocument();
    expect(screen.getByText("Report Builder")).toBeInTheDocument();
    expect(screen.getAllByText("SOC 2 Evidence Report").length).toBeGreaterThan(0);
    expect(screen.getByText("sha256-report")).toBeInTheDocument();
  });

  it("filters, exports, opens audit drawer, recomputes evidence, patches violations, and attests", async () => {
    const calls = mockComplianceFetch();
    renderWithQueryClient(
      <DetailDrawerProvider>
        <CompliancePage />
      </DetailDrawerProvider>
    );

    expect(await screen.findByText("Audit Events")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Source"), { target: { value: "policy-engine" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Filter" })[0]);
    await waitFor(() =>
      expect(calls).toContain("/api/v1/audit/events?source_component=policy-engine")
    );

    fireEvent.click(screen.getByRole("button", { name: "Export" }));
    expect(await screen.findByText("audit-export://evt-policy.json")).toBeInTheDocument();

    const auditRow = screen.getAllByText("evt_policy")[0].closest("tr");
    expect(auditRow).toBeTruthy();
    fireEvent.click(within(auditRow as HTMLElement).getByRole("button", { name: "Open" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close detail drawer" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Recompute Evidence" }));
    expect(await screen.findByText("1 mapped / 1 refreshed")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Acknowledge" }));
    await waitFor(() =>
      expect(calls).toContain("/api/v1/compliance/violations/cviol_1")
    );

    fireEvent.change(screen.getByPlaceholderText("Resolution reason"), {
      target: { value: "remediated" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
    await waitFor(() =>
      expect(
        calls.filter((path) => path === "/api/v1/compliance/violations/cviol_1").length
      ).toBeGreaterThan(1)
    );

    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
    await waitFor(() =>
      expect(calls).toContain("/api/v1/compliance/reports/crep_1/generate")
    );

    fireEvent.change(screen.getByLabelText("Statement"), { target: { value: "I attest" } });
    fireEvent.click(screen.getByRole("button", { name: "Attest" }));
    expect(await screen.findByText("ratt_1")).toBeInTheDocument();
  });
});

function mockComplianceFetch() {
  const calls: string[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const parsed = new URL(url, "http://test.local");
    const path = `${parsed.pathname}${parsed.search}`;
    calls.push(path);

    if (path === "/api/v1/audit/events/evt_policy") {
      return json(policyEvent);
    }
    if (path === "/api/v1/audit/events/evt_policy/verify" && init?.method === "POST") {
      return json({ valid: true, checked_count: 1 });
    }
    if (path.startsWith("/api/v1/audit/events?correlation_id=corr-1")) {
      return json([policyEvent, runtimeEvent]);
    }
    if (path.startsWith("/api/v1/audit/events")) {
      return json([policyEvent, runtimeEvent]);
    }
    if (path === "/api/v1/audit/export" && init?.method === "POST") {
      return json({ id: "aexp_1", artifact_uri: "audit-export://evt-policy.json" });
    }
    if (path === "/api/v1/compliance/frameworks") {
      return json([framework]);
    }
    if (path.startsWith("/api/v1/compliance/controls")) {
      return json([control]);
    }
    if (path === "/api/v1/compliance/evidence/recompute" && init?.method === "POST") {
      return json({ scanned_event_count: 2, evidence_count: 1, refreshed_count: 1 });
    }
    if (path.startsWith("/api/v1/compliance/evidence")) {
      return json([evidence]);
    }
    if (path.startsWith("/api/v1/compliance/violations/cviol_1") && init?.method === "PATCH") {
      return json({ ...violation, status: "acknowledged" });
    }
    if (path.startsWith("/api/v1/compliance/violations")) {
      return json([violation]);
    }
    if (path === "/api/v1/compliance/reports" && init?.method === "POST") {
      return json({ ...report, id: "crep_new", name: "Draft SOC 2 Report", status: "draft" });
    }
    if (path === "/api/v1/compliance/reports/crep_1/generate" && init?.method === "POST") {
      return json(report);
    }
    if (path === "/api/v1/compliance/reports/crep_1/attest" && init?.method === "POST") {
      return json({ id: "ratt_1", report_id: "crep_1", statement: "I attest" });
    }
    if (path === "/api/v1/compliance/reports/crep_1") {
      return json(report);
    }
    if (path.startsWith("/api/v1/compliance/reports")) {
      return json([report]);
    }
    if (path.startsWith("/api/v1/artifacts")) {
      return json([reportArtifact]);
    }
    return json({});
  });
  return calls;
}

function json(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
      status
    })
  );
}
