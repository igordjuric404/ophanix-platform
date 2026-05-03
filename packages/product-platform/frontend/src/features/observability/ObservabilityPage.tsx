import { Activity, AlertTriangle, CircleDollarSign, FlaskConical, Gauge } from "lucide-react";
import { useState, type ReactNode } from "react";

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
  type ChaosExperiment,
  type ChaosRun,
  type CostDashboard,
  type Incident,
  type ObservabilityParams,
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

const targetTypes = ["agent", "mcp-server", "runtime", "environment"];
const incidentSeverities = ["info", "warning", "critical"];
const incidentStatuses = ["", "open", "acknowledged", "resolved"];
const chaosFaultTypes = ["latency", "error", "timeout", "trust_perturbation", "policy_denial"];
const rolloutStrategies = ["canary", "percentage"];

export function ObservabilityPage() {
  const [incidentFilters, setIncidentFilters] = useState<ObservabilityParams>({});
  const [chaosFilters, setChaosFilters] = useState<ObservabilityParams>({});
  const [rolloutFilters, setRolloutFilters] = useState<ObservabilityParams>({});
  const [chaosRuns, setChaosRuns] = useState<ChaosRun[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const slosQuery = useObservabilitySlos();
  const costsQuery = useObservabilityCosts();
  const incidentsQuery = useObservabilityIncidents(incidentFilters);
  const chaosQuery = useObservabilityChaosExperiments(chaosFilters);
  const rolloutsQuery = useObservabilityRollouts(rolloutFilters);
  const mutation = useObservabilityMutation();

  const slos = slosQuery.data ?? [];
  const costs = costsQuery.data ?? emptyCostDashboard();
  const incidents = incidentsQuery.data ?? [];
  const experiments = chaosQuery.data ?? [];
  const rollouts = rolloutsQuery.data ?? [];

  async function runTask(label: string, task: () => Promise<unknown>) {
    try {
      await mutation.mutateAsync(task);
      setMessage(label);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed");
    }
  }

  async function runResultTask<T>(label: string, task: () => Promise<T>, onResult: (value: T) => void) {
    try {
      const result = (await mutation.mutateAsync(task)) as T;
      onResult(result);
      setMessage(label);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed");
    }
  }

  return (
    <>
      <PageHeader
        title="Observability"
        description="SLO, cost, incident, chaos, and rollout operations for governed agents."
      />
      <div className="space-y-6 p-6">
        {message ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            {message}
          </div>
        ) : null}
        <ObservabilitySummary costs={costs} incidents={incidents} rollouts={rollouts} slos={slos} />
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <SloPanel
            onCreate={(payload) => runTask("SLO created", () => createObservabilitySlo(payload))}
            onMeasure={(sloId, payload) =>
              runTask("SLO measurement recorded", () =>
                createObservabilitySloMeasurement(sloId, payload)
              )
            }
            slos={slos}
          />
          <CostPanel
            costs={costs}
            onBudget={(payload) =>
              runTask("Cost budget created", () => createObservabilityCostBudget(payload))
            }
            onEvent={(payload) =>
              runTask("Cost event recorded", () => createObservabilityCostEvent(payload))
            }
          />
        </div>
        <IncidentPanel
          filters={incidentFilters}
          incidents={incidents}
          onAck={(incidentId) =>
            runTask("Incident acknowledged", () => acknowledgeObservabilityIncident(incidentId))
          }
          onCreate={(payload) =>
            runTask("Incident created", () => createObservabilityIncident(payload))
          }
          onFilter={setIncidentFilters}
          onResolve={(incidentId, payload) =>
            runTask("Incident resolved", () => resolveObservabilityIncident(incidentId, payload))
          }
        />
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <ChaosPanel
            experiments={experiments}
            filters={chaosFilters}
            onCreate={(payload) =>
              runTask("Chaos experiment created", () =>
                createObservabilityChaosExperiment(payload)
              )
            }
            onFilter={setChaosFilters}
            onRun={(experimentId, payload) =>
              runResultTask(
                "Chaos experiment run completed",
                () => runObservabilityChaosExperiment(experimentId, payload),
                (run) => setChaosRuns((items) => [run, ...items.filter((item) => item.id !== run.id)])
              )
            }
            onStop={(runId) =>
              runResultTask(
                "Chaos run stopped",
                () => stopObservabilityChaosRun(runId),
                (run) => setChaosRuns((items) => [run, ...items.filter((item) => item.id !== run.id)])
              )
            }
            runs={chaosRuns}
          />
          <RolloutPanel
            filters={rolloutFilters}
            onAdvance={(rolloutId, payload) =>
              runTask("Rollout advanced", () => advanceObservabilityRollout(rolloutId, payload))
            }
            onCreate={(payload) =>
              runTask("Rollout created", () => createObservabilityRollout(payload))
            }
            onFilter={setRolloutFilters}
            onRollback={(rolloutId, payload) =>
              runTask("Rollout rolled back", () => rollbackObservabilityRollout(rolloutId, payload))
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
  slos
}: {
  costs: CostDashboard;
  incidents: Incident[];
  rollouts: Rollout[];
  slos: SloObjective[];
}) {
  return (
    <div className="grid gap-4 md:grid-cols-4">
      <Metric icon={<Gauge className="h-4 w-4" />} label="SLOs" value={slos.length} />
      <Metric icon={<CircleDollarSign className="h-4 w-4" />} label="Total Cost" value={formatMoney(costs.total_amount)} />
      <Metric icon={<AlertTriangle className="h-4 w-4" />} label="Open Incidents" value={incidents.filter((item) => item.status !== "resolved").length} />
      <Metric icon={<Activity className="h-4 w-4" />} label="Rollouts" value={rollouts.length} />
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
                <TableHead>Measure</TableHead>
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
        <div className="grid gap-3 md:grid-cols-3" data-observability-cost-chart>
          {Object.entries(costs.by_provider).map(([provider, amount]) => (
            <Metric key={provider} label={provider} value={formatMoney(amount)} />
          ))}
          {Object.entries(costs.by_model).map(([model, amount]) => (
            <Metric key={model} label={model} value={formatMoney(amount)} />
          ))}
        </div>
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
  onRun,
  onStop,
  runs
}: {
  experiments: ChaosExperiment[];
  filters: ObservabilityParams;
  onCreate: (payload: Record<string, unknown>) => void;
  onFilter: (filters: ObservabilityParams) => void;
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
            onCreate(observabilityChaosExperimentPayloadFromForm(event.currentTarget));
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
              {experiments.map((experiment) => (
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
                        onRun(experiment.id, observabilityChaosRunPayloadFromForm(event.currentTarget));
                      }}
                    >
                      <div className="flex gap-2">
                        <Input aria-label={`${experiment.name} error rate`} className="w-24" defaultValue="0.01" name="error_rate" type="number" />
                        <Input aria-label={`${experiment.name} duration`} className="w-24" defaultValue="10" name="duration_seconds" type="number" />
                      </div>
                      <CheckboxField label="Acknowledge blast radius" name="acknowledge_blast_radius" />
                      <Button type="submit" variant="outline">
                        Run Experiment
                      </Button>
                    </form>
                  </TableCell>
                </TableRow>
              ))}
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
  onRollback,
  rollouts
}: {
  filters: ObservabilityParams;
  onAdvance: (rolloutId: string, payload: Record<string, unknown>) => void;
  onCreate: (payload: Record<string, unknown>) => void;
  onFilter: (filters: ObservabilityParams) => void;
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
            onCreate(observabilityRolloutPayloadFromForm(event.currentTarget));
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
              {rollouts.map((rollout) => (
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
                          onAdvance(rollout.id, observabilityRolloutAdvancePayloadFromForm(event.currentTarget));
                        }}
                      >
                        <Input aria-label={`${rollout.name} SLO status`} className="w-28" defaultValue="healthy" name="slo_status" />
                        <Input aria-label={`${rollout.name} trust score`} className="w-24" defaultValue="1000" name="trust_score" type="number" />
                        <Button type="submit" variant="outline">
                          Advance
                        </Button>
                      </form>
                      <form
                        className="flex flex-wrap gap-2"
                        onSubmit={(event) => {
                          event.preventDefault();
                          onRollback(rollout.id, observabilityRolloutRollbackPayloadFromForm(event.currentTarget));
                        }}
                      >
                        <Input aria-label={`${rollout.name} rollback reason`} className="w-48" name="reason" placeholder="Rollback reason" />
                        <Button type="submit" variant="outline">
                          Rollback
                        </Button>
                      </form>
                    </div>
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

function CheckboxField({ label, name }: { label: string; name: string }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input name={name} type="checkbox" />
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
    target_value: numberValue(values.target_value),
    window: String(values.window ?? "30d").trim()
  };
}

export function observabilitySloPayloadFromForm(form: HTMLFormElement) {
  return observabilitySloPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilitySloMeasurementPayloadFromValues(values: Record<string, unknown>) {
  return {
    value: numberValue(values.value),
    good_events: optionalNumber(values.good_events),
    total_events: optionalNumber(values.total_events)
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
    amount_limit: numberValue(values.amount_limit),
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
    amount: numberValue(values.amount),
    units: numberValue(values.units),
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
    blast_radius: parseJsonObject(values.blast_radius_json, { max_agents: 1, environment: "demo" }),
    guardrails: parseJsonObject(values.guardrails_json, { max_error_rate: 0.05 })
  };
}

export function observabilityChaosExperimentPayloadFromForm(form: HTMLFormElement) {
  return observabilityChaosExperimentPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function observabilityChaosRunPayloadFromValues(values: Record<string, unknown>) {
  const observedMetrics: Record<string, number> = {};
  for (const key of ["error_rate", "duration_seconds", "latency_ms", "trust_score"]) {
    if (optionalString(values[key]) !== null) {
      observedMetrics[key] = numberValue(values[key]);
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
      stages: String(values.stages ?? "5,25,100")
        .split(",")
        .map((stage) => Number.parseInt(stage.trim(), 10))
        .filter((stage) => Number.isFinite(stage)),
      gates: parseJsonObject(values.gates_json, {})
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
      metrics[key] = numberValue(values[key]);
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

function numberValue(value: unknown) {
  const parsed = Number.parseFloat(String(value ?? "0"));
  return Number.isFinite(parsed) ? parsed : 0;
}

function optionalNumber(value: unknown) {
  return optionalString(value) === null ? null : numberValue(value);
}

function optionalString(value: unknown) {
  const normalized = String(value ?? "").trim();
  return normalized || null;
}

function parseJsonObject(value: unknown, fallback: Record<string, unknown>) {
  try {
    const parsed = JSON.parse(String(value ?? ""));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : fallback;
  } catch {
    return fallback;
  }
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
