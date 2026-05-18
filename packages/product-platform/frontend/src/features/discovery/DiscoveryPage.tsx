import { Play, RefreshCw, Search, ShieldAlert } from "lucide-react";
import { useState, type FormEvent } from "react";

import {
  assignDiscoveryFindingOwner,
  createDiscoveryRun,
  markDiscoveryFindingDecommissioned,
  patchDiscoveryTargetSchedule,
  reconcileDiscoveryRun,
  registerDiscoveryFindingAgent,
  suppressDiscoveryFinding,
  useDiscoveryFindings,
  useDiscoveryMutation,
  useDiscoveryRuns,
  useDiscoveryScanners,
  useDiscoveryTargets,
  type DiscoveryFinding,
  type DiscoveryParams,
  type DiscoveryRun,
  type DiscoveryScanner,
  type DiscoveryTarget
} from "../../api/discovery";
import { PageHeader } from "../../components/layout/PageHeader";
import { EmptyState } from "../../components/shared/EmptyState";
import { RiskBadge } from "../../components/shared/RiskBadge";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { cn } from "../../lib/utils";

export function DiscoveryPage() {
  const [findingFilters, setFindingFilters] = useState<DiscoveryParams>({});
  const scannersQuery = useDiscoveryScanners();
  const targetsQuery = useDiscoveryTargets();
  const runsQuery = useDiscoveryRuns();
  const findingsQuery = useDiscoveryFindings(findingFilters);
  const mutation = useDiscoveryMutation();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const scanners = scannersQuery.data ?? [];
  const targets = targetsQuery.data ?? [];
  const runs = runsQuery.data ?? [];
  const findings = findingsQuery.data ?? [];
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0] ?? null;
  const selectedFinding =
    findings.find((finding) => finding.id === selectedFindingId) ?? findings[0] ?? null;

  async function runTask(label: string, task: () => Promise<unknown>) {
    await mutation.mutateAsync(task);
    setMessage(label);
  }

  function applyFindingFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setFindingFilters({
      risk_level: formString(form, "risk_level"),
      status: formString(form, "status"),
      source: formString(form, "source"),
      owner: formString(form, "owner"),
      registry_match: formString(form, "registry_match"),
      include_suppressed: form.get("include_suppressed") === "on" ? true : undefined
    });
  }

  return (
    <>
      <PageHeader
        title="Discovery"
        description="Run scans, reconcile shadow agents, and turn findings into governed registry work."
      />
      <div className="space-y-6 p-6" data-discovery-workspace>
        {message ? (
          <div className="feedback-success">
            {message}
          </div>
        ) : null}
        <ScannerCards scanners={scanners} isLoading={scannersQuery.isLoading} />
        <DiscoveryTargets
          onRunTask={runTask}
          targets={targets}
          isLoading={targetsQuery.isLoading}
        />
        <DiscoveryRuns
          onRunTask={runTask}
          onSelectRun={setSelectedRunId}
          runs={runs}
          selectedRun={selectedRun}
        />
        <DiscoveryFindings
          findings={findings}
          includeSuppressed={findingFilters.include_suppressed === true}
          onFilter={applyFindingFilters}
          onRunTask={runTask}
          onSelectFinding={setSelectedFindingId}
          selectedFinding={selectedFinding}
        />
      </div>
    </>
  );
}

