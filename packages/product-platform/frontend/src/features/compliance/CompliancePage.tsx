import { FileCheck2, FileText, ShieldAlert, ShieldCheck, Timeline } from "lucide-react";
import { useMemo, useState, type FormEvent, type InputHTMLAttributes } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  getAuditEvent,
  listAuditEvents,
  verifyAuditEvent,
  type AuditEvent,
  type AuditVerification
} from "../../api/audit";
import type { TenantContext } from "../../api/client";
import {
  attestComplianceReport,
  createComplianceReport,
  exportAuditEvents,
  generateComplianceReport,
  getComplianceReport,
  listArtifacts,
  listComplianceControls,
  listComplianceEvidence,
  listComplianceFrameworks,
  listComplianceReports,
  listComplianceViolations,
  patchComplianceViolation,
  recomputeComplianceEvidence,
  useComplianceMutation,
  type Artifact,
  type ComplianceControl,
  type ComplianceEvidence,
  type ComplianceEvidenceRecompute,
  type ComplianceFramework,
  type ComplianceParams,
  type ComplianceReport,
  type ComplianceViolation
} from "../../api/compliance";
import { scopedQueryKey, useTenantQueryScope } from "../../api/queryScope";
import { useDetailDrawer } from "../../app/drawerContext";
import { PageHeader } from "../../components/layout/PageHeader";
import { ActionFeedback, useActionFeedback } from "../../components/shared/ActionFeedback";
import { EmptyState } from "../../components/shared/EmptyState";
import { QueryErrorSummary } from "../../components/shared/ErrorState";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "../../components/ui/table";
import { cn } from "../../lib/utils";

