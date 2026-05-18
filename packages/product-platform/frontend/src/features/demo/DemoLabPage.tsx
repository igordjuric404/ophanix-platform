import { Play, RotateCcw, Square, StepForward } from "lucide-react";
import { useState } from "react";

import {
  cancelDemoRun,
  continueDemoRun,
  resetDemoEnvironment,
  startDemoRun,
  useDemoBaselineStatus,
  useDemoMutation,
  useDemoResetRun,
  useDemoResetRuns,
  useDemoRun,
  useDemoScenario,
  useDemoScenarios,
  type DemoBaselineStatus,
  type DemoProofChecklistItem,
  type DemoRequiredService,
  type DemoResetRun,
  type DemoRun,
  type DemoScenarioDetail,
  type DemoScenarioSummary,
  type DemoStepRun
} from "../../api/demo";
import { PageHeader } from "../../components/layout/PageHeader";
import {
  ActionFeedback,
  actionErrorMessage,
  type ActionFeedbackMessage
} from "../../components/shared/ActionFeedback";
import { EmptyState } from "../../components/shared/EmptyState";
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

const terminalRunStatuses = new Set(["succeeded", "failed", "canceled", "cancelled"]);

export function DemoLabPage() {
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedResetId, setSelectedResetId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<ActionFeedbackMessage | null>(null);

  const scenariosQuery = useDemoScenarios();
  const resetRunsQuery = useDemoResetRuns({ limit: 10 });
  const baselineQuery = useDemoBaselineStatus();
  const mutation = useDemoMutation();

  const scenarios = scenariosQuery.data ?? [];
  const activeScenarioId = selectedScenarioId ?? scenarios[0]?.id ?? null;
  const scenarioQuery = useDemoScenario(activeScenarioId);
  const activeScenario =
    scenarioQuery.data ?? scenarios.find((scenario) => scenario.id === activeScenarioId) ?? null;
  const resetRuns = resetRunsQuery.data ?? [];
  const activeResetId = selectedResetId ?? resetRuns[0]?.id ?? null;
  const resetDetailQuery = useDemoResetRun(activeResetId);
  const activeReset =
    resetDetailQuery.data ?? resetRuns.find((resetRun) => resetRun.id === activeResetId) ?? null;
  const runQuery = useDemoRun(selectedRunId);
  const activeRun = runQuery.data ?? null;
  const baselineStatus = baselineQuery.data ?? null;

  async function runResultTask<T>(label: string, task: () => Promise<T>, onResult: (value: T) => void) {
    try {
      const result = (await mutation.mutateAsync(task)) as T;
      onResult(result);
      setFeedback({ type: "success", message: label });
    } catch (error) {
      setFeedback({ type: "error", message: actionErrorMessage(error) });
    }
  }

  return (
    <>
      <PageHeader
        title="Demo Lab"
        description="Run governed demo scenarios, reset the local environment, and follow live proof links across the platform."
      />
      <div className="space-y-6 p-6" data-demo-lab-workspace>
        <ActionFeedback feedback={feedback} />
        <DemoSummary
          baselineStatus={baselineStatus}
          resetRun={activeReset}
          run={activeRun}
          scenarios={scenarios}
        />
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <BaselinePanel baselineStatus={baselineStatus} />
          <ResetPanel
            onReset={(payload) =>
              runResultTask("Demo environment reset", () => resetDemoEnvironment(payload), (resetRun) =>
                setSelectedResetId(resetRun.id)
              )
            }
            onSelect={setSelectedResetId}
            resetRun={activeReset}
            resetRuns={resetRuns}
            selectedResetId={activeReset?.id ?? null}
          />
        </div>
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <ScenarioCatalog
            onSelect={setSelectedScenarioId}
            scenarios={scenarios}
            selectedScenarioId={activeScenario?.id ?? null}
          />
          <ScenarioDetail
            onStart={(scenarioId) =>
              runResultTask("Demo scenario started", () => startDemoRun(scenarioId), (run) =>
                setSelectedRunId(run.id)
              )
            }
            scenario={activeScenario}
          />
        </div>
        <RunTimeline
          onCancel={(runId) =>
            runResultTask("Demo run canceled", () => cancelDemoRun(runId), (run) =>
              setSelectedRunId(run.id)
            )
          }
          onContinue={(runId) =>
            runResultTask("Demo run advanced", () => continueDemoRun(runId), (run) =>
              setSelectedRunId(run.id)
            )
          }
          run={activeRun}
        />
        <ProofChecklist stepRuns={activeRun?.step_runs ?? []} />
      </div>
    </>
  );
}

