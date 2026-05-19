import { Activity, AlertTriangle, CircleDollarSign, FlaskConical, Gauge, GitBranch } from "lucide-react";
import { useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import type { TenantContext } from "../../api/client";
import {
  acknowledgeObservabilityIncident,
  advanceObservabilityRollout,
  createObservabilityChaosExperiment,
  createObservabilityCostBudget,
  createObservabilityCostEvent,
  createObservabilityIncident,
  createObservabilityRollout,
  createObservabilitySlo,
  createObservabilitySloMeasurement,
  resolveObservabilityIncident,
  rollbackObservabilityRollout,
  runObservabilityChaosExperiment,
  stopObservabilityChaosRun,
  useObservabilityChaosExperiments,
  useObservabilityCosts,
  useObservabilityIncidents,
  useObservabilityMutation,
  useObservabilityRollouts,
  useObservabilitySlos,
  useObservabilityTraceDetail,
  useObservabilityTraces,
  type ChaosExperiment,
  type ChaosRun,
  type CostDashboard,
  type Incident,
  type ObservabilityParams,
  type ObservabilityTrace,
  type ObservabilityTraceDetail,
  type Rollout,
  type SloObjective
} from "../../api/observability";
import { PageHeader } from "../../components/layout/PageHeader";
import { EmptyState } from "../../components/shared/EmptyState";
import { StatusBadge } from "../../components/shared/StatusBadge";
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
import {
  ActionFeedback,
  actionErrorMessage,
  useActionFeedback
} from "../../components/shared/ActionFeedback";
import { QueryErrorSummary } from "../../components/shared/ErrorState";
import {
  parseIntegerListField,
  parseJsonObjectField,
  parseOptionalNumberField,
  parseRequiredNumberField
} from "../../lib/forms";
import {
  canAdvanceRollout,
  canRollbackRollout,
  canRunChaosExperiment
} from "../../lib/actionAvailability";

const targetTypes = ["agent", "mcp-server", "runtime", "environment"];
const incidentSeverities = ["info", "warning", "critical"];
const incidentStatuses = ["", "open", "acknowledged", "resolved"];
const chaosFaultTypes = ["latency", "error", "timeout", "trust_perturbation", "policy_denial"];
const rolloutStrategies = ["canary", "percentage"];

export function ObservabilityPage() {
  const [incidentFilters, setIncidentFilters] = useState<ObservabilityParams>({});
  const [chaosFilters, setChaosFilters] = useState<ObservabilityParams>({});
  const [rolloutFilters, setRolloutFilters] = useState<ObservabilityParams>({});
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [chaosRuns, setChaosRuns] = useState<ChaosRun[]>([]);
  const { feedback, runWithFeedback, setError } = useActionFeedback();

  const tracesQuery = useObservabilityTraces();
  const slosQuery = useObservabilitySlos();
  const costsQuery = useObservabilityCosts();
  const incidentsQuery = useObservabilityIncidents(incidentFilters);
  const chaosQuery = useObservabilityChaosExperiments(chaosFilters);
  const rolloutsQuery = useObservabilityRollouts(rolloutFilters);
  const mutation = useObservabilityMutation();

  const traces = tracesQuery.data ?? [];
  const slos = slosQuery.data ?? [];
  const costs = costsQuery.data ?? emptyCostDashboard();
  const incidents = incidentsQuery.data ?? [];
  const experiments = chaosQuery.data ?? [];
  const rollouts = rolloutsQuery.data ?? [];
  const activeTraceId = selectedTraceId ?? traces[0]?.trace_id ?? null;
  const traceDetailQuery = useObservabilityTraceDetail(activeTraceId);
  const traceDetail = traceDetailQuery.data ?? null;

  async function runTask(label: string, task: (tenantContext: TenantContext) => Promise<unknown>) {
    await runWithFeedback(() => mutation.mutateAsync(task), {
      errorMessage: `${label} failed`,
      successMessage: label
    });
  }

  async function runResultTask<T>(
    label: string,
    task: (tenantContext: TenantContext) => Promise<T>,
    onResult: (value: T) => void
  ) {
    const result = await runWithFeedback<T>(
      () => mutation.mutateAsync(task) as Promise<T>,
      {
        errorMessage: `${label} failed`,
        successMessage: label
      }
    );
    if (result) {
      onResult(result);
    }
  }

  return (
    <>
      <PageHeader
        title="Observability"
        description="SLO, cost, incident, chaos, and rollout operations for governed agents."
      />
      <div className="space-y-6 p-6">
        <ActionFeedback feedback={feedback} />
        <QueryErrorSummary
          items={[
            { error: tracesQuery.error, isError: tracesQuery.isError, label: "Traces", onRetry: () => void tracesQuery.refetch() },
            { error: traceDetailQuery.error, isError: traceDetailQuery.isError, label: "Trace detail", onRetry: () => void traceDetailQuery.refetch() },
            { error: slosQuery.error, isError: slosQuery.isError, label: "SLOs", onRetry: () => void slosQuery.refetch() },
            { error: costsQuery.error, isError: costsQuery.isError, label: "Costs", onRetry: () => void costsQuery.refetch() },
            { error: incidentsQuery.error, isError: incidentsQuery.isError, label: "Incidents", onRetry: () => void incidentsQuery.refetch() },
            { error: chaosQuery.error, isError: chaosQuery.isError, label: "Chaos experiments", onRetry: () => void chaosQuery.refetch() },
            { error: rolloutsQuery.error, isError: rolloutsQuery.isError, label: "Rollouts", onRetry: () => void rolloutsQuery.refetch() }
          ]}
        />
        <ObservabilitySummary costs={costs} incidents={incidents} rollouts={rollouts} slos={slos} traces={traces} />
        <TracePanel
          activeTraceId={activeTraceId}
          detail={traceDetail}
          isLoading={traceDetailQuery.isLoading}
          onSelect={setSelectedTraceId}
          traces={traces}
        />
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <SloPanel
            onCreate={(payload) =>
              runTask("SLO created", (tenantContext) =>
                createObservabilitySlo(payload, tenantContext)
              )
            }
            onMeasure={(sloId, payload) =>
              runTask("SLO measurement recorded", (tenantContext) =>
                createObservabilitySloMeasurement(sloId, payload, tenantContext)
              )
            }
            slos={slos}
          />
          <CostPanel
            costs={costs}
            onBudget={(payload) =>
              runTask("Cost budget created", (tenantContext) =>
                createObservabilityCostBudget(payload, tenantContext)
              )
            }
            onEvent={(payload) =>
              runTask("Cost event recorded", (tenantContext) =>
                createObservabilityCostEvent(payload, tenantContext)
              )
            }
          />
        </div>
        <IncidentPanel
          filters={incidentFilters}
          incidents={incidents}
          onAck={(incidentId) =>
            runTask("Incident acknowledged", (tenantContext) =>
              acknowledgeObservabilityIncident(incidentId, tenantContext)
            )
          }
          onCreate={(payload) =>
            runTask("Incident created", (tenantContext) =>
              createObservabilityIncident(payload, tenantContext)
            )
          }
          onFilter={setIncidentFilters}
          onResolve={(incidentId, payload) =>
            runTask("Incident resolved", (tenantContext) =>
              resolveObservabilityIncident(incidentId, payload, tenantContext)
            )
          }
        />
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <ChaosPanel
            experiments={experiments}
            filters={chaosFilters}
            onCreate={(payload) =>
              runTask("Chaos experiment created", (tenantContext) =>
                createObservabilityChaosExperiment(payload, tenantContext)
              )
            }
            onFilter={setChaosFilters}
            onInvalidInput={(error) => setError(actionErrorMessage(error, "Invalid chaos form input"))}
            onRun={(experimentId, payload) =>
              runResultTask(
                "Chaos experiment run completed",
                (tenantContext) =>
                  runObservabilityChaosExperiment(experimentId, payload, tenantContext),
                (run) => setChaosRuns((items) => [run, ...items.filter((item) => item.id !== run.id)])
              )
            }
            onStop={(runId) =>
              runResultTask(
                "Chaos run stopped",
                (tenantContext) => stopObservabilityChaosRun(runId, tenantContext),
                (run) => setChaosRuns((items) => [run, ...items.filter((item) => item.id !== run.id)])
              )
            }
            runs={chaosRuns}
          />
          <RolloutPanel
            filters={rolloutFilters}
            onAdvance={(rolloutId, payload) =>
              runTask("Rollout advanced", (tenantContext) =>
                advanceObservabilityRollout(rolloutId, payload, tenantContext)
              )
            }
            onCreate={(payload) =>
              runTask("Rollout created", (tenantContext) =>
                createObservabilityRollout(payload, tenantContext)
              )
            }
            onFilter={setRolloutFilters}
            onInvalidInput={(error) => setError(actionErrorMessage(error, "Invalid rollout form input"))}
            onRollback={(rolloutId, payload) =>
              runTask("Rollout rolled back", (tenantContext) =>
                rollbackObservabilityRollout(rolloutId, payload, tenantContext)
              )
            }
            rollouts={rollouts}
          />
        </div>
      </div>
    </>
  );
}

function ObservabilitySummary({
  costs,
  incidents,
  rollouts,
  slos,
  traces
}: {
  costs: CostDashboard;
  incidents: Incident[];
  rollouts: Rollout[];
  slos: SloObjective[];
  traces: ObservabilityTrace[];
}) {
  return (
    <div className="grid gap-4 md:grid-cols-5">
      <Metric icon={<GitBranch className="h-4 w-4" />} label="Traces" value={traces.length} />
      <Metric icon={<Gauge className="h-4 w-4" />} label="SLOs" value={slos.length} />
      <Metric icon={<CircleDollarSign className="h-4 w-4" />} label="Total Cost" value={formatMoney(costs.total_amount)} />
      <Metric icon={<AlertTriangle className="h-4 w-4" />} label="Open Incidents" value={incidents.filter((item) => item.status !== "resolved").length} />
      <Metric icon={<Activity className="h-4 w-4" />} label="Rollouts" value={rollouts.length} />
    </div>
  );
}

function TracePanel({
  activeTraceId,
  detail,
  isLoading,
  onSelect,
  traces
}: {
  activeTraceId: string | null;
  detail: ObservabilityTraceDetail | null;
  isLoading: boolean;
  onSelect: (traceId: string) => void;
  traces: ObservabilityTrace[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Trace Timeline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {traces.length === 0 ? (
          <EmptyState title="No traces" description="Runtime trace evidence appears after traces or linked runs are recorded." />
        ) : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,0.38fr)_minmax(0,0.62fr)]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Trace</TableHead>
                  <TableHead>Agent</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Open</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {traces.map((trace) => (
                  <TableRow data-observability-trace-row={trace.trace_id} key={trace.id}>
                    <TableCell>
                      <div className="max-w-56 break-all font-medium">{trace.name}</div>
                      <div className="max-w-56 break-all text-xs text-muted-foreground">{trace.trace_id}</div>
                    </TableCell>
                    <TableCell>{trace.agent_id ?? "n/a"}</TableCell>
                    <TableCell>
                      <StatusBadge status={trace.status} />
                    </TableCell>
                    <TableCell>
                      <Button
                        onClick={() => onSelect(trace.trace_id)}
                        type="button"
                        variant={activeTraceId === trace.trace_id ? "default" : "outline"}
                      >
                        View
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <TraceDetailPanel detail={detail} isLoading={isLoading} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TraceDetailPanel({
  detail,
  isLoading
}: {
  detail: ObservabilityTraceDetail | null;
  isLoading: boolean;
}) {
  if (isLoading) {
    return <EmptyState title="Loading trace" description="Fetching trace timeline." />;
  }
  if (!detail) {
    return <EmptyState title="No trace selected" description="Select a trace to inspect runtime evidence." />;
  }
  const timeline = detail.timeline.length > 0 ? detail.timeline : spansToTimeline(detail);
  return (
    <div className="space-y-4" data-observability-trace-detail={detail.trace.trace_id}>
      <div className="grid gap-3 sm:grid-cols-4">
        <Metric label="Spans" value={detail.spans.length} />
        <Metric label="Runs" value={detail.runs.length} />
        <Metric label="Tool Calls" value={detail.tool_runtime_actions.length + detail.mcp_tool_calls.length} />
        <Metric label="Evals" value={detail.eval_results.length} />
      </div>
      <div className="rounded-md border bg-muted/20 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="max-w-full break-all text-sm font-medium">{detail.trace.name}</div>
            <div className="max-w-full break-all text-xs text-muted-foreground">{detail.trace.trace_id}</div>
          </div>
          <StatusBadge status={detail.trace.status} />
        </div>
        {timeline.length === 0 ? (
          <div className="mt-4">
            <EmptyState title="No timeline entries" description="Spans and linked runtime records appear here." />
          </div>
        ) : (
          <ol className="mt-4 space-y-2" data-observability-trace-timeline={detail.trace.trace_id}>
            {timeline.map((entry) => (
              <li className="rounded-md border bg-card p-3" key={`${entry.kind}-${entry.id}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">{entry.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {entry.kind}
                      {entry.span_id ? ` span ${entry.span_id}` : ""}
                    </div>
                  </div>
                  <StatusBadge status={entry.status} />
                </div>
                <div className="mt-2 text-xs text-muted-foreground">{formatDate(entry.timestamp)}</div>
              </li>
            ))}
          </ol>
        )}
      </div>
      <TraceEvidenceTables detail={detail} />
    </div>
  );
}

function TraceEvidenceTables({ detail }: { detail: ObservabilityTraceDetail }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-md border p-3">
        <div className="mb-2 text-sm font-medium">Runtime Runs</div>
        {detail.runs.length === 0 ? (
          <EmptyState title="No runs" description="Linked runtime sessions appear here." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detail.runs.map((run) => (
                <TableRow key={String(run.id)}>
                  <TableCell className="break-all">{String(run.id)}</TableCell>
                  <TableCell>{String(run.agent_id ?? "n/a")}</TableCell>
                  <TableCell>
                    <StatusBadge status={String(run.state ?? "unknown")} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
      <div className="rounded-md border p-3">
        <div className="mb-2 text-sm font-medium">Eval Results</div>
        {detail.eval_results.length === 0 ? (
          <EmptyState title="No evals" description="Trace-linked eval results appear here." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Evaluator</TableHead>
                <TableHead>Dataset</TableHead>
                <TableHead>Score</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detail.eval_results.map((result) => (
                <TableRow key={result.id}>
                  <TableCell>{result.evaluator_name}</TableCell>
                  <TableCell>{result.dataset_name ?? result.dataset_id ?? "n/a"}</TableCell>
                  <TableCell>{result.score == null ? "n/a" : result.score.toFixed(2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}

function SloPanel({
  onCreate,
  onMeasure,
  slos
}: {
  onCreate: (payload: Record<string, unknown>) => void;
  onMeasure: (sloId: string, payload: Record<string, unknown>) => void;
  slos: SloObjective[];
}) {
  const [selectedSloId, setSelectedSloId] = useState<string | null>(null);
  const selectedSlo = slos.find((slo) => slo.id === selectedSloId) ?? slos[0] ?? null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>SLO Objectives</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="grid gap-3 md:grid-cols-3"
          onSubmit={(event) => {
            event.preventDefault();
            onCreate(observabilitySloPayloadFromForm(event.currentTarget));
            event.currentTarget.reset();
          }}
        >
          <Field label="Name" name="name" placeholder="Task success" />
          <SelectField label="Target Type" name="target_type" options={targetTypes} />
          <Field label="Target ID" name="target_id" placeholder="agent_1" />
          <Field defaultValue="task_success_rate" label="SLI" name="sli" />
          <Field defaultValue="0.95" label="Target Value" name="target_value" type="number" />
          <Field defaultValue="30d" label="Window" name="window" />
          <div className="flex items-end">
            <Button type="submit">Create SLO</Button>
          </div>
        </form>
        <SloTrendCard slo={selectedSlo} />
        {slos.length === 0 ? (
          <EmptyState title="No SLOs" description="Create an objective and record measurements." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Target</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Burn</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Freshness</TableHead>
                <TableHead>Measure</TableHead>
                <TableHead>Trend</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {slos.map((slo) => {
                const latest = slo.measurements[0];
                return (
                  <TableRow data-observability-slo-row={slo.id} key={slo.id}>
                    <TableCell>{slo.name}</TableCell>
                    <TableCell>
                      {slo.target_type}:{slo.target_id}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={latest?.status ?? slo.status} />
                    </TableCell>
                    <TableCell>{latest ? latest.burn_rate.toFixed(2) : "n/a"}</TableCell>
                    <TableCell>{formatSourceLabel(latest?.source)}</TableCell>
                    <TableCell>{latest ? formatFreshness(latest.measured_at) : "n/a"}</TableCell>
                    <TableCell>
                      <form
                        className="flex gap-2"
                        onSubmit={(event) => {
                          event.preventDefault();
                          onMeasure(slo.id, observabilitySloMeasurementPayloadFromForm(event.currentTarget));
                        }}
                      >
                        <Input aria-label={`${slo.name} value`} className="w-24" defaultValue="0.98" name="value" type="number" />
                        <Button type="submit" variant="outline">
                          Record
                        </Button>
                      </form>
                    </TableCell>
                    <TableCell>
                      <Button
                        onClick={() => setSelectedSloId(slo.id)}
                        type="button"
                        variant={selectedSlo?.id === slo.id ? "default" : "outline"}
                      >
                        View Trend
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function SloTrendCard({ slo }: { slo: SloObjective | null }) {
  const trend = slo ? sloTrendData(slo) : [];
  const hasChart = trend.length > 1;

  return (
    <div className="rounded-md border bg-muted/20 p-4" data-observability-slo-trend>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium">SLO Trend</div>
          <p className="text-xs text-muted-foreground">
            {slo
              ? `${slo.name} value, target, and burn rate over recent measurements.`
              : "Select or create an SLO to inspect its measurement trend."}
          </p>
        </div>
        {slo ? <StatusBadge status={slo.status} /> : null}
      </div>
      {!slo ? (
        <EmptyState title="No SLO selected" description="Create an objective before charting measurements." />
      ) : !hasChart ? (
        <div className="mt-4">
          <EmptyState
            title="SLO trend unavailable"
            description="Record at least two measurements to draw a trend chart."
          />
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <LineChart
            accessibilityLayer
            data={trend}
            height={220}
            margin={{ bottom: 8, left: 0, right: 16, top: 8 }}
            width={560}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" tickLine={false} />
            <YAxis tickLine={false} />
            <Tooltip formatter={(value, name) => [`${value}`, name]} />
            <Line
              dataKey="valuePercent"
              dot={{ r: 3 }}
              isAnimationActive={false}
              name="Value %"
              stroke="#2563eb"
              strokeWidth={2}
              type="monotone"
            />
            <Line
              dataKey="targetPercent"
              dot={false}
              isAnimationActive={false}
              name="Target %"
              stroke="#16a34a"
              strokeDasharray="4 4"
              strokeWidth={2}
              type="monotone"
            />
            <Line
              dataKey="burnRate"
              dot={{ r: 3 }}
              isAnimationActive={false}
              name="Burn rate"
              stroke="#f97316"
              strokeWidth={2}
              type="monotone"
            />
          </LineChart>
        </div>
      )}
      {trend.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Measured</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Target</TableHead>
              <TableHead>Burn</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {trend.map((point) => (
              <TableRow key={point.id}>
                <TableCell>{point.label}</TableCell>
                <TableCell>{point.valuePercent.toFixed(2)}%</TableCell>
                <TableCell>{point.targetPercent.toFixed(2)}%</TableCell>
                <TableCell>{point.burnRate.toFixed(2)}</TableCell>
                <TableCell>
                  <StatusBadge status={point.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
    </div>
  );
}

function CostPanel({
  costs,
  onBudget,
  onEvent
}: {
  costs: CostDashboard;
  onBudget: (payload: Record<string, unknown>) => void;
  onEvent: (payload: Record<string, unknown>) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Cost Controls</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-2">
          <form
            className="grid gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              onBudget(observabilityCostBudgetPayloadFromForm(event.currentTarget));
              event.currentTarget.reset();
            }}
          >
            <SelectField label="Budget Target Type" name="target_type" options={targetTypes} />
            <Field label="Budget Target ID" name="target_id" placeholder="agent_1" />
            <Field defaultValue="monthly" label="Period" name="period" />
            <Field defaultValue="100" label="Amount Limit" name="amount_limit" type="number" />
            <SelectField label="Breach Action" name="action_on_breach" options={["warn", "throttle", "kill_switch"]} />
            <Button type="submit">Create Budget</Button>
          </form>
          <form
            className="grid gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              onEvent(observabilityCostEventPayloadFromForm(event.currentTarget));
              event.currentTarget.reset();
            }}
          >
            <SelectField label="Cost Target Type" name="target_type" options={targetTypes} />
            <Field label="Cost Target ID" name="target_id" placeholder="agent_1" />
            <Field label="Provider" name="provider" placeholder="openai" />
            <Field label="Model" name="model" placeholder="gpt" />
            <Field defaultValue="1.25" label="Amount" name="amount" type="number" />
            <Field defaultValue="1000" label="Units" name="units" type="number" />
            <Field label="Correlation" name="correlation_id" />
            <Button type="submit">Record Cost</Button>
          </form>
        </div>
        <CostDistributionChart costs={costs} />
        {costs.budgets.length === 0 ? (
          <EmptyState title="No budgets" description="Cost controls appear after a budget is created." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Target</TableHead>
                <TableHead>Used</TableHead>
                <TableHead>Limit</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {costs.budgets.map((budget) => (
                <TableRow data-observability-cost-budget-row={budget.id} key={budget.id}>
                  <TableCell>
                    {budget.target_type}:{budget.target_id}
                  </TableCell>
                  <TableCell>{formatMoney(budget.used_amount)}</TableCell>
                  <TableCell>{formatMoney(budget.amount_limit)}</TableCell>
                  <TableCell>
                    <StatusBadge status={budget.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function CostDistributionChart({ costs }: { costs: CostDashboard }) {
  const rows = costDistributionRows(costs);
  const latestEvent = costs.events[0] ?? null;

  return (
    <div className="rounded-md border bg-muted/20 p-4" data-observability-cost-chart>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium">Cost Distribution</div>
          <p className="text-xs text-muted-foreground">
            Spend grouped by provider, model, and governed target.
          </p>
          {latestEvent ? (
            <p className="text-xs text-muted-foreground">
              {formatSourceLabel(latestEvent.source)} · {formatFreshness(latestEvent.created_at)}
            </p>
          ) : null}
        </div>
        <div className="text-sm font-semibold">{formatMoney(costs.total_amount)}</div>
      </div>
      {rows.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title="No cost events"
            description="Record cost events to chart provider, model, and target spend."
          />
        </div>
      ) : (
        <>
          <div className="mt-4 overflow-x-auto">
            <BarChart
              accessibilityLayer
              data={rows}
              height={240}
              margin={{ bottom: 28, left: 0, right: 16, top: 8 }}
              width={620}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis angle={-18} dataKey="label" height={56} interval={0} textAnchor="end" tickLine={false} />
              <YAxis tickFormatter={(value) => `$${value}`} tickLine={false} />
              <Tooltip formatter={(value) => [formatMoney(Number(value)), "Spend"]} />
              <Bar dataKey="amount" fill="#2563eb" isAnimationActive={false} name="Spend" radius={[4, 4, 0, 0]} />
            </BarChart>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Group</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Spend</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={`${row.group}-${row.name}`}>
                  <TableCell>{row.group}</TableCell>
                  <TableCell>{row.name}</TableCell>
                  <TableCell>{formatMoney(row.amount)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  );
}

function IncidentPanel({
  filters,
  incidents,
  onAck,
  onCreate,
  onFilter,
  onResolve
}: {
  filters: ObservabilityParams;
  incidents: Incident[];
  onAck: (incidentId: string) => void;
  onCreate: (payload: Record<string, unknown>) => void;
  onFilter: (filters: ObservabilityParams) => void;
  onResolve: (incidentId: string, payload: Record<string, unknown>) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Incident Queue</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,0.35fr)_minmax(0,0.65fr)]">
          <form
            className="grid gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              onCreate(observabilityIncidentPayloadFromForm(event.currentTarget));
              event.currentTarget.reset();
            }}
          >
            <SelectField label="Severity" name="severity" options={incidentSeverities} />
            <Field label="Incident Title" name="title" />
            <TextAreaField label="Summary" name="summary" />
            <Field label="Correlation ID" name="correlation_id" />
            <Button type="submit">Create Incident</Button>
          </form>
          <div className="space-y-3">
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                onFilter(cleanParams(new FormData(event.currentTarget), ["status", "severity"]));
              }}
            >
              <SelectField defaultValue={String(filters.status ?? "")} label="Incident Status" name="status" options={incidentStatuses} />
              <SelectField defaultValue={String(filters.severity ?? "")} label="Incident Severity" name="severity" options={["", ...incidentSeverities]} />
              <Button type="submit" variant="outline">
                Filter
              </Button>
            </form>
            {incidents.length === 0 ? (
              <EmptyState title="No incidents" description="Operational incidents and correlations appear here." />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Title</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {incidents.map((incident) => (
                    <TableRow data-observability-incident-row={incident.id} key={incident.id}>
                      <TableCell>
                        <div className="font-medium">{incident.title}</div>
                        <div className="text-xs text-muted-foreground">{incident.correlation_id ?? "no correlation"}</div>
                        <div className="text-xs text-muted-foreground">
                          {formatSourceLabel(incident.source)}
                          {incident.trace_id ? ` · ${shortTrace(incident.trace_id)}` : ""}
                        </div>
                      </TableCell>
                      <TableCell>{incident.severity}</TableCell>
                      <TableCell>
                        <StatusBadge status={incident.status} />
                      </TableCell>
                      <TableCell>
                        <div className="space-y-2">
                          <Button
                            disabled={incident.status === "resolved"}
                            onClick={() => onAck(incident.id)}
                            type="button"
                            variant="outline"
                          >
                            Ack
                          </Button>
                          <form
                            className="flex gap-2"
                            onSubmit={(event) => {
                              event.preventDefault();
                              onResolve(incident.id, observabilityIncidentResolvePayloadFromForm(event.currentTarget));
                            }}
                          >
                            <Input aria-label={`${incident.title} resolution`} name="resolution_note" placeholder="Resolution note" />
                            <Button disabled={incident.status === "resolved"} type="submit" variant="outline">
                              Resolve
                            </Button>
                          </form>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ChaosPanel({
  experiments,
  filters,
  onCreate,
  onFilter,
  onInvalidInput,
  onRun,
  onStop,
  runs
}: {
  experiments: ChaosExperiment[];
  filters: ObservabilityParams;
  onCreate: (payload: Record<string, unknown>) => void;
  onFilter: (filters: ObservabilityParams) => void;
  onInvalidInput: (error: unknown) => void;
  onRun: (experimentId: string, payload: Record<string, unknown>) => void;
  onStop: (runId: string) => void;
  runs: ChaosRun[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Chaos Experiments</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="grid gap-3 md:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            try {
              onCreate(observabilityChaosExperimentPayloadFromForm(event.currentTarget));
            } catch (error) {
              onInvalidInput(error);
              return;
            }
            event.currentTarget.reset();
          }}
        >
          <Field label="Experiment Name" name="name" />
          <SelectField label="Fault Type" name="fault_type" options={chaosFaultTypes} />
          <SelectField label="Chaos Target Type" name="target_type" options={targetTypes} />
          <Field label="Chaos Target ID" name="target_id" placeholder="agent_1" />
          <TextAreaField defaultValue='{"max_agents":1,"environment":"demo"}' label="Blast Radius JSON" name="blast_radius_json" />
          <TextAreaField defaultValue='{"max_error_rate":0.05}' label="Guardrails JSON" name="guardrails_json" />
          <div>
            <Button type="submit">
              <FlaskConical className="h-4 w-4" />
              Create Experiment
            </Button>
          </div>
        </form>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            onFilter(cleanParams(new FormData(event.currentTarget), ["status", "target_type"]));
          }}
        >
          <SelectField defaultValue={String(filters.status ?? "")} label="Chaos Status" name="status" options={["", "ready", "paused", "disabled"]} />
          <SelectField defaultValue={String(filters.target_type ?? "")} label="Chaos Filter Target" name="target_type" options={["", ...targetTypes]} />
          <Button type="submit" variant="outline">
            Filter
          </Button>
        </form>
        {experiments.length === 0 ? (
          <EmptyState title="No chaos experiments" description="Create guarded experiments before running them." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Fault</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Run</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {experiments.map((experiment) => {
                const canRun = canRunChaosExperiment(experiment);
                return (
                  <TableRow data-observability-chaos-row={experiment.id} key={experiment.id}>
                    <TableCell>{experiment.name}</TableCell>
                    <TableCell>{experiment.fault_type}</TableCell>
                    <TableCell>
                      <StatusBadge status={experiment.status} />
                    </TableCell>
                    <TableCell>
                      <form
                        className="grid gap-2"
                        onSubmit={(event) => {
                          event.preventDefault();
                          if (!canRun) {
                            return;
                          }
                          onRun(experiment.id, observabilityChaosRunPayloadFromForm(event.currentTarget));
                        }}
                      >
                        <div className="flex gap-2">
                          <Input
                            aria-label={`${experiment.name} error rate`}
                            className="w-24"
                            defaultValue="0.01"
                            disabled={!canRun}
                            name="error_rate"
                            type="number"
                          />
                          <Input
                            aria-label={`${experiment.name} duration`}
                            className="w-24"
                            defaultValue="10"
                            disabled={!canRun}
                            name="duration_seconds"
                            type="number"
                          />
                        </div>
                        <CheckboxField
                          disabled={!canRun}
                          label="Acknowledge blast radius"
                          name="acknowledge_blast_radius"
                        />
                        <Button disabled={!canRun} type="submit" variant="outline">
                          Run Experiment
                        </Button>
                      </form>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
        {runs.length === 0 ? (
          <EmptyState title="No recent run" description="Run an experiment to inspect the result." />
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <div className="rounded-md border p-3" data-observability-chaos-run-detail={run.id} key={run.id}>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium">{run.id}</div>
                    <div className="text-xs text-muted-foreground">{JSON.stringify(run.result)}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={run.status} />
                    <Button
                      disabled={run.status !== "running"}
                      onClick={() => onStop(run.id)}
                      type="button"
                      variant="outline"
                    >
                      Stop
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RolloutPanel({
  filters,
  onAdvance,
  onCreate,
  onFilter,
  onInvalidInput,
  onRollback,
  rollouts
}: {
  filters: ObservabilityParams;
  onAdvance: (rolloutId: string, payload: Record<string, unknown>) => void;
  onCreate: (payload: Record<string, unknown>) => void;
  onFilter: (filters: ObservabilityParams) => void;
  onInvalidInput: (error: unknown) => void;
  onRollback: (rolloutId: string, payload: Record<string, unknown>) => void;
  rollouts: Rollout[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Rollouts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="grid gap-3 md:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            try {
              onCreate(observabilityRolloutPayloadFromForm(event.currentTarget));
            } catch (error) {
              onInvalidInput(error);
              return;
            }
            event.currentTarget.reset();
          }}
        >
          <Field label="Rollout Name" name="name" />
          <SelectField label="Rollout Target Type" name="target_type" options={targetTypes} />
          <Field label="Rollout Target ID" name="target_id" />
          <SelectField label="Strategy" name="strategy" options={rolloutStrategies} />
          <Field defaultValue="5,25,100" label="Stages" name="stages" />
          <TextAreaField defaultValue='{"require_slo_healthy":true}' label="Gates JSON" name="gates_json" />
          <div>
            <Button type="submit">Create Rollout</Button>
          </div>
        </form>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            onFilter(cleanParams(new FormData(event.currentTarget), ["status", "target_type"]));
          }}
        >
          <SelectField defaultValue={String(filters.status ?? "")} label="Rollout Status" name="status" options={["", "active", "blocked", "complete", "rolled_back"]} />
          <SelectField defaultValue={String(filters.target_type ?? "")} label="Rollout Filter Target" name="target_type" options={["", ...targetTypes]} />
          <Button type="submit" variant="outline">
            Filter
          </Button>
        </form>
        {rollouts.length === 0 ? (
          <EmptyState title="No rollouts" description="Create staged operations for risky changes." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Timeline</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rollouts.map((rollout) => {
                const canAdvance = canAdvanceRollout(rollout);
                const canRollback = canRollbackRollout(rollout);
                return (
                  <TableRow data-observability-rollout-row={rollout.id} key={rollout.id}>
                    <TableCell>{rollout.name}</TableCell>
                    <TableCell>
                      <StatusBadge status={rollout.status} />
                    </TableCell>
                    <TableCell>
                      <RolloutTimeline rollout={rollout} />
                    </TableCell>
                    <TableCell>
                      <div className="grid gap-2">
                        <form
                          className="flex flex-wrap gap-2"
                          onSubmit={(event) => {
                            event.preventDefault();
                            if (!canAdvance) {
                              return;
                            }
                            onAdvance(rollout.id, observabilityRolloutAdvancePayloadFromForm(event.currentTarget));
                          }}
                        >
                          <Input
                            aria-label={`${rollout.name} SLO status`}
                            className="w-28"
                            defaultValue="healthy"
                            disabled={!canAdvance}
                            name="slo_status"
                          />
                          <Input
                            aria-label={`${rollout.name} trust score`}
                            className="w-24"
                            defaultValue="1000"
                            disabled={!canAdvance}
                            name="trust_score"
                            type="number"
                          />
                          <Button disabled={!canAdvance} type="submit" variant="outline">
                            Advance
                          </Button>
                        </form>
                        <form
                          className="flex flex-wrap gap-2"
                          onSubmit={(event) => {
                            event.preventDefault();
                            if (!canRollback) {
                              return;
                            }
                            onRollback(rollout.id, observabilityRolloutRollbackPayloadFromForm(event.currentTarget));
                          }}
                        >
                          <Input
                            aria-label={`${rollout.name} rollback reason`}
                            className="w-48"
                            disabled={!canRollback}
                            name="reason"
                            placeholder="Rollback reason"
                          />
                          <Button disabled={!canRollback} type="submit" variant="outline">
                            Rollback
                          </Button>
                        </form>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function RolloutTimeline({ rollout }: { rollout: Rollout }) {
  const stages = rolloutStages(rollout.config, rollout.strategy);
  return (
    <ol className="flex flex-wrap gap-2" data-observability-rollout-timeline={rollout.id}>
      {stages.map((stage) => (
        <li
          className="rounded-md border px-2 py-1 text-xs"
          data-stage={stage}
          key={stage}
        >
          {stage}%
        </li>
      ))}
    </ol>
  );
}

function Metric({ icon, label, value }: { icon?: ReactNode; label: string; value: ReactNode }) {
  return (
    <div className="rounded-md border bg-card p-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function Field({
  defaultValue,
  label,
  name,
  placeholder,
  type = "text"
}: {
  defaultValue?: string;
  label: string;
  name: string;
  placeholder?: string;
  type?: string;
}) {
  const id = `${name}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <Input defaultValue={defaultValue} id={id} name={name} placeholder={placeholder} type={type} />
    </div>
  );
}

function TextAreaField({
  defaultValue,
  label,
  name
}: {
  defaultValue?: string;
  label: string;
  name: string;
}) {
  const id = `${name}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <textarea
        className="min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        defaultValue={defaultValue}
        id={id}
        name={name}
      />
    </div>
  );
}

function SelectField({
  defaultValue,
  label,
  name,
  options
}: {
  defaultValue?: string;
  label: string;
  name: string;
  options: string[];
}) {
  const id = `${name}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <select
        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
        defaultValue={defaultValue}
        id={id}
        name={name}
      >
        {options.map((option) => (
          <option key={option || "all"} value={option}>
            {option || "all"}
          </option>
        ))}
      </select>
    </div>
  );
}

function CheckboxField({
  disabled = false,
  label,
  name
}: {
  disabled?: boolean;
  label: string;
  name: string;
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input disabled={disabled} name={name} type="checkbox" />
      {label}
    </label>
  );
}

export function observabilitySloPayloadFromValues(values: Record<string, unknown>) {
  return {
    name: String(values.name ?? "").trim(),
    target_type: String(values.target_type ?? "agent").trim(),
    target_id: String(values.target_id ?? "").trim(),
    sli: String(values.sli ?? "task_success_rate").trim(),
    target_value: numberValue(values.target_value, "Target Value"),
    window: String(values.window ?? "30d").trim()
  };
}

export function observabilitySloPayloadFromForm(form: HTMLFormElement) {
  return observabilitySloPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilitySloMeasurementPayloadFromValues(values: Record<string, unknown>) {
  return {
    value: numberValue(values.value, "Measurement Value"),
    good_events: optionalNumber(values.good_events, "Good Events"),
    total_events: optionalNumber(values.total_events, "Total Events")
  };
}

export function observabilitySloMeasurementPayloadFromForm(form: HTMLFormElement) {
  return observabilitySloMeasurementPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityCostBudgetPayloadFromValues(values: Record<string, unknown>) {
  return {
    target_type: String(values.target_type ?? "agent").trim(),
    target_id: String(values.target_id ?? "").trim(),
    period: String(values.period ?? "monthly").trim(),
    amount_limit: numberValue(values.amount_limit, "Amount Limit"),
    action_on_breach: String(values.action_on_breach ?? "warn").trim()
  };
}

export function observabilityCostBudgetPayloadFromForm(form: HTMLFormElement) {
  return observabilityCostBudgetPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityCostEventPayloadFromValues(values: Record<string, unknown>) {
  return {
    target_type: String(values.target_type ?? "agent").trim(),
    target_id: String(values.target_id ?? "").trim(),
    provider: String(values.provider ?? "").trim(),
    model: String(values.model ?? "").trim(),
    amount: numberValue(values.amount, "Amount"),
    units: numberValue(values.units, "Units"),
    correlation_id: optionalString(values.correlation_id)
  };
}

export function observabilityCostEventPayloadFromForm(form: HTMLFormElement) {
  return observabilityCostEventPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityIncidentPayloadFromValues(values: Record<string, unknown>) {
  return {
    severity: String(values.severity ?? "warning").trim(),
    title: String(values.title ?? "").trim(),
    summary: String(values.summary ?? "").trim(),
    correlation_id: optionalString(values.correlation_id)
  };
}

export function observabilityIncidentPayloadFromForm(form: HTMLFormElement) {
  return observabilityIncidentPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityIncidentResolvePayloadFromValues(values: Record<string, unknown>) {
  return {
    resolution_note: String(values.resolution_note ?? "").trim()
  };
}

export function observabilityIncidentResolvePayloadFromForm(form: HTMLFormElement) {
  return observabilityIncidentResolvePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityChaosExperimentPayloadFromValues(values: Record<string, unknown>) {
  return {
    name: String(values.name ?? "").trim(),
    fault_type: String(values.fault_type ?? "latency").trim(),
    target_type: String(values.target_type ?? "agent").trim(),
    target_id: String(values.target_id ?? "").trim(),
    blast_radius: parseJsonObjectField(values.blast_radius_json, "Blast Radius JSON", {
      emptyFallback: { max_agents: 1, environment: "demo" }
    }),
    guardrails: parseJsonObjectField(values.guardrails_json, "Guardrails JSON", {
      emptyFallback: { max_error_rate: 0.05 }
    })
  };
}

export function observabilityChaosExperimentPayloadFromForm(form: HTMLFormElement) {
  return observabilityChaosExperimentPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityChaosRunPayloadFromValues(values: Record<string, unknown>) {
  const observedMetrics: Record<string, number> = {};
  for (const key of ["error_rate", "duration_seconds", "latency_ms", "trust_score"]) {
    if (optionalString(values[key]) !== null) {
      observedMetrics[key] = numberValue(values[key], humanizeFieldName(key));
    }
  }
  return {
    observed_metrics: observedMetrics,
    acknowledgement: values.acknowledge_blast_radius ? "blast-radius-acknowledged" : null
  };
}

export function observabilityChaosRunPayloadFromForm(form: HTMLFormElement) {
  return observabilityChaosRunPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityRolloutPayloadFromValues(values: Record<string, unknown>) {
  const strategy = String(values.strategy ?? "canary").trim();
  return {
    name: String(values.name ?? "").trim(),
    target_type: String(values.target_type ?? "agent").trim(),
    target_id: String(values.target_id ?? "").trim(),
    strategy,
    config: {
      stages: parseIntegerListField(values.stages ?? "5,25,100", "Stages"),
      gates: parseJsonObjectField(values.gates_json, "Gates JSON", { emptyFallback: {} })
    }
  };
}

export function observabilityRolloutPayloadFromForm(form: HTMLFormElement) {
  return observabilityRolloutPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityRolloutAdvancePayloadFromValues(values: Record<string, unknown>) {
  const metrics: Record<string, number | string> = {};
  if (optionalString(values.slo_status) !== null) {
    metrics.slo_status = String(values.slo_status).trim();
  }
  for (const key of ["policy_deny_rate", "trust_score", "open_incidents"]) {
    if (optionalString(values[key]) !== null) {
      metrics[key] = numberValue(values[key], humanizeFieldName(key));
    }
  }
  return { metrics };
}

export function observabilityRolloutAdvancePayloadFromForm(form: HTMLFormElement) {
  return observabilityRolloutAdvancePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityRolloutRollbackPayloadFromValues(values: Record<string, unknown>) {
  return {
    reason: String(values.reason ?? "").trim()
  };
}

export function observabilityRolloutRollbackPayloadFromForm(form: HTMLFormElement) {
  return observabilityRolloutRollbackPayloadFromValues(Object.fromEntries(new FormData(form)));
}

function cleanParams(form: FormData, keys: string[]) {
  return Object.fromEntries(
    keys
      .map((key) => [key, String(form.get(key) ?? "").trim()])
      .filter(([, value]) => value !== "")
  );
}

function formatMoney(value: number) {
  return `$${Number(value ?? 0).toFixed(2)}`;
}

function formatSourceLabel(source?: string | null) {
  if (!source) {
    return "Unknown";
  }
  return source
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatFreshness(value?: string | null) {
  if (!value) {
    return "n/a";
  }
  return formatShortDate(value);
}

function shortTrace(traceId: string) {
  return `trace ${traceId.slice(0, 8)}`;
}

function costDistributionRows(costs: CostDashboard) {
  return [
    ...Object.entries(costs.by_provider).map(([name, amount]) => ({
      amount,
      group: "Provider",
      label: `Provider: ${name}`,
      name
    })),
    ...Object.entries(costs.by_model).map(([name, amount]) => ({
      amount,
      group: "Model",
      label: `Model: ${name}`,
      name
    })),
    ...Object.entries(costs.by_target).map(([name, amount]) => ({
      amount,
      group: "Target",
      label: `Target: ${name}`,
      name
    }))
  ]
    .filter((row) => row.amount > 0)
    .sort((left, right) => right.amount - left.amount || left.label.localeCompare(right.label));
}

function sloTrendData(slo: SloObjective) {
  return [...slo.measurements]
    .sort((left, right) => left.measured_at.localeCompare(right.measured_at))
    .map((measurement) => ({
      id: measurement.id,
      label: formatShortDate(measurement.measured_at),
      status: measurement.status,
      valuePercent: percentage(measurement.value),
      targetPercent: percentage(slo.target_value),
      burnRate: measurement.burn_rate
    }));
}

function percentage(value: number) {
  return Number((Number(value ?? 0) * 100).toFixed(2));
}

function formatShortDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("en-US", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short"
  });
}

function spansToTimeline(detail: ObservabilityTraceDetail): ObservabilityTraceDetail["timeline"] {
  return detail.spans.map((span) => ({
    id: span.id,
    kind: "span",
    name: span.name,
    parent_span_id: span.parent_span_id,
    span_id: span.span_id,
    status: span.status,
    timestamp: span.start_time
  }));
}

function numberValue(value: unknown, fieldName: string) {
  return parseRequiredNumberField(value, fieldName);
}

function optionalNumber(value: unknown, fieldName: string) {
  return parseOptionalNumberField(value, fieldName);
}

function optionalString(value: unknown) {
  const normalized = String(value ?? "").trim();
  return normalized || null;
}

function rolloutStages(config: Record<string, unknown>, strategy: string) {
  const stages = config.stages;
  if (Array.isArray(stages) && stages.length) {
    return stages
      .map((stage) => Number.parseInt(String(stage), 10))
      .filter((stage) => Number.isFinite(stage));
  }
  if (strategy === "percentage") {
    const percentage = Number.parseInt(String(config.percentage ?? 100), 10);
    return Number.isFinite(percentage) ? [percentage] : [];
  }
  return [5, 25, 50, 100];
}

function emptyCostDashboard(): CostDashboard {
  return {
    budgets: [],
    events: [],
    total_amount: 0,
    by_target: {},
    by_provider: {},
    by_model: {}
  };
}

function humanizeFieldName(name: string) {
  return name
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