export function CompliancePage() {
  const [auditFilters, setAuditFilters] = useState<ComplianceParams>({});
  const [evidenceFilters, setEvidenceFilters] = useState<ComplianceParams>({});
  const [violationFilters, setViolationFilters] = useState<ComplianceParams>({});
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [auditExport, setAuditExport] = useState<string | null>(null);
  const [evidenceRecompute, setEvidenceRecompute] =
    useState<ComplianceEvidenceRecompute | null>(null);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [attestationId, setAttestationId] = useState<string | null>(null);
  const { feedback, runWithFeedback } = useActionFeedback();
  const scope = useTenantQueryScope();

  const auditEventsQuery = useQuery({
    queryKey: scopedQueryKey(["audit", "events", auditFilters], scope),
    queryFn: () => listAuditEvents(auditFilters, scope.context)
  });
  const auditEvents = auditEventsQuery.data ?? [];
  const activeEventId = selectedEventId ?? auditEvents[0]?.id ?? null;
  const activeListEvent = auditEvents.find((event) => event.id === activeEventId) ?? auditEvents[0] ?? null;
  const activeEventQuery = useQuery({
    enabled: Boolean(activeEventId),
    queryKey: scopedQueryKey(["audit", "events", activeEventId], scope),
    queryFn: () => getAuditEvent(activeEventId as string, scope.context)
  });
  const activeEvent = activeEventQuery.data ?? activeListEvent;
  const verificationQuery = useQuery({
    enabled: Boolean(activeEventId),
    queryKey: scopedQueryKey(["audit", "events", activeEventId, "verification"], scope),
    queryFn: () => verifyAuditEvent(activeEventId as string, scope.context)
  });
  const relatedEventsQuery = useQuery({
    enabled: Boolean(activeEvent?.correlation_id),
    queryKey: scopedQueryKey(["audit", "events", "correlation", activeEvent?.correlation_id], scope),
    queryFn: () => listAuditEvents({ correlation_id: activeEvent?.correlation_id }, scope.context)
  });
  const frameworksQuery = useQuery({
    queryKey: scopedQueryKey(["compliance", "frameworks"], scope),
    queryFn: () => listComplianceFrameworks(scope.context)
  });
  const controlsQuery = useQuery({
    queryKey: scopedQueryKey(["compliance", "controls"], scope),
    queryFn: () => listComplianceControls({}, scope.context)
  });
  const evidenceQuery = useQuery({
    queryKey: scopedQueryKey(["compliance", "evidence", evidenceFilters], scope),
    queryFn: () => listComplianceEvidence(evidenceFilters, scope.context)
  });
  const violationsQuery = useQuery({
    queryKey: scopedQueryKey(["compliance", "violations", violationFilters], scope),
    queryFn: () => listComplianceViolations(violationFilters, scope.context)
  });
  const reportsQuery = useQuery({
    queryKey: scopedQueryKey(["compliance", "reports"], scope),
    queryFn: () => listComplianceReports({}, scope.context)
  });
  const artifactsQuery = useQuery({
    queryKey: scopedQueryKey(["artifacts", "compliance.report"], scope),
    queryFn: () => listArtifacts({ artifact_type: "compliance.report" }, scope.context)
  });
  const activeReportId = selectedReportId ?? reportsQuery.data?.[0]?.id ?? null;
  const selectedReportQuery = useQuery({
    enabled: Boolean(activeReportId),
    queryKey: scopedQueryKey(["compliance", "reports", activeReportId], scope),
    queryFn: () => getComplianceReport(activeReportId as string, scope.context)
  });
  const mutation = useComplianceMutation();
  const drawer = useDetailDrawer();

  async function runTask(label: string, task: (tenantContext: TenantContext) => Promise<unknown>) {
    await runWithFeedback(() => mutation.mutateAsync(task), {
      errorMessage: `${label} failed`,
      successMessage: label
    });
  }

  return (
    <>
      <PageHeader
        title="Compliance"
        description="Audit explorer, control evidence, violations, and report attestations."
      />
      <div className="space-y-6 p-6" data-compliance-workspace>
        <ActionFeedback feedback={feedback} />
        <QueryErrorSummary
          items={[
            { error: auditEventsQuery.error, isError: auditEventsQuery.isError, label: "Audit events", onRetry: () => void auditEventsQuery.refetch() },
            { error: activeEventQuery.error, isError: activeEventQuery.isError, label: "Audit event detail", onRetry: () => void activeEventQuery.refetch() },
            { error: verificationQuery.error, isError: verificationQuery.isError, label: "Audit verification", onRetry: () => void verificationQuery.refetch() },
            { error: relatedEventsQuery.error, isError: relatedEventsQuery.isError, label: "Related audit events", onRetry: () => void relatedEventsQuery.refetch() },
            { error: frameworksQuery.error, isError: frameworksQuery.isError, label: "Compliance frameworks", onRetry: () => void frameworksQuery.refetch() },
            { error: controlsQuery.error, isError: controlsQuery.isError, label: "Compliance controls", onRetry: () => void controlsQuery.refetch() },
            { error: evidenceQuery.error, isError: evidenceQuery.isError, label: "Compliance evidence", onRetry: () => void evidenceQuery.refetch() },
            { error: violationsQuery.error, isError: violationsQuery.isError, label: "Compliance violations", onRetry: () => void violationsQuery.refetch() },
            { error: reportsQuery.error, isError: reportsQuery.isError, label: "Compliance reports", onRetry: () => void reportsQuery.refetch() },
            { error: artifactsQuery.error, isError: artifactsQuery.isError, label: "Compliance artifacts", onRetry: () => void artifactsQuery.refetch() },
            { error: selectedReportQuery.error, isError: selectedReportQuery.isError, label: "Report detail", onRetry: () => void selectedReportQuery.refetch() }
          ]}
        />
        <AuditExplorer
          events={auditEvents}
          exportResult={auditExport}
          filters={auditFilters}
          isLoading={auditEventsQuery.isLoading}
          onExport={async (payload) => {
            const result = await runWithFeedback<{ artifact_uri?: string }>(
              () =>
                mutation.mutateAsync((tenantContext) =>
                  exportAuditEvents(payload, tenantContext)
                ) as Promise<{ artifact_uri?: string }>,
              {
                errorMessage: "Audit export failed"
              }
            );
            if (!result) {
              return;
            }
            setAuditExport(result.artifact_uri ?? "audit-export");
          }}
          onFilter={setAuditFilters}
          onOpenEvent={(eventId) => {
            setSelectedEventId(eventId);
            void drawer.openAuditEvent(eventId);
          }}
          relatedEvents={relatedEventsQuery.data ?? []}
          selectedEvent={activeEvent}
          verification={verificationQuery.data ?? null}
        />
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(26rem,0.8fr)]">
          <ControlMap
            controls={controlsQuery.data ?? []}
            evidence={evidenceQuery.data ?? []}
            frameworks={frameworksQuery.data ?? []}
          />
          <EvidenceLibrary
            controls={controlsQuery.data ?? []}
            evidence={evidenceQuery.data ?? []}
            filters={evidenceFilters}
            onFilter={setEvidenceFilters}
            onRecompute={async () => {
              const result = await runWithFeedback<ComplianceEvidenceRecompute>(
                () =>
                  mutation.mutateAsync((tenantContext) =>
                    recomputeComplianceEvidence(tenantContext)
                  ) as Promise<ComplianceEvidenceRecompute>,
                {
                  errorMessage: "Evidence recompute failed"
                }
              );
              if (!result) {
                return;
              }
              setEvidenceRecompute(result);
            }}
            recomputeResult={evidenceRecompute}
          />
        </div>
        <ViolationQueue
          filters={violationFilters}
          onAcknowledge={(violationId) =>
            runTask("Violation acknowledged", (tenantContext) =>
              patchComplianceViolation(violationId, { status: "acknowledged" }, tenantContext)
            )
          }
          onFilter={setViolationFilters}
          onResolve={(violationId, reason) =>
            runTask("Violation resolved", (tenantContext) =>
              patchComplianceViolation(
                violationId,
                { status: "resolved", reason },
                tenantContext
              )
            )
          }
          violations={violationsQuery.data ?? []}
        />
        <ReportBuilder
          artifacts={artifactsQuery.data ?? []}
          attestationId={attestationId}
          frameworks={frameworksQuery.data ?? []}
          onAttest={async (reportId, payload) => {
            const result = await runWithFeedback<{ id?: string }>(
              () =>
                mutation.mutateAsync((tenantContext) =>
                  attestComplianceReport(reportId, payload, tenantContext)
                ) as Promise<{ id?: string }>,
              {
                errorMessage: "Report attestation failed"
              }
            );
            if (!result) {
              return;
            }
            setAttestationId(result.id ?? "attested");
          }}
          onCreate={async (payload) => {
            const report = await runWithFeedback<ComplianceReport>(
              () =>
                mutation.mutateAsync((tenantContext) =>
                  createComplianceReport(payload, tenantContext)
                ) as Promise<ComplianceReport>,
              {
                errorMessage: "Report creation failed",
                successMessage: (value) => `Created ${value.name}`
              }
            );
            if (!report) {
              return;
            }
            setSelectedReportId(report.id);
          }}
          onGenerate={async (reportId) => {
            const report = await runWithFeedback<ComplianceReport>(
              () =>
                mutation.mutateAsync((tenantContext) =>
                  generateComplianceReport(reportId, tenantContext)
                ) as Promise<ComplianceReport>,
              {
                errorMessage: "Report generation failed",
                successMessage: (value) => `Generated ${value.name}`
              }
            );
            if (!report) {
              return;
            }
            setSelectedReportId(report.id);
          }}
          onOpen={setSelectedReportId}
          reports={reportsQuery.data ?? []}
          selectedReport={selectedReportQuery.data ?? reportsQuery.data?.[0] ?? null}
        />
      </div>
    </>
  );
}