function DemoSummary({
  baselineStatus,
  resetRun,
  run,
  scenarios
}: {
  baselineStatus: DemoBaselineStatus | null;
  resetRun: DemoResetRun | null;
  run: DemoRun | null;
  scenarios: DemoScenarioSummary[];
}) {
  return (
    <div className="grid gap-4 md:grid-cols-4">
      <SummaryCard label="Scenarios" value={String(scenarios.length)} />
      <SummaryCard
        label="Baseline"
        value={baselineStatus?.overall_status ?? "unknown"}
        status={baselineStatus?.overall_status}
      />
      <SummaryCard label="Active Run" value={run?.status ?? "not started"} status={run?.status} />
      <SummaryCard label="Latest Reset" value={resetRun?.status ?? "none"} status={resetRun?.status} />
    </div>
  );
}

function SummaryCard({ label, status, value }: { label: string; status?: string | null; value: string }) {
  return (
    <Card>
      <CardContent className="flex min-h-24 flex-col justify-between p-4">
        <span className="text-sm text-muted-foreground">{label}</span>
        <div className="flex items-center justify-between gap-3">
          <strong className="text-2xl">{value}</strong>
          {status ? <StatusPill status={status} /> : null}
        </div>
      </CardContent>
    </Card>
  );
}

function BaselinePanel({ baselineStatus }: { baselineStatus: DemoBaselineStatus | null }) {
  return (
    <Card data-demo-prerequisites-panel>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <div>
          <CardTitle>Prerequisites</CardTitle>
          <p className="text-sm text-muted-foreground">Local demo baseline and compose service checks.</p>
        </div>
        <StatusPill status={baselineStatus?.overall_status ?? "unknown"} />
      </CardHeader>
      <CardContent>
        {baselineStatus?.checks.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Check</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Count</TableHead>
                <TableHead>Detail</TableHead>
                <TableHead>Missing</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {baselineStatus.checks.map((check) => (
                <TableRow
                  data-demo-baseline-check={check.key}
                  data-demo-baseline-status={check.status}
                  key={check.key}
                >
                  <TableCell>
                    <div className="font-medium">{check.label}</div>
                    <div className="text-xs text-muted-foreground">
                      {check.required ? "required" : "optional"}
                    </div>
                  </TableCell>
                  <TableCell>
                    <StatusPill status={check.status} />
                  </TableCell>
                  <TableCell>
                    {check.count}
                    {check.expected_count ? `/${check.expected_count}` : ""}
                  </TableCell>
                  <TableCell>{check.detail}</TableCell>
                  <TableCell>{check.missing.length ? check.missing.join(", ") : "none"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState
            title="No baseline status"
            description="Seed the demo environment before running scenario checks."
          />
        )}
      </CardContent>
    </Card>
  );
}

function ResetPanel({
  onReset,
  onSelect,
  resetRun,
  resetRuns,
  selectedResetId
}: {
  onReset: (payload: Record<string, unknown>) => void;
  onSelect: (resetId: string) => void;
  resetRun: DemoResetRun | null;
  resetRuns: DemoResetRun[];
  selectedResetId: string | null;
}) {
  return (
    <Card data-demo-reset-panel>
      <CardHeader>
        <CardTitle>Environment Reset</CardTitle>
        <p className="text-sm text-muted-foreground">
          Clear scenario state, preserve admin configuration, and reload baseline fixtures.
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        <dl className="grid gap-3 rounded-md border p-3 text-sm md:grid-cols-[8rem_1fr]">
          <dt className="font-medium">Clears</dt>
          <dd>demo_step_runs, demo_runs, demo-lab audit events</dd>
          <dt className="font-medium">Preserves</dt>
          <dd>users, organizations, environments, provider credentials</dd>
        </dl>
        <form
          className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]"
          onSubmit={(event) => {
            event.preventDefault();
            onReset(demoResetPayloadFromForm(event.currentTarget));
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="demo-reset-confirmation">Confirmation</Label>
            <Input
              autoComplete="off"
              id="demo-reset-confirmation"
              name="confirmation"
              pattern="RESET"
              placeholder="RESET"
              required
            />
          </div>
          <div className="flex items-end">
            <Button type="submit">
              <RotateCcw className="h-4 w-4" />
              Reset Demo
            </Button>
          </div>
        </form>
        <ResetResult resetRun={resetRun} />
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Reset History</h3>
          {resetRuns.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Reset</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {resetRuns.map((item) => (
                  <TableRow data-demo-reset-row={item.id} key={item.id}>
                    <TableCell>{item.id}</TableCell>
                    <TableCell>
                      <StatusPill status={item.status} />
                    </TableCell>
                    <TableCell>{item.started_at}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        disabled={selectedResetId === item.id}
                        onClick={() => onSelect(item.id)}
                        type="button"
                        variant="secondary"
                      >
                        Open
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <EmptyState title="No reset runs" description="Reset history appears after the first reset." />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ResetResult({ resetRun }: { resetRun: DemoResetRun | null }) {
  if (!resetRun) {
    return (
      <div className="rounded-md border p-4 text-sm" data-demo-reset-result>
        <strong>No reset run</strong>
        <p className="mt-1 text-muted-foreground">Baseline fixtures are ready for the first reset.</p>
      </div>
    );
  }
  return (
    <div
      className="space-y-3 rounded-md border p-4"
      data-demo-reset-progress={resetRun.status}
      data-demo-reset-result={resetRun.id}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="font-medium">{resetRun.id}</div>
          <div className="text-sm text-muted-foreground">
            {resetRun.started_at} to {resetRun.finished_at ?? "running"}
          </div>
        </div>
        <StatusPill status={resetRun.status} />
      </div>
      <div className="grid gap-2 text-sm md:grid-cols-3">
        <SummaryLine label="Cleared demo runs" value={resetSummaryCount(resetRun, "cleared", "demo_runs")} />
        <SummaryLine
          label="Cleared step runs"
          value={resetSummaryCount(resetRun, "cleared", "demo_step_runs")}
        />
        <SummaryLine
          label="Cleared audit events"
          value={resetSummaryCount(resetRun, "cleared", "demo_lab_audit_events")}
        />
        <SummaryLine
          label="Seed policies"
          value={resetSummaryCount(resetRun, "seeded", "policy_placeholders")}
        />
        <SummaryLine
          label="Seed scenarios"
          value={resetSummaryCount(resetRun, "seeded", "demo_scenarios")}
        />
        <SummaryLine label="Seed steps" value={resetSummaryCount(resetRun, "seeded", "demo_steps")} />
      </div>
    </div>
  );
}

function SummaryLine({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-muted p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

function ScenarioCatalog({
  onSelect,
  scenarios,
  selectedScenarioId
}: {
  onSelect: (scenarioId: string) => void;
  scenarios: DemoScenarioSummary[];
  selectedScenarioId: string | null;
}) {
  return (
    <Card data-demo-scenario-catalog>
      <CardHeader>
        <CardTitle>Scenario Catalog</CardTitle>
      </CardHeader>
      <CardContent>
        {scenarios.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Scenario</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Services</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scenarios.map((scenario) => (
                <TableRow data-demo-scenario-row={scenario.id} key={scenario.id}>
                  <TableCell>
                    <div className="font-medium">{scenario.name}</div>
                    <div className="text-xs text-muted-foreground">{scenario.slug}</div>
                  </TableCell>
                  <TableCell>
                    <StatusPill status={scenario.status} />
                  </TableCell>
                  <TableCell>{scenario.required_services.length}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      disabled={selectedScenarioId === scenario.id}
                      onClick={() => onSelect(scenario.id)}
                      type="button"
                      variant="secondary"
                    >
                      Open
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState title="No scenarios" description="Seed Demo Lab scenarios to begin." />
        )}
      </CardContent>
    </Card>
  );
}

function ScenarioDetail({
  onStart,
  scenario
}: {
  onStart: (scenarioId: string) => void;
  scenario: DemoScenarioDetail | DemoScenarioSummary | null;
}) {
  if (!scenario) {
    return (
      <Card data-demo-scenario-detail>
        <CardHeader>
          <CardTitle>Scenario Detail</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState title="No scenario selected" description="Open a scenario from the catalog." />
        </CardContent>
      </Card>
    );
  }
  const detail = scenario as DemoScenarioDetail;
  const steps = detail.steps ?? [];
  return (
    <Card data-demo-scenario-detail={scenario.id}>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>{scenario.name}</CardTitle>
          <p className="text-sm text-muted-foreground">{scenario.description}</p>
        </div>
        <Button onClick={() => onStart(scenario.id)} type="button">
          <Play className="h-4 w-4" />
          Start Scenario
        </Button>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-md border p-3 text-sm">
          <div className="text-xs text-muted-foreground">Value Proof</div>
          <div className="font-medium">{scenario.value_proof}</div>
        </div>
        <RequiredServices services={scenario.required_services} />
        {steps.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Step</TableHead>
                <TableHead>Expected</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {steps.map((step) => (
                <TableRow data-demo-step-row={step.id} key={step.id}>
                  <TableCell>{step.step_order}</TableCell>
                  <TableCell>
                    <div className="font-medium">{step.title}</div>
                    <div className="text-xs text-muted-foreground">{step.action_type}</div>
                  </TableCell>
                  <TableCell>{step.expected_result}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState title="No steps" description="Scenario definition is incomplete." />
        )}
      </CardContent>
    </Card>
  );
}

function RequiredServices({ services }: { services: DemoRequiredService[] }) {
  if (!services.length) {
    return <EmptyState title="No required services" description="This scenario has no prerequisites." />;
  }
  return (
    <div className="grid gap-2 md:grid-cols-2">
      {services.map((service) => (
        <div className="rounded-md border p-3 text-sm" data-demo-required-service={service.key} key={service.key}>
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium">{service.label}</span>
            <Badge tone={service.required ? "warning" : "muted"}>
              {service.required ? "required" : "optional"}
            </Badge>
          </div>
          {service.evidence_route ? (
            <a className="mt-2 block text-xs font-medium underline" href={service.evidence_route}>
              Evidence
            </a>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function RunTimeline({
  onCancel,
  onContinue,
  run
}: {
  onCancel: (runId: string) => void;
  onContinue: (runId: string) => void;
  run: DemoRun | null;
}) {
  if (!run) {
    return (
      <Card data-demo-run-timeline>
        <CardHeader>
          <CardTitle>Run Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState title="No run yet" description="Start a scenario to watch live execution state." />
        </CardContent>
      </Card>
    );
  }
  const terminal = terminalRunStatuses.has(run.status);
  return (
    <Card data-demo-run-timeline={run.id}>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <div>
          <CardTitle>Run Timeline</CardTitle>
          <p className="text-sm text-muted-foreground">
            {run.started_at} to {run.finished_at ?? "running"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={terminal} onClick={() => onContinue(run.id)} type="button" variant="secondary">
            <StepForward className="h-4 w-4" />
            Continue
          </Button>
          <Button disabled={terminal} onClick={() => onCancel(run.id)} type="button" variant="secondary">
            <Square className="h-4 w-4" />
            Cancel
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid gap-3 rounded-md border p-3 text-sm md:grid-cols-[8rem_1fr]">
          <dt className="font-medium">Status</dt>
          <dd>
            <StatusPill status={run.status} />
          </dd>
          <dt className="font-medium">Completed</dt>
          <dd>
            {summaryValue(run.summary, "completed_steps")}/{summaryValue(run.summary, "total_steps")}
          </dd>
        </dl>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Step</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Expected</TableHead>
              <TableHead>Actual</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {run.step_runs.map((stepRun) => (
              <TableRow data-demo-step-run-status={stepRun.status} key={stepRun.id}>
                <TableCell>
                  <div className="font-medium">{stepRun.step?.title ?? stepRun.demo_step_id}</div>
                  <div className="text-xs text-muted-foreground">{stepRun.demo_step_id}</div>
                </TableCell>
                <TableCell>
                  <StatusPill status={stepRun.status} />
                </TableCell>
                <TableCell>{stepRun.step?.expected_result ?? "pending"}</TableCell>
                <TableCell>{stepRun.actual_result ?? "pending"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function ProofChecklist({ stepRuns }: { stepRuns: DemoStepRun[] }) {
  const items = stepRuns.flatMap((stepRun) =>
    stepRun.proof_checklist.map((item) => ({
      ...item,
      stepTitle: stepRun.step?.title ?? stepRun.demo_step_id,
      stepStatus: stepRun.status
    }))
  );
  return (
    <Card data-demo-proof-checklist>
      <CardHeader>
        <CardTitle>Proof Checklist</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Step</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Expected</TableHead>
                <TableHead>Actual</TableHead>
                <TableHead>Evidence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item, index) => (
                <ProofChecklistRow item={item} key={`${item.route}-${index}`} />
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState title="No proof yet" description="Run scenario steps to collect evidence." />
        )}
      </CardContent>
    </Card>
  );
}

function ProofChecklistRow({
  item
}: {
  item: DemoProofChecklistItem & { stepStatus: string; stepTitle: string };
}) {
  return (
    <TableRow data-demo-proof-item={item.status}>
      <TableCell>
        <div className="font-medium">{item.stepTitle}</div>
        <div className="text-xs text-muted-foreground">{item.area}</div>
      </TableCell>
      <TableCell>
        <StatusPill status={item.status} />
      </TableCell>
      <TableCell>{item.expected_result}</TableCell>
      <TableCell>{item.actual_result ?? "pending"}</TableCell>
      <TableCell>
        <a className="font-medium underline" href={item.route}>
          {item.label}
        </a>
      </TableCell>
    </TableRow>
  );
}

function StatusPill({ status }: { status: string }) {
  return <Badge tone={statusTone(status)}>{status}</Badge>;
}

function statusTone(status: string): "default" | "success" | "warning" | "danger" | "muted" {
  const normalized = status.toLowerCase();
  if (
    normalized.includes("healthy") ||
    normalized.includes("succeeded") ||
    normalized.includes("completed") ||
    normalized.includes("published")
  ) {
    return "success";
  }
  if (normalized.includes("running") || normalized.includes("pending") || normalized.includes("degraded")) {
    return "warning";
  }
  if (normalized.includes("fail") || normalized.includes("error") || normalized.includes("cancel")) {
    return "danger";
  }
  return "muted";
}

function resetSummaryCount(resetRun: DemoResetRun, section: string, key: string) {
  const sectionValue = resetRun.summary[section];
  if (!sectionValue || typeof sectionValue !== "object" || Array.isArray(sectionValue)) {
    return 0;
  }
  const value = (sectionValue as Record<string, unknown>)[key];
  return typeof value === "number" ? value : Number(value ?? 0);
}

function summaryValue(summary: Record<string, unknown>, key: string) {
  const value = summary[key];
  return typeof value === "number" || typeof value === "string" ? value : 0;
}

export function demoResetPayloadFromValues(values: Record<string, unknown>) {
  const confirmation = String(values.confirmation ?? "").trim();
  if (confirmation !== "RESET") {
    throw new Error("Type RESET to confirm demo reset.");
  }
  const reason = String(values.reason ?? "").trim();
  return {
    confirmation,
    reason: reason || null
  };
}

export function demoResetPayloadFromForm(form: HTMLFormElement) {
  return demoResetPayloadFromValues(Object.fromEntries(new FormData(form)));
}