function ScannerCards({
  isLoading,
  scanners
}: {
  isLoading: boolean;
  scanners: DiscoveryScanner[];
}) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Scanners</h2>
          <p className="text-sm text-muted-foreground">
            Built-in process, config, and GitHub scanner availability.
          </p>
        </div>
      </div>
      {isLoading ? (
        <div className="mt-5 rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
          Loading scanners
        </div>
      ) : (
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          {scanners.map((scanner) => (
            <div className="rounded-lg border p-4" key={scanner.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold">{scanner.name}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{scanner.description}</p>
                </div>
                <StatusBadge status={scanner.status ?? (scanner.available ? "available" : "unavailable")} />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(scanner.required_config ?? []).map((item) => (
                  <Badge key={item} tone="muted">
                    {item}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function DiscoveryTargets({
  isLoading,
  onRunTask,
  targets
}: {
  isLoading: boolean;
  onRunTask: (label: string, task: () => Promise<unknown>) => Promise<void>;
  targets: DiscoveryTarget[];
}) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div>
        <h2 className="text-lg font-semibold">Targets</h2>
        <p className="text-sm text-muted-foreground">
          Configure schedules and trigger manual discovery runs.
        </p>
      </div>
      <div className="mt-5 overflow-x-auto">
        {isLoading ? (
          <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
            Loading targets
          </div>
        ) : targets.length === 0 ? (
          <EmptyState title="No targets" description="Create a target through the API or setup flow." />
        ) : (
          <table className="w-full min-w-[52rem] text-sm">
            <thead className="border-b text-left text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">Target</th>
                <th className="py-2 pr-3 font-medium">Scanner</th>
                <th className="py-2 pr-3 font-medium">Schedule</th>
                <th className="py-2 pr-3 font-medium">Next run</th>
                <th className="py-2 pr-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {targets.map((target) => (
                <tr className="border-b last:border-b-0" key={target.id}>
                  <td className="py-3 pr-3 font-medium">{target.target_value}</td>
                  <td className="py-3 pr-3">{target.scanner_type}</td>
                  <td className="py-3 pr-3">{target.schedule_mode ?? "manual"}</td>
                  <td className="py-3 pr-3">{target.next_run_at ?? "n/a"}</td>
                  <td className="py-3 pr-3">
                    <div className="flex flex-wrap gap-2">
                      <Button
                        onClick={() =>
                          onRunTask("Discovery run started", () =>
                            createDiscoveryRun({ target_id: target.id })
                          )
                        }
                        type="button"
                        variant="outline"
                      >
                        <Play className="h-4 w-4" />
                        Run now
                      </Button>
                      <Button
                        onClick={() =>
                          onRunTask("Schedule updated", () =>
                            patchDiscoveryTargetSchedule(target.id, { mode: "hourly" })
                          )
                        }
                        type="button"
                        variant="ghost"
                      >
                        Hourly
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

function DiscoveryRuns({
  onRunTask,
  onSelectRun,
  runs,
  selectedRun
}: {
  onRunTask: (label: string, task: () => Promise<unknown>) => Promise<void>;
  onSelectRun: (runId: string) => void;
  runs: DiscoveryRun[];
  selectedRun: DiscoveryRun | null;
}) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Scan Runs</h2>
          <p className="text-sm text-muted-foreground">
            Persisted run state, findings, errors, and reconciliation entry points.
          </p>
        </div>
        {selectedRun ? (
          <Button
            onClick={() =>
              onRunTask("Run reconciled", () => reconcileDiscoveryRun(selectedRun.id))
            }
            type="button"
            variant="outline"
          >
            <RefreshCw className="h-4 w-4" />
            Reconcile selected
          </Button>
        ) : null}
      </div>
      <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_26rem]">
        <div className="overflow-x-auto">
          {runs.length === 0 ? (
            <EmptyState title="No scan runs" description="Run a target to collect raw findings." />
          ) : (
            <table className="w-full min-w-[48rem] text-sm">
              <thead className="border-b text-left text-muted-foreground">
                <tr>
                  <th className="py-2 pr-3 font-medium">Run</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Findings</th>
                  <th className="py-2 pr-3 font-medium">High risk</th>
                  <th className="py-2 pr-3 font-medium">Duration</th>
                  <th className="py-2 pr-3 font-medium">Error</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    className={cn(
                      "cursor-pointer border-b last:border-b-0",
                      selectedRun?.id === run.id ? "bg-accent/50" : ""
                    )}
                    data-discovery-run-row={run.id}
                    key={run.id}
                    onClick={() => onSelectRun(run.id)}
                  >
                    <td className="py-3 pr-3 font-medium">{run.id}</td>
                    <td className="py-3 pr-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="py-3 pr-3">{run.raw_finding_count ?? 0} raw</td>
                    <td className="py-3 pr-3">{run.high_risk_count ?? 0} high</td>
                    <td className="py-3 pr-3">{durationLabel(run)}</td>
                    <td className="py-3 pr-3" data-discovery-run-error={run.error_message ? true : undefined}>
                      {run.error_message ?? "n/a"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <RunDetail run={selectedRun} />
      </div>
    </section>
  );
}

function RunDetail({ run }: { run: DiscoveryRun | null }) {
  if (!run) {
    return <EmptyState title="No run selected" description="Select a run to inspect raw findings." />;
  }
  return (
    <aside className="rounded-lg border p-4" data-discovery-run-detail={run.id}>
      <h3 className="font-semibold">Run Detail</h3>
      <div className="mt-3 space-y-2 text-sm">
        <div>Status: {run.status}</div>
        <div>Duration: {durationLabel(run)}</div>
        <div>Reconciliation: ready</div>
      </div>
      <div className="mt-4 space-y-3">
        {(run.raw_findings ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">No raw findings</p>
        ) : (
          (run.raw_findings ?? []).map((finding) => (
            <div className="rounded-md bg-muted/50 p-3 text-sm" key={finding.id}>
              <div className="font-medium">{finding.fingerprint}</div>
              <pre className="mt-2 max-h-36 overflow-auto text-xs">
                {JSON.stringify(finding.raw_payload_json ?? {}, null, 2)}
              </pre>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}

function DiscoveryFindings({
  findings,
  includeSuppressed,
  onFilter,
  onRunTask,
  onSelectFinding,
  selectedFinding
}: {
  findings: DiscoveryFinding[];
  includeSuppressed: boolean;
  onFilter: (event: FormEvent<HTMLFormElement>) => void;
  onRunTask: (label: string, task: () => Promise<unknown>) => Promise<void>;
  onSelectFinding: (findingId: string) => void;
  selectedFinding: DiscoveryFinding | null;
}) {
  const visibleFindings = includeSuppressed
    ? findings
    : findings.filter((finding) => finding.status !== "suppressed");
  return (
    <section className="rounded-lg border bg-card p-5" data-discovery-findings>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Findings</h2>
          <p className="text-sm text-muted-foreground">
            Risk triage, evidence review, registry matching, and suppression actions.
          </p>
        </div>
        <form className="flex flex-wrap items-end gap-3" onSubmit={onFilter}>
          <SelectField label="Risk" name="risk_level" options={["", "critical", "high", "medium", "low"]} />
          <SelectField
            label="Status"
            name="status"
            options={["", "shadow_candidate", "manual_review", "registered", "suppressed"]}
          />
          <Field compact label="Source" name="source" placeholder="agentmesh.yaml" />
          <Field compact label="Owner" name="owner" placeholder="team-a" />
          <SelectField label="Registry" name="registry_match" options={["", "matched", "unmatched"]} />
          <label className="flex h-9 items-center gap-2 text-sm">
            <input name="include_suppressed" type="checkbox" />
            Suppressed
          </label>
          <Button type="submit" variant="outline">
            <Search className="h-4 w-4" />
            Filter findings
          </Button>
        </form>
      </div>
      <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_28rem]">
        <div className="overflow-x-auto">
          {visibleFindings.length === 0 ? (
            <EmptyState title="No active findings" description="Change filters to include suppressed findings." />
          ) : (
            <table className="w-full min-w-[56rem] text-sm">
              <thead className="border-b text-left text-muted-foreground">
                <tr>
                  <th className="py-2 pr-3 font-medium">Finding</th>
                  <th className="py-2 pr-3 font-medium">Risk</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Owner</th>
                  <th className="py-2 pr-3 font-medium">Source</th>
                  <th className="py-2 pr-3 font-medium">Registry</th>
                </tr>
              </thead>
              <tbody>
                {visibleFindings.map((finding) => (
                  <tr
                    className={cn(
                      "cursor-pointer border-b last:border-b-0",
                      selectedFinding?.id === finding.id ? "bg-accent/50" : ""
                    )}
                    data-discovery-finding-row={finding.id}
                    key={finding.id}
                    onClick={() => onSelectFinding(finding.id)}
                  >
                    <td className="py-3 pr-3 font-medium">{finding.detected_name}</td>
                    <td className="py-3 pr-3">
                      <RiskBadge risk={finding.risk_level ?? "low"} />
                      <span className="ml-2 text-muted-foreground">{finding.risk_score ?? 0}</span>
                    </td>
                    <td className="py-3 pr-3">{finding.status}</td>
                    <td className="py-3 pr-3">{finding.owner_hint ?? "unassigned"}</td>
                    <td className="py-3 pr-3">{finding.source ?? "n/a"}</td>
                    <td className="py-3 pr-3">{finding.registry_agent_id ?? "unmatched"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <FindingDetail finding={selectedFinding} onRunTask={onRunTask} />
      </div>
    </section>
  );
}

function FindingDetail({
  finding,
  onRunTask
}: {
  finding: DiscoveryFinding | null;
  onRunTask: (label: string, task: () => Promise<unknown>) => Promise<void>;
}) {
  if (!finding) {
    return <EmptyState title="No finding selected" description="Select a finding to inspect risk evidence." />;
  }
  return (
    <aside className="rounded-lg border p-4" data-discovery-finding-detail={finding.id}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">{finding.detected_name}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{finding.fingerprint}</p>
        </div>
        <RiskBadge risk={finding.risk_level ?? "low"} />
      </div>
      <div className="mt-4">
        <h4 className="text-sm font-semibold">Risk Factors</h4>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {(finding.risk_factors ?? ["No risk factors"]).map((factor) => (
            <li key={factor}>{factor}</li>
          ))}
        </ul>
      </div>
      <div className="mt-4">
        <h4 className="text-sm font-semibold">Evidence</h4>
        <div className="mt-2 space-y-2">
          {(finding.evidence ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No evidence records</p>
          ) : (
            (finding.evidence ?? []).map((evidence) => (
              <div className="rounded-md bg-muted/50 p-3 text-sm" key={evidence.id}>
                <div className="font-medium">{evidence.evidence_type}</div>
                <div className="text-muted-foreground">{evidence.evidence_value}</div>
              </div>
            ))
          )}
        </div>
      </div>
      <div className="mt-4 space-y-3">
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            const owner = formString(new FormData(event.currentTarget), "owner_user_id");
            void onRunTask("Owner assigned", () =>
              assignDiscoveryFindingOwner(finding.id, { owner_user_id: owner })
            );
          }}
        >
          <Input name="owner_user_id" required placeholder="owner_1" />
          <Button type="submit" variant="outline">
            Assign
          </Button>
        </form>
        <div className="flex flex-wrap gap-2">
          <Button
            data-discovery-action="register-agent"
            onClick={() =>
              onRunTask("Registration draft created", () =>
                registerDiscoveryFindingAgent(finding.id, { owner_user_id: finding.owner_hint ?? "owner_1" })
              )
            }
            type="button"
            variant="outline"
          >
            <ShieldAlert className="h-4 w-4" />
            Register Agent
          </Button>
          <form
            className="flex gap-2"
            data-discovery-action="suppress"
            onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              void onRunTask("Finding suppressed", () =>
                suppressDiscoveryFinding(finding.id, {
                  reason: formString(form, "reason"),
                  confirm: formString(form, "confirm")
                })
              );
            }}
          >
            <Input className="w-28" name="reason" required placeholder="Reason" />
            <Input className="w-28" name="confirm" required placeholder="Confirm" />
            <Button type="submit" variant="outline">
              Suppress
            </Button>
          </form>
          <Button
            onClick={() =>
              onRunTask("Finding decommissioned", () =>
                markDiscoveryFindingDecommissioned(finding.id)
              )
            }
            type="button"
            variant="ghost"
          >
            Mark decommissioned
          </Button>
        </div>
      </div>
    </aside>
  );
}

function durationLabel(run: DiscoveryRun) {
  if (!run.started_at || !run.finished_at) {
    return "n/a";
  }
  const started = new Date(run.started_at).getTime();
  const finished = new Date(run.finished_at).getTime();
  if (Number.isNaN(started) || Number.isNaN(finished) || finished < started) {
    return "n/a";
  }
  return `${Math.round((finished - started) / 1000)}s`;
}

function Field({
  compact,
  label,
  name,
  placeholder
}: {
  compact?: boolean;
  label: string;
  name: string;
  placeholder?: string;
}) {
  return (
    <div className={cn("space-y-1", compact ? "w-36" : "")}>
      <Label htmlFor={`discovery-${name}`}>{label}</Label>
      <Input id={`discovery-${name}`} name={name} placeholder={placeholder} />
    </div>
  );
}

function SelectField({
  label,
  name,
  options
}: {
  label: string;
  name: string;
  options: string[];
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={`discovery-${name}`}>{label}</Label>
      <select
        className="flex h-9 w-36 rounded-md border border-input bg-background px-3 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        id={`discovery-${name}`}
        name={name}
      >
        {options.map((option) => (
          <option key={option || "any"} value={option}>
            {option || "any"}
          </option>
        ))}
      </select>
    </div>
  );
}

function formString(form: FormData, key: string) {
  return String(form.get(key) ?? "").trim();
}