function AuditExplorer({
  events,
  exportResult,
  filters,
  isLoading,
  onExport,
  onFilter,
  onOpenEvent,
  relatedEvents,
  selectedEvent,
  verification
}: {
  events: AuditEvent[];
  exportResult: string | null;
  filters: ComplianceParams;
  isLoading: boolean;
  onExport: (payload: Record<string, unknown>) => void;
  onFilter: (filters: ComplianceParams) => void;
  onOpenEvent: (eventId: string) => void;
  relatedEvents: AuditEvent[];
  selectedEvent: AuditEvent | null;
  verification: AuditVerification | null;
}) {
  function submitFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter(cleanParamsFromForm(event.currentTarget, [
      "event_type",
      "source_component",
      "actor_id",
      "resource_type",
      "resource_id",
      "decision",
      "severity",
      "correlation_id"
    ]));
  }

  return (
    <Card data-compliance-audit-explorer>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Timeline className="h-4 w-4" />
              Audit Events
            </CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">{events.length} events in view.</p>
          </div>
          <Badge tone={isLoading ? "warning" : "success"}>{isLoading ? "Loading" : "Ready"}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3 md:grid-cols-9" onSubmit={submitFilter}>
          <Field label="Event" name="event_type" defaultValue={String(filters.event_type ?? "")} placeholder="policy.decision" />
          <Field label="Source" name="source_component" defaultValue={String(filters.source_component ?? "")} placeholder="policy-engine" />
          <Field label="Actor" name="actor_id" defaultValue={String(filters.actor_id ?? "")} placeholder="user id" />
          <Field label="Resource Type" name="resource_type" defaultValue={String(filters.resource_type ?? "")} placeholder="policy_evaluation" />
          <Field label="Resource" name="resource_id" defaultValue={String(filters.resource_id ?? "")} placeholder="resource id" />
          <SelectField defaultValue={String(filters.decision ?? "")} label="Decision" name="decision" options={["", "allow", "deny", "allowed", "denied"]} />
          <Field label="Severity" name="severity" defaultValue={String(filters.severity ?? "")} placeholder="warning" />
          <Field label="Correlation" name="correlation_id" defaultValue={String(filters.correlation_id ?? "")} placeholder="correlation id" />
          <div className="flex items-end">
            <Button type="submit" variant="outline">
              Filter
            </Button>
          </div>
        </form>
        <form
          className="flex flex-wrap items-end gap-3 rounded-md border bg-muted/20 p-3"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            onExport({
              format: formString(data, "format") || "json",
              filters: auditEventFilterParams(filters)
            });
          }}
        >
          <SelectField label="Format" name="format" options={["json", "csv", "markdown"]} />
          <Button type="submit">
            Export
          </Button>
          {exportResult ? <output className="text-sm text-muted-foreground">{exportResult}</output> : null}
        </form>
        {events.length ? (
          <div className="overflow-x-auto">
            <Table data-compliance-audit-table>
              <TableHeader>
                <TableRow>
                  <TableHead>Event</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>Decision</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => (
                  <TableRow data-compliance-audit-row={event.id} key={event.id}>
                    <TableCell>
                      <strong>{event.event_type}</strong>
                      <small className="block text-muted-foreground">{event.id}</small>
                    </TableCell>
                    <TableCell>{event.source_component ?? "n/a"}</TableCell>
                    <TableCell>{[event.actor_type, event.actor_id].filter(Boolean).join(" / ") || "n/a"}</TableCell>
                    <TableCell>{[event.resource_type, event.resource_id].filter(Boolean).join(" / ") || "n/a"}</TableCell>
                    <TableCell>{event.decision ?? "n/a"}</TableCell>
                    <TableCell>
                      <StatusBadge status={event.severity ?? "info"} />
                    </TableCell>
                    <TableCell>
                      <Button onClick={() => onOpenEvent(event.id)} type="button" variant="outline">
                        Open
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <EmptyState description="Adjust filters or run a governed workflow." title="No events" />
        )}
        <div className="grid gap-4 lg:grid-cols-2">
          <AuditVerificationPanel event={selectedEvent} verification={verification} />
          <CorrelationTimeline currentEvent={selectedEvent} events={relatedEvents.length ? relatedEvents : events} />
        </div>
      </CardContent>
    </Card>
  );
}

function AuditVerificationPanel({
  event,
  verification
}: {
  event: AuditEvent | null;
  verification: AuditVerification | null;
}) {
  if (!event) {
    return null;
  }
  const label = verification?.valid ? "verified" : verification ? "failed" : "pending";
  return (
    <section className="rounded-md border p-3" data-compliance-hash-verification={event.id}>
      <h3 className="font-semibold">Hash Verification</h3>
      <StatusBadge status={label} />
      <p className="mt-2 text-sm text-muted-foreground">
        {verification?.reason ?? `${verification?.checked_count ?? 0} event(s) checked`}
      </p>
    </section>
  );
}

function CorrelationTimeline({
  currentEvent,
  events
}: {
  currentEvent: AuditEvent | null;
  events: AuditEvent[];
}) {
  if (!currentEvent) {
    return null;
  }
  const related = [...events]
    .filter((event) => event.correlation_id && event.correlation_id === currentEvent.correlation_id)
    .sort((left, right) => String(left.created_at).localeCompare(String(right.created_at)));
  return (
    <section className="rounded-md border p-3" data-compliance-correlation-timeline={currentEvent.correlation_id ?? ""}>
      <h3 className="font-semibold">Correlation Timeline</h3>
      {related.length ? (
        <ol className="mt-3 space-y-2">
          {related.map((event) => (
            <li className="rounded-md bg-muted p-2 text-sm" key={event.id}>
              <strong>{event.event_type}</strong>
              <span className="block text-muted-foreground">{event.id}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">Single event</p>
      )}
    </section>
  );
}

function ControlMap({
  controls,
  evidence,
  frameworks
}: {
  controls: ComplianceControl[];
  evidence: ComplianceEvidence[];
  frameworks: ComplianceFramework[];
}) {
  const evidenceByControl = useMemo(() => groupEvidenceByControl(evidence), [evidence]);
  return (
    <Card data-compliance-control-map>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4" />
          Framework Controls
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2" data-compliance-framework-tabs>
          {frameworks.map((framework) => (
            <Badge key={framework.id} tone="muted">
              {framework.name} {framework.version}
            </Badge>
          ))}
        </div>
        {controls.length ? (
          <Table data-compliance-control-table>
            <TableHeader>
              <TableRow>
                <TableHead>Framework</TableHead>
                <TableHead>Control</TableHead>
                <TableHead>Required Evidence</TableHead>
                <TableHead>Fresh Evidence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {controls.map((control) => {
                const linkedEvidence = evidenceByControl.get(control.id) ?? [];
                return (
                  <TableRow data-compliance-control-row={control.id} key={control.id}>
                    <TableCell>{control.framework_name ?? control.framework_id}</TableCell>
                    <TableCell>
                      <strong>{control.control_code}</strong>
                      <small className="block text-muted-foreground">{control.title}</small>
                    </TableCell>
                    <TableCell>{(control.required_evidence_types ?? []).join(", ") || "n/a"}</TableCell>
                    <TableCell>
                      <Badge tone={linkedEvidence.length ? "success" : "warning"}>
                        {linkedEvidence.length}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        ) : (
          <EmptyState description="Seed or import a framework to populate controls." title="No controls" />
        )}
      </CardContent>
    </Card>
  );
}

function EvidenceLibrary({
  controls,
  evidence,
  filters,
  onFilter,
  onRecompute,
  recomputeResult
}: {
  controls: ComplianceControl[];
  evidence: ComplianceEvidence[];
  filters: ComplianceParams;
  onFilter: (filters: ComplianceParams) => void;
  onRecompute: () => void;
  recomputeResult: ComplianceEvidenceRecompute | null;
}) {
  return (
    <Card data-compliance-evidence-library>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileCheck2 className="h-4 w-4" />
          Mapped Evidence
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="grid gap-3 md:grid-cols-3"
          onSubmit={(event) => {
            event.preventDefault();
            onFilter(cleanParamsFromForm(event.currentTarget, ["control_id", "status"]));
          }}
        >
          <label className="space-y-1">
            <span className="text-sm font-medium">Control</span>
            <select className="h-9 w-full rounded-md border bg-background px-3 text-sm" defaultValue={String(filters.control_id ?? "")} name="control_id">
              <option value="">Any</option>
              {controls.map((control) => (
                <option key={control.id} value={control.id}>
                  {control.control_code}
                </option>
              ))}
            </select>
          </label>
          <SelectField defaultValue={String(filters.status ?? "")} label="Status" name="status" options={["", "fresh", "stale", "missing"]} />
          <div className="flex items-end gap-2">
            <Button type="submit" variant="outline">
              Filter
            </Button>
            <Button onClick={onRecompute} type="button" variant="secondary">
              Recompute Evidence
            </Button>
          </div>
        </form>
        {recomputeResult ? (
          <p className="rounded-md border bg-muted p-3 text-sm" data-compliance-evidence-recompute-result>
            {recomputeResult.evidence_count ?? 0} mapped / {recomputeResult.refreshed_count ?? 0} refreshed
          </p>
        ) : null}
        {evidence.length ? (
          <Table data-compliance-evidence-table>
            <TableHeader>
              <TableRow>
                <TableHead>Control</TableHead>
                <TableHead>Evidence</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {evidence.map((item) => (
                <TableRow data-compliance-evidence-row={item.id} key={item.id}>
                  <TableCell>{item.control_code ?? item.control_id}</TableCell>
                  <TableCell>
                    <strong>{item.title}</strong>
                    <small className="block text-muted-foreground">{item.summary}</small>
                  </TableCell>
                  <TableCell>{`${item.source_type}:${item.source_id}`}</TableCell>
                  <TableCell>
                    <StatusBadge status={item.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState description="Run recompute to map evidence from audit events." title="No evidence" />
        )}
      </CardContent>
    </Card>
  );
}

function ViolationQueue({
  filters,
  onAcknowledge,
  onFilter,
  onResolve,
  violations
}: {
  filters: ComplianceParams;
  onAcknowledge: (violationId: string) => void;
  onFilter: (filters: ComplianceParams) => void;
  onResolve: (violationId: string, reason: string) => void;
  violations: ComplianceViolation[];
}) {
  return (
    <Card data-compliance-violations>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4" />
          Violation Queue
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="grid gap-3 md:grid-cols-3"
          onSubmit={(event) => {
            event.preventDefault();
            onFilter(cleanParamsFromForm(event.currentTarget, ["status", "severity", "control_id", "agent_id"]));
          }}
        >
          <SelectField defaultValue={String(filters.status ?? "")} label="Status" name="status" options={["", "open", "acknowledged", "resolved"]} />
          <SelectField defaultValue={String(filters.severity ?? "")} label="Severity" name="severity" options={["", "warning", "high", "critical"]} />
          <div className="flex items-end">
            <Button type="submit" variant="outline">
              Filter
            </Button>
          </div>
        </form>
        {violations.length ? (
          <Table data-compliance-violation-table>
            <TableHeader>
              <TableRow>
                <TableHead>Control</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {violations.map((violation) => (
                <TableRow data-compliance-violation-row={violation.id} key={violation.id}>
                  <TableCell>{violation.control_code ?? violation.control_id}</TableCell>
                  <TableCell>
                    <StatusBadge status={violation.severity} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={violation.status} />
                  </TableCell>
                  <TableCell>
                    <strong>{violation.reason}</strong>
                    <small className="block text-muted-foreground">{violation.resolution_reason}</small>
                  </TableCell>
                  <TableCell>
                    <div className="space-y-2">
                      <Button
                        disabled={violation.status === "resolved"}
                        onClick={() => onAcknowledge(violation.id)}
                        type="button"
                        variant="outline"
                      >
                        Acknowledge
                      </Button>
                      <form
                        className="flex gap-2"
                        onSubmit={(event) => {
                          event.preventDefault();
                          const form = new FormData(event.currentTarget);
                          onResolve(violation.id, formString(form, "reason"));
                        }}
                      >
                        <Input name="reason" placeholder="Resolution reason" required />
                        <Button disabled={violation.status === "resolved"} type="submit" variant="ghost">
                          Resolve
                        </Button>
                      </form>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState description="Queue is clear." title="No violations" />
        )}
      </CardContent>
    </Card>
  );
}

function ReportBuilder({
  artifacts,
  attestationId,
  frameworks,
  onAttest,
  onCreate,
  onGenerate,
  onOpen,
  reports,
  selectedReport
}: {
  artifacts: Artifact[];
  attestationId: string | null;
  frameworks: ComplianceFramework[];
  onAttest: (reportId: string, payload: Record<string, unknown>) => void;
  onCreate: (payload: Record<string, unknown>) => void;
  onGenerate: (reportId: string) => void;
  onOpen: (reportId: string) => void;
  reports: ComplianceReport[];
  selectedReport: ComplianceReport | null;
}) {
  const activeArtifacts = selectedReport
    ? artifacts.filter((artifact) =>
        (artifact.links ?? []).some(
          (link) => link.target_type === "compliance_report" && link.target_id === selectedReport.id
        )
      )
    : [];

  return (
    <Card data-compliance-reports>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-4 w-4" />
          Report Builder
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form
          className="grid gap-3 md:grid-cols-5"
          onSubmit={(event) => {
            event.preventDefault();
            onCreate(cleanParamsFromForm(event.currentTarget, ["framework_id", "name", "date_from", "date_to"]));
          }}
        >
          <label className="space-y-1">
            <span className="text-sm font-medium">Framework</span>
            <select className="h-9 w-full rounded-md border bg-background px-3 text-sm" name="framework_id" required>
              {frameworks.map((framework) => (
                <option key={framework.id} value={framework.id}>
                  {framework.name}
                </option>
              ))}
            </select>
          </label>
          <Field label="Name" name="name" placeholder="SOC 2 Evidence Report" />
          <Field label="From" name="date_from" placeholder="2026-01-01" />
          <Field label="To" name="date_to" placeholder="2026-12-31" />
          <div className="flex items-end">
            <Button type="submit">Create Draft</Button>
          </div>
        </form>
        {reports.length ? (
          <Table data-compliance-report-table>
            <TableHeader>
              <TableRow>
                <TableHead>Report</TableHead>
                <TableHead>Framework</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Evidence</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {reports.map((report) => (
                <TableRow data-compliance-report-row={report.id} key={report.id}>
                  <TableCell>
                    <strong>{report.name}</strong>
                    <small className="block text-muted-foreground">
                      {report.date_from} to {report.date_to}
                    </small>
                  </TableCell>
                  <TableCell>{report.framework_name ?? report.framework_id}</TableCell>
                  <TableCell>
                    <StatusBadge status={report.status} />
                  </TableCell>
                  <TableCell>{report.evidence_item_ids?.length ?? 0}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-2">
                      <Button onClick={() => onOpen(report.id)} type="button" variant="outline">
                        Open
                      </Button>
                      <Button onClick={() => onGenerate(report.id)} type="button" variant="secondary">
                        Generate
                      </Button>
                      {report.artifact_uri ? (
                        <a className="text-sm font-medium underline" href={`/api/v1/compliance/reports/${encodeURIComponent(report.id)}/download`}>
                          Download
                        </a>
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState description="Create a draft report from a framework and date range." title="No reports" />
        )}
        {selectedReport ? (
          <section className="rounded-md border p-4" data-compliance-report-preview={selectedReport.id}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-semibold">{selectedReport.name}</h3>
              <Badge tone="muted">{selectedReport.artifact_uri ?? "draft"}</Badge>
            </div>
            {activeArtifacts.length ? (
              <ul className="mt-3 space-y-2" data-compliance-report-artifacts={selectedReport.id}>
                {activeArtifacts.map((artifact) => (
                  <li className="rounded-md bg-muted p-2 text-sm" data-compliance-report-artifact={artifact.id} key={artifact.id}>
                    <strong>{artifact.name}</strong>
                    <code className="ml-2">{artifact.checksum}</code>
                  </li>
                ))}
              </ul>
            ) : null}
            <pre className="mt-3 max-h-72 overflow-auto rounded-md bg-muted p-3 text-xs">
              {selectedReport.rendered_markdown ?? "Generate report"}
            </pre>
            <form
              className="mt-3 flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                const form = new FormData(event.currentTarget);
                onAttest(selectedReport.id, {
                  statement: formString(form, "statement"),
                  signature_ref: formString(form, "signature_ref") || undefined
                });
              }}
            >
              <Field label="Statement" name="statement" placeholder="I attest this report" required />
              <Field label="Signature" name="signature_ref" placeholder="optional" />
              <Button disabled={!selectedReport.artifact_uri} type="submit">
                Attest
              </Button>
              {attestationId ? <output className="text-sm text-muted-foreground">{attestationId}</output> : null}
            </form>
          </section>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Field({
  className,
  label,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <Label className={cn("space-y-1", className)}>
      <span>{label}</span>
      <Input {...props} />
    </Label>
  );
}

function SelectField({
  className,
  defaultValue,
  label,
  name,
  options
}: {
  className?: string;
  defaultValue?: string;
  label: string;
  name: string;
  options: string[];
}) {
  return (
    <label className={cn("space-y-1", className)}>
      <span className="text-sm font-medium">{label}</span>
      <select className="h-9 w-full rounded-md border bg-background px-3 text-sm" defaultValue={defaultValue} name={name}>
        {options.map((option) => (
          <option key={option || "any"} value={option}>
            {option || "Any"}
          </option>
        ))}
      </select>
    </label>
  );
}

function groupEvidenceByControl(evidence: ComplianceEvidence[]) {
  const grouped = new Map<string, ComplianceEvidence[]>();
  for (const item of evidence) {
    const rows = grouped.get(item.control_id) ?? [];
    rows.push(item);
    grouped.set(item.control_id, rows);
  }
  return grouped;
}

function auditEventFilterParams(filters: ComplianceParams) {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}

function cleanParamsFromForm(form: HTMLFormElement, keys: string[]) {
  const data = new FormData(form);
  return Object.fromEntries(
    keys
      .map((key) => [key, formString(data, key)])
      .filter(([, value]) => value !== "")
  );
}

function formString(form: FormData, key: string) {
  return String(form.get(key) ?? "").trim();
}
