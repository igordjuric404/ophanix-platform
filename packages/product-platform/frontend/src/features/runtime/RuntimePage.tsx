import {
  Activity,
  Ban,
  CheckCircle2,
  Gauge,
  Play,
  ShieldAlert,
  Square
} from "lucide-react";
import {
  useState,
  type FormEvent,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes
} from "react";

import {
  addRuntimeSagaStep,
  cancelRuntimeSaga,
  createRuntimeAction,
  createRuntimeRingRule,
  createRuntimeSaga,
  createRuntimeSandboxProfile,
  createRuntimeSession,
  endRuntimeSession,
  executeRuntimeSaga,
  testRuntimeSandboxProfile,
  triggerRuntimeKillSwitch,
  useRuntimeKillSwitchEvents,
  useRuntimeMutation,
  useRuntimeRingDecisions,
  useRuntimeRingRules,
  useRuntimeSagaDetail,
  useRuntimeSagas,
  useRuntimeSandboxProfiles,
  useRuntimeSessionDetail,
  useRuntimeSessions,
  type RuntimeAction,
  type RuntimeKillSwitchEvent,
  type RuntimeParams,
  type RuntimeRingDecision,
  type RuntimeRingRule,
  type RuntimeSaga,
  type RuntimeSandboxDecision,
  type RuntimeSandboxProfile,
  type RuntimeSession
} from "../../api/runtime";
import { PageHeader } from "../../components/layout/PageHeader";
import { EmptyState } from "../../components/shared/EmptyState";
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
import {
  ActionFeedback,
  actionErrorMessage,
  useActionFeedback
} from "../../components/shared/ActionFeedback";
import type { TenantContext } from "../../api/client";
import { QueryErrorSummary } from "../../components/shared/ErrorState";
import {
  canAddRuntimeSagaStep,
  canCancelRuntimeSaga,
  canEndRuntimeSession,
  canExecuteRuntimeSaga
} from "../../lib/actionAvailability";
import { parseOptionalNumberField, parseRequiredNumberField } from "../../lib/forms";
import { cn } from "../../lib/utils";

const rings = ["0", "1", "2", "3"];
const reversibilityOptions = ["none", "partial", "full"];
const ringDecisionResults = ["", "allowed", "denied"];
const sandboxProviders = ["subprocess", "noop"];
const killSwitchTargets = ["session", "agent", "mcp_server", "tool", "plugin"];

export function RuntimePage() {
  const [sessionFilters, setSessionFilters] = useState<RuntimeParams>({});
  const [decisionFilters, setDecisionFilters] = useState<RuntimeParams>({});
  const [sagaFilters, setSagaFilters] = useState<RuntimeParams>({});
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [selectedSagaId, setSelectedSagaId] = useState<string | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [sandboxDecision, setSandboxDecision] = useState<RuntimeSandboxDecision | null>(null);
  const { feedback, runWithFeedback, setError } = useActionFeedback();

  const sessionsQuery = useRuntimeSessions(sessionFilters);
  const decisionsQuery = useRuntimeRingDecisions(decisionFilters);
  const rulesQuery = useRuntimeRingRules();
  const sagasQuery = useRuntimeSagas(sagaFilters);
  const sandboxProfilesQuery = useRuntimeSandboxProfiles();
  const killSwitchEventsQuery = useRuntimeKillSwitchEvents();
  const mutation = useRuntimeMutation();

  const sessions = sessionsQuery.data ?? [];
  const decisions = decisionsQuery.data ?? [];
  const rules = rulesQuery.data ?? [];
  const sagas = sagasQuery.data ?? [];
  const profiles = sandboxProfilesQuery.data ?? [];
  const killSwitchEvents = killSwitchEventsQuery.data ?? [];
  const activeSessionId = selectedSessionId;
  const activeSagaId = selectedSagaId;
  const activeProfileId = selectedProfileId;
  const sessionDetailQuery = useRuntimeSessionDetail(activeSessionId);
  const sagaDetailQuery = useRuntimeSagaDetail(activeSagaId);
  const selectedSession =
    activeSessionId
      ? sessionDetailQuery.data ?? sessions.find((session) => session.id === activeSessionId) ?? null
      : null;
  const selectedSaga = activeSagaId
    ? sagaDetailQuery.data ?? sagas.find((saga) => saga.id === activeSagaId) ?? null
    : null;
  const selectedProfile = activeProfileId
    ? profiles.find((profile) => profile.id === activeProfileId) ?? null
    : null;

  async function runTask(label: string, task: (tenantContext: TenantContext) => Promise<unknown>) {
    const result = await runWithFeedback(() => mutation.mutateAsync(task), {
      errorMessage: `${label} failed`,
      successMessage: label
    });
    return result !== null;
  }

  return (
    <>
      <PageHeader
        title="Runtime"
        description="Runtime sessions, execution rings, saga orchestration, sandbox profiles, and kill switch controls."
      />
      <div className="space-y-6 p-6">
        <ActionFeedback feedback={feedback} />
        <QueryErrorSummary
          items={[
            { error: sessionsQuery.error, isError: sessionsQuery.isError, label: "Runtime sessions", onRetry: () => void sessionsQuery.refetch() },
            { error: decisionsQuery.error, isError: decisionsQuery.isError, label: "Ring decisions", onRetry: () => void decisionsQuery.refetch() },
            { error: rulesQuery.error, isError: rulesQuery.isError, label: "Ring rules", onRetry: () => void rulesQuery.refetch() },
            { error: sagasQuery.error, isError: sagasQuery.isError, label: "Runtime sagas", onRetry: () => void sagasQuery.refetch() },
            { error: sandboxProfilesQuery.error, isError: sandboxProfilesQuery.isError, label: "Sandbox profiles", onRetry: () => void sandboxProfilesQuery.refetch() },
            { error: killSwitchEventsQuery.error, isError: killSwitchEventsQuery.isError, label: "Kill switch events", onRetry: () => void killSwitchEventsQuery.refetch() },
            { error: sessionDetailQuery.error, isError: sessionDetailQuery.isError, label: "Session detail", onRetry: () => void sessionDetailQuery.refetch() },
            { error: sagaDetailQuery.error, isError: sagaDetailQuery.isError, label: "Saga detail", onRetry: () => void sagaDetailQuery.refetch() }
          ]}
        />
        <RuntimeSummary
          decisions={decisions}
          events={killSwitchEvents}
          profiles={profiles}
          sessions={sessions}
        />
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(24rem,0.85fr)]">
          <SessionsPanel
            filters={sessionFilters}
            onCreate={(payload) =>
              runTask("Runtime session started", (tenantContext) =>
                createRuntimeSession(payload, tenantContext)
              )
            }
            onFilter={setSessionFilters}
            onSelect={setSelectedSessionId}
            selectedSessionId={activeSessionId}
            sessions={sessions}
          />
          <SessionDetailPanel
            onAction={(sessionId, payload) =>
              runTask("Runtime action evaluated", (tenantContext) =>
                createRuntimeAction(sessionId, payload, tenantContext)
              )
            }
            onEnd={(sessionId, payload) =>
              runTask("Runtime session ended", (tenantContext) =>
                endRuntimeSession(sessionId, payload, tenantContext)
              )
            }
            session={selectedSession}
          />
        </div>
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.7fr)]">
          <RingDecisionsPanel decisions={decisions} filters={decisionFilters} onFilter={setDecisionFilters} />
          <RingRulesPanel
            onCreate={(payload) =>
              runTask("Ring rule created", (tenantContext) =>
                createRuntimeRingRule(payload, tenantContext)
              )
            }
            rules={rules}
          />
        </div>
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <SagasPanel
            filters={sagaFilters}
            onCreate={(payload) =>
              runTask("Saga created", (tenantContext) => createRuntimeSaga(payload, tenantContext))
            }
            onFilter={setSagaFilters}
            onSelect={setSelectedSagaId}
            sagas={sagas}
            selectedSagaId={activeSagaId}
          />
          <SagaMonitor
            onAddStep={(sagaId, payload) =>
              runTask("Saga step added", (tenantContext) =>
                addRuntimeSagaStep(sagaId, payload, tenantContext)
              )
            }
            onCancel={(sagaId, payload) =>
              runTask("Saga cancelled", (tenantContext) =>
                cancelRuntimeSaga(sagaId, payload, tenantContext)
              )
            }
            onExecute={(sagaId, payload) =>
              runTask("Saga execution started", (tenantContext) =>
                executeRuntimeSaga(sagaId, payload, tenantContext)
              )
            }
            saga={selectedSaga}
          />
        </div>
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.75fr)]">
          <SandboxPanel
            decision={sandboxDecision}
            onCreate={(payload) =>
              runTask("Sandbox profile created", (tenantContext) =>
                createRuntimeSandboxProfile(payload, tenantContext)
              )
            }
            onSelect={(profileId) => {
              setSelectedProfileId(profileId);
              setSandboxDecision(null);
            }}
            onTest={async (profileId, payload) => {
              const result = await runWithFeedback<RuntimeSandboxDecision>(
                () =>
                  mutation.mutateAsync((tenantContext) =>
                    testRuntimeSandboxProfile(profileId, payload, tenantContext)
                  ) as Promise<RuntimeSandboxDecision>,
                {
                  errorMessage: "Sandbox profile test failed",
                  successMessage: "Sandbox profile tested"
                }
              );
              if (!result) {
                return;
              }
              setSandboxDecision(result);
            }}
            profiles={profiles}
            selectedProfile={selectedProfile}
          />
          <KillSwitchPanel
            events={killSwitchEvents}
            onInvalidInput={(error) =>
              setError(actionErrorMessage(error, "Invalid kill-switch input"))
            }
            onTrigger={(payload) =>
              runTask("Kill switch triggered", (tenantContext) =>
                triggerRuntimeKillSwitch(payload, tenantContext)
              )
            }
          />
        </div>
      </div>
    </>
  );
}

function RuntimeSummary({
  decisions,
  events,
  profiles,
  sessions
}: {
  decisions: RuntimeRingDecision[];
  events: RuntimeKillSwitchEvent[];
  profiles: RuntimeSandboxProfile[];
  sessions: RuntimeSession[];
}) {
  const activeSessions = sessions.filter((session) => session.state === "active").length;
  const denied = decisions.filter((decision) => decision.result === "denied").length;
  const activeProfiles = profiles.filter((profile) => profile.status === "active").length;

  return (
    <section className="grid gap-4 md:grid-cols-4" data-runtime-summary>
      <MetricCard icon={<Activity className="h-4 w-4" />} label="Active Sessions" value={activeSessions} />
      <MetricCard icon={<Gauge className="h-4 w-4" />} label="Denied Decisions" value={denied} />
      <MetricCard icon={<ShieldAlert className="h-4 w-4" />} label="Sandbox Profiles" value={activeProfiles} />
      <MetricCard icon={<Ban className="h-4 w-4" />} label="Kill Switches" value={events.length} />
    </section>
  );
}

function SessionsPanel({
  filters,
  onCreate,
  onFilter,
  onSelect,
  selectedSessionId,
  sessions
}: {
  filters: RuntimeParams;
  onCreate: (payload: Record<string, unknown>) => void;
  onFilter: (params: RuntimeParams) => void;
  onSelect: (sessionId: string) => void;
  selectedSessionId: string | null;
  sessions: RuntimeSession[];
}) {
  function onCreateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate(runtimeSessionPayloadFromForm(event.currentTarget));
    event.currentTarget.reset();
  }

  function onFilterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter({
      state: emptyToNull(formString(event.currentTarget, "state")),
      agent_id: emptyToNull(formString(event.currentTarget, "agent_id"))
    });
  }

  return (
    <Card data-runtime-sessions>
      <CardHeader>
        <CardTitle>Runtime Sessions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]" data-runtime-session-form onSubmit={onCreateSubmit}>
          <Field idPrefix="runtime-session" label="Agent ID" name="agent_id" required />
          <SelectField idPrefix="runtime-session" label="Ring" name="ring" options={rings} value="2" />
          <Field idPrefix="runtime-session" label="Sponsor" name="sponsor_user_id" />
          <Button className="self-end" type="submit">Start</Button>
        </form>
        <form className="grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={onFilterSubmit}>
          <SelectField
            emptyLabel="All states"
            idPrefix="runtime-session-filter"
            label="State"
            name="state"
            options={["", "active", "archived"]}
            value={String(filters.state ?? "")}
          />
          <Field
            defaultValue={String(filters.agent_id ?? "")}
            idPrefix="runtime-session-filter"
            label="Agent"
            name="agent_id"
          />
          <Button className="self-end" type="submit">Filter</Button>
        </form>
        {sessions.length === 0 ? (
          <EmptyState title="No sessions" description="Start a runtime session for an active agent." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Agent</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Ring</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Ended</TableHead>
                <TableHead>Detail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.map((session) => (
                <TableRow data-runtime-session-row={session.id} key={session.id}>
                  <TableCell>
                    <strong>{session.agent_name ?? session.agent_id}</strong>
                    <small className="block text-muted-foreground">{session.id}</small>
                  </TableCell>
                  <TableCell><StatusBadge status={session.state} /></TableCell>
                  <TableCell>{session.ring}</TableCell>
                  <TableCell>{session.started_at}</TableCell>
                  <TableCell>{session.ended_at ?? "active"}</TableCell>
                  <TableCell>
                    <Button
                      disabled={selectedSessionId === session.id}
                      onClick={() => onSelect(session.id)}
                      type="button"
                      variant="outline"
                    >
                      Open
                    </Button>
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

function SessionDetailPanel({
  onAction,
  onEnd,
  session
}: {
  onAction: (sessionId: string, payload: Record<string, unknown>) => void;
  onEnd: (sessionId: string, payload: Record<string, unknown>) => void;
  session: RuntimeSession | null;
}) {
  if (!session) {
    return (
      <Card data-runtime-session-detail>
        <CardHeader><CardTitle>Session Timeline</CardTitle></CardHeader>
        <CardContent>
          <EmptyState title="No session selected" description="Start or open a session to submit actions." />
        </CardContent>
      </Card>
    );
  }
  const sessionId = session.id;
  const actions = session.actions ?? [];
  const canEndSession = canEndRuntimeSession(session);

  function submitAction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onAction(sessionId, runtimeActionPayloadFromForm(event.currentTarget));
    event.currentTarget.reset();
  }

  function submitEnd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canEndSession) {
      return;
    }
    onEnd(sessionId, runtimeSessionEndPayloadFromForm(event.currentTarget));
    event.currentTarget.reset();
  }

  return (
    <Card data-runtime-session-detail={session.id}>
      <CardHeader>
        <CardTitle>Session Timeline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 md:grid-cols-3">
          <Metadata label="Agent" value={session.agent_name ?? session.agent_id} />
          <Metadata label="State" value={<StatusBadge status={session.state} />} />
          <Metadata label="Assigned Ring" value={session.ring} />
        </div>
        <form className="grid gap-3 md:grid-cols-3" data-runtime-action-form onSubmit={submitAction}>
          <Field idPrefix="runtime-action" label="Action" name="action_name" required />
          <Field defaultValue="runtime-action" idPrefix="runtime-action" label="Resource" name="resource_type" required />
          <SelectField idPrefix="runtime-action" label="Reversibility" name="reversibility" options={reversibilityOptions} />
          <CheckboxField idPrefix="runtime-action" label="Read only" name="is_read_only" />
          <CheckboxField idPrefix="runtime-action" label="Admin" name="is_admin" />
          <Button className="self-end" type="submit">Evaluate</Button>
        </form>
        <form className="grid gap-3 md:grid-cols-[1fr_auto]" data-runtime-session-end-form onSubmit={submitEnd}>
          <Field idPrefix="runtime-session-end" label="End Reason" name="reason" />
          <Button className="self-end" disabled={!canEndSession} type="submit" variant="outline">
            End Session
          </Button>
        </form>
        {actions.length === 0 ? (
          <EmptyState title="No actions" description="Submit an action for ring evaluation." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action</TableHead>
                <TableHead>Decision</TableHead>
                <TableHead>Required</TableHead>
                <TableHead>Assigned</TableHead>
                <TableHead>Reason</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {actions.map((action) => (
                <RuntimeActionRow action={action} key={action.id} />
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function RuntimeActionRow({ action }: { action: RuntimeAction }) {
  return (
    <TableRow data-runtime-action-row={action.id}>
      <TableCell>
        <strong>{action.action_name}</strong>
        <small className="block text-muted-foreground">{action.resource_type}</small>
      </TableCell>
      <TableCell><StatusBadge status={action.decision} /></TableCell>
      <TableCell>{action.required_ring ?? "n/a"}</TableCell>
      <TableCell>{action.ring_decision?.assigned_ring ?? "n/a"}</TableCell>
      <TableCell>{action.reason}</TableCell>
    </TableRow>
  );
}

function RingDecisionsPanel({
  decisions,
  filters,
  onFilter
}: {
  decisions: RuntimeRingDecision[];
  filters: RuntimeParams;
  onFilter: (params: RuntimeParams) => void;
}) {
  const allowed = decisions.filter((decision) => decision.result === "allowed").length;
  const denied = decisions.filter((decision) => decision.result === "denied").length;

  function submitFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter({
      result: emptyToNull(formString(event.currentTarget, "result")),
      session_id: emptyToNull(formString(event.currentTarget, "session_id")),
      agent_id: emptyToNull(formString(event.currentTarget, "agent_id"))
    });
  }

  return (
    <Card data-runtime-ring-decisions>
      <CardHeader>
        <CardTitle>Ring Decisions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2" data-runtime-ring-chart>
          <InlineMetric icon={<CheckCircle2 className="h-4 w-4" />} label="Allowed" value={allowed} />
          <InlineMetric icon={<Ban className="h-4 w-4" />} label="Denied" value={denied} />
        </div>
        <form className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]" onSubmit={submitFilter}>
          <SelectField
            emptyLabel="All results"
            idPrefix="runtime-decision-filter"
            label="Result"
            name="result"
            options={ringDecisionResults}
            value={String(filters.result ?? "")}
          />
          <Field defaultValue={String(filters.session_id ?? "")} idPrefix="runtime-decision-filter" label="Session" name="session_id" />
          <Field defaultValue={String(filters.agent_id ?? "")} idPrefix="runtime-decision-filter" label="Agent" name="agent_id" />
          <Button className="self-end" type="submit">Filter</Button>
        </form>
        {decisions.length === 0 ? (
          <EmptyState title="No decisions" description="Evaluated runtime actions will appear here." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action</TableHead>
                <TableHead>Result</TableHead>
                <TableHead>Required</TableHead>
                <TableHead>Assigned</TableHead>
                <TableHead>Trust</TableHead>
                <TableHead>Reason</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {decisions.map((decision) => (
                <TableRow data-runtime-ring-decision-row={decision.id} key={decision.id}>
                  <TableCell>
                    <strong>{decision.action_name}</strong>
                    <small className="block text-muted-foreground">{decision.agent_id}</small>
                  </TableCell>
                  <TableCell><StatusBadge status={decision.result} /></TableCell>
                  <TableCell>{decision.required_ring}</TableCell>
                  <TableCell>{decision.assigned_ring}</TableCell>
                  <TableCell>{decision.agent_trust_score}</TableCell>
                  <TableCell>{decision.reason}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function RingRulesPanel({
  onCreate,
  rules
}: {
  onCreate: (payload: Record<string, unknown>) => void;
  rules: RuntimeRingRule[];
}) {
  function submitRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate(runtimeRingRulePayloadFromForm(event.currentTarget));
    event.currentTarget.reset();
  }

  return (
    <Card data-runtime-ring-rules>
      <CardHeader>
        <CardTitle>Ring Rule Editor</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3" data-runtime-ring-rule-form onSubmit={submitRule}>
          <Field idPrefix="runtime-ring-rule" label="Pattern" name="action_pattern" required />
          <SelectField idPrefix="runtime-ring-rule" label="Required Ring" name="required_ring" options={rings} value="2" />
          <Field defaultValue="0" idPrefix="runtime-ring-rule" label="Min Trust" max={1000} min={0} name="min_trust_score" required type="number" />
          <CheckboxField defaultChecked idPrefix="runtime-ring-rule" label="Enabled" name="enabled" />
          <Button type="submit">Create</Button>
        </form>
        {rules.length === 0 ? (
          <EmptyState title="No rules" description="Create a ring override rule." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Pattern</TableHead>
                <TableHead>Ring</TableHead>
                <TableHead>Min Trust</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map((rule) => (
                <TableRow data-runtime-ring-rule-row={rule.id} key={rule.id}>
                  <TableCell><strong>{rule.action_pattern}</strong></TableCell>
                  <TableCell>{rule.required_ring}</TableCell>
                  <TableCell>{rule.min_trust_score}</TableCell>
                  <TableCell><StatusBadge status={rule.enabled ? "enabled" : "disabled"} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function SagasPanel({
  filters,
  onCreate,
  onFilter,
  onSelect,
  sagas,
  selectedSagaId
}: {
  filters: RuntimeParams;
  onCreate: (payload: Record<string, unknown>) => void;
  onFilter: (params: RuntimeParams) => void;
  onSelect: (sagaId: string) => void;
  sagas: RuntimeSaga[];
  selectedSagaId: string | null;
}) {
  function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate(runtimeSagaPayloadFromForm(event.currentTarget));
    event.currentTarget.reset();
  }

  function submitFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter({ status: emptyToNull(formString(event.currentTarget, "status")) });
  }

  return (
    <Card data-runtime-sagas>
      <CardHeader>
        <CardTitle>Saga Builder</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]" data-runtime-saga-form onSubmit={submitCreate}>
          <Field idPrefix="runtime-saga" label="Name" name="name" required />
          <Field idPrefix="runtime-saga" label="Runtime Session" name="runtime_session_id" />
          <Field idPrefix="runtime-saga" label="Correlation" name="correlation_id" />
          <Button className="self-end" type="submit">Create</Button>
        </form>
        <form className="grid gap-3 md:grid-cols-[1fr_auto]" onSubmit={submitFilter}>
          <SelectField
            emptyLabel="All statuses"
            idPrefix="runtime-saga-filter"
            label="Saga Status"
            name="status"
            options={["", "draft", "running", "completed", "failed", "compensated", "cancelled"]}
            value={String(filters.status ?? "")}
          />
          <Button className="self-end" type="submit">Filter</Button>
        </form>
        {sagas.length === 0 ? (
          <EmptyState title="No sagas" description="Create a saga definition." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Saga</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Session</TableHead>
                <TableHead>Correlation</TableHead>
                <TableHead>Detail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sagas.map((saga) => (
                <TableRow data-runtime-saga-row={saga.id} key={saga.id}>
                  <TableCell>
                    <strong>{saga.name}</strong>
                    <small className="block text-muted-foreground">{saga.id}</small>
                  </TableCell>
                  <TableCell><StatusBadge status={saga.status} /></TableCell>
                  <TableCell>{saga.runtime_session_id ?? "unlinked"}</TableCell>
                  <TableCell>{saga.correlation_id ?? "n/a"}</TableCell>
                  <TableCell>
                    <Button
                      disabled={selectedSagaId === saga.id}
                      onClick={() => onSelect(saga.id)}
                      type="button"
                      variant="outline"
                    >
                      Open
                    </Button>
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

function SagaMonitor({
  onAddStep,
  onCancel,
  onExecute,
  saga
}: {
  onAddStep: (sagaId: string, payload: Record<string, unknown>) => void;
  onCancel: (sagaId: string, payload: Record<string, unknown>) => void;
  onExecute: (sagaId: string, payload: Record<string, unknown>) => void;
  saga: RuntimeSaga | null;
}) {
  if (!saga) {
    return (
      <Card data-runtime-saga-monitor>
        <CardHeader><CardTitle>Saga Monitor</CardTitle></CardHeader>
        <CardContent><EmptyState title="No saga selected" description="Create or open a saga." /></CardContent>
      </Card>
    );
  }
  const sagaId = saga.id;
  const steps = saga.steps ?? [];
  const events = saga.events ?? [];
  const nextOrder = nextSagaStepOrder(steps);
  const canAddStep = canAddRuntimeSagaStep(saga);
  const canExecuteSaga = canExecuteRuntimeSaga(saga);
  const canCancelSaga = canCancelRuntimeSaga(saga);

  function submitStep(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canAddStep) {
      return;
    }
    onAddStep(sagaId, runtimeSagaStepPayloadFromForm(event.currentTarget));
    event.currentTarget.reset();
  }

  function submitExecute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canExecuteSaga) {
      return;
    }
    onExecute(sagaId, runtimeSagaExecutePayloadFromForm(event.currentTarget));
  }

  function submitCancel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCancelSaga) {
      return;
    }
    onCancel(sagaId, runtimeSagaCancelPayloadFromForm(event.currentTarget));
    event.currentTarget.reset();
  }

  return (
    <Card data-runtime-saga-monitor={saga.id}>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle>{saga.name}</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">{saga.correlation_id ?? "No correlation"}</p>
          </div>
          <StatusBadge status={saga.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 md:grid-cols-4">
          <Metadata label="Runtime Session" value={saga.runtime_session_id ?? "unlinked"} />
          <Metadata label="Started" value={saga.started_at ?? "not started"} />
          <Metadata label="Finished" value={saga.finished_at ?? "not finished"} />
          <Metadata label="Steps" value={steps.length} />
        </div>
        <form className="grid gap-3 md:grid-cols-4" data-runtime-saga-step-form onSubmit={submitStep}>
          <Field defaultValue={String(nextOrder)} idPrefix="runtime-saga-step" label="Order" min={1} name="step_order" required type="number" />
          <Field idPrefix="runtime-saga-step" label="Step Name" name="name" required />
          <Field idPrefix="runtime-saga-step" label="Action" name="action_name" required />
          <Field idPrefix="runtime-saga-step" label="Target Agent" name="target_agent_id" required />
          <Field idPrefix="runtime-saga-step" label="Capability" name="required_capability" />
          <Field idPrefix="runtime-saga-step" label="Compensation" name="compensation_action" />
          <Field defaultValue="300" idPrefix="runtime-saga-step" label="Timeout" min={1} name="timeout_seconds" required type="number" />
          <Field defaultValue="0" idPrefix="runtime-saga-step" label="Retries" min={0} name="retry_count" required type="number" />
          <Button className="self-end" disabled={!canAddStep} type="submit">Add Step</Button>
        </form>
        <div className="grid gap-3 md:grid-cols-2">
          <form className="grid gap-3" data-runtime-saga-execute-form onSubmit={submitExecute}>
            <Field idPrefix="runtime-saga-execute" label="Failure Actions" name="failure_actions" />
            <Button disabled={!canExecuteSaga} type="submit"><Play className="h-4 w-4" />Execute / Retry</Button>
          </form>
          <form className="grid gap-3" data-runtime-saga-cancel-form onSubmit={submitCancel}>
            <Field idPrefix="runtime-saga-cancel" label="Cancel Reason" name="reason" />
            <Button disabled={!canCancelSaga} type="submit" variant="outline"><Square className="h-4 w-4" />Cancel</Button>
          </form>
        </div>
        {steps.length === 0 ? (
          <EmptyState title="No steps" description="Add an ordered step before execution." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Step</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>Capability</TableHead>
                <TableHead>Compensation</TableHead>
                <TableHead>Activity</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {steps.map((step) => (
                <TableRow data-runtime-saga-step-row={step.id} key={step.id}>
                  <TableCell>
                    <strong>{step.name}</strong>
                    <small className="block text-muted-foreground">{step.action_name}</small>
                  </TableCell>
                  <TableCell><StatusBadge status={step.status} /></TableCell>
                  <TableCell>{step.target_agent_name ?? step.target_agent_id}</TableCell>
                  <TableCell>{step.required_capability ?? "n/a"}</TableCell>
                  <TableCell>{step.compensation_action ?? "none"}</TableCell>
                  <TableCell><SagaActivityEvidence result={step.result} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {events.length === 0 ? (
          <EmptyState title="No events" description="Execution events will appear here." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Event</TableHead>
                <TableHead>Message</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((event) => (
                <TableRow data-runtime-saga-event-row={event.id} key={event.id}>
                  <TableCell>
                    <strong>{event.event_type}</strong>
                    <small className="block text-muted-foreground">{event.created_at}</small>
                  </TableCell>
                  <TableCell>{event.message}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function SagaActivityEvidence({ result }: { result?: Record<string, unknown> }) {
  const workerJobId = optionalText(result?.worker_job_id);
  const idempotencyKey = optionalText(result?.idempotency_key);
  const externalOperationId = optionalText(result?.external_operation_id);
  if (!workerJobId && !idempotencyKey && !externalOperationId) {
    return <span className="text-muted-foreground">pending</span>;
  }
  return (
    <div className="space-y-1 break-all text-xs">
      {workerJobId ? <div><span className="text-muted-foreground">Job</span> {workerJobId}</div> : null}
      {idempotencyKey ? <div><span className="text-muted-foreground">Key</span> {idempotencyKey}</div> : null}
      {externalOperationId ? <div><span className="text-muted-foreground">Op</span> {externalOperationId}</div> : null}
    </div>
  );
}

function SandboxPanel({
  decision,
  onCreate,
  onSelect,
  onTest,
  profiles,
  selectedProfile
}: {
  decision: RuntimeSandboxDecision | null;
  onCreate: (payload: Record<string, unknown>) => void;
  onSelect: (profileId: string) => void;
  onTest: (profileId: string, payload: Record<string, unknown>) => void;
  profiles: RuntimeSandboxProfile[];
  selectedProfile: RuntimeSandboxProfile | null;
}) {
  function submitProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate(runtimeSandboxProfilePayloadFromForm(event.currentTarget));
    event.currentTarget.reset();
  }

  function submitTest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedProfile) {
      onTest(selectedProfile.id, runtimeSandboxTestPayloadFromForm(event.currentTarget));
    }
  }

  return (
    <Card data-runtime-sandbox>
      <CardHeader>
        <CardTitle>Sandbox Profiles</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3 md:grid-cols-3" data-runtime-sandbox-profile-form onSubmit={submitProfile}>
          <Field idPrefix="runtime-sandbox" label="Name" name="name" required />
          <SelectField idPrefix="runtime-sandbox" label="Provider" name="provider_type" options={sandboxProviders} />
          <Field idPrefix="runtime-sandbox" label="Allowed Imports" name="allowed_imports" />
          <Field defaultValue="os, subprocess, socket" idPrefix="runtime-sandbox" label="Blocked Imports" name="blocked_imports" />
          <Field idPrefix="runtime-sandbox" label="Allowed Paths" name="allowed_paths" />
          <Field defaultValue="deny" idPrefix="runtime-sandbox" label="Network Egress" name="network_egress" />
          <Field defaultValue="5" idPrefix="runtime-sandbox" label="Timeout" min={1} name="timeout_seconds" type="number" />
          <Field defaultValue="128" idPrefix="runtime-sandbox" label="Memory MB" min={1} name="memory_mb" type="number" />
          <Button className="self-end" type="submit">Create</Button>
        </form>
        {selectedProfile?.provider_warning ? (
          <p className="feedback-warning px-3 py-2" data-runtime-sandbox-warning>
            {selectedProfile.provider_warning}
          </p>
        ) : null}
        {selectedProfile ? (
          <form className="grid gap-3 md:grid-cols-2" data-runtime-sandbox-test-form onSubmit={submitTest}>
            <Field idPrefix="runtime-sandbox-test" label="Agent ID" name="agent_id" />
            <Field idPrefix="runtime-sandbox-test" label="Action" name="action_name" />
            <TextArea className="md:col-span-2" idPrefix="runtime-sandbox-test" label="Sample Code" name="code" required />
            <Button className="self-end" type="submit">Test</Button>
          </form>
        ) : null}
        {decision ? (
          <div className="rounded-md border p-3" data-runtime-sandbox-decision>
            <strong>{decision.decision}</strong>
            <p className="text-sm text-muted-foreground">{decision.reason}</p>
            {decision.violations.length ? (
              <ul className="mt-2 list-disc pl-5 text-sm">
                {decision.violations.map((violation) => (
                  <li key={`${violation.line}-${violation.column}-${violation.violation_type}`}>
                    {violation.violation_type}: {violation.description}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
        {profiles.length === 0 ? (
          <EmptyState title="No sandbox profiles" description="Create a sandbox profile." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Profile</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Blocked</TableHead>
                <TableHead>Paths</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Detail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {profiles.map((profile) => (
                <TableRow data-runtime-sandbox-profile-row={profile.id} key={profile.id}>
                  <TableCell>
                    <strong>{profile.name}</strong>
                    <small className="block text-muted-foreground">{profile.id}</small>
                  </TableCell>
                  <TableCell><Badge tone="muted">{profile.provider_type}</Badge></TableCell>
                  <TableCell>{profile.blocked_imports.join(", ") || "none"}</TableCell>
                  <TableCell>{profile.allowed_paths.join(", ") || "none"}</TableCell>
                  <TableCell><StatusBadge status={profile.status} /></TableCell>
                  <TableCell>
                    <Button onClick={() => onSelect(profile.id)} type="button" variant="outline">Open</Button>
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

function KillSwitchPanel({
  events,
  onInvalidInput,
  onTrigger
}: {
  events: RuntimeKillSwitchEvent[];
  onInvalidInput: (error: unknown) => void;
  onTrigger: (payload: Record<string, unknown>) => Promise<boolean>;
}) {
  async function submitTrigger(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const succeeded = await onTrigger(runtimeKillSwitchPayloadFromForm(event.currentTarget));
      if (succeeded) {
        event.currentTarget.reset();
      }
    } catch (error) {
      onInvalidInput(error);
    }
  }

  return (
    <Card data-runtime-kill-switch>
      <CardHeader>
        <CardTitle>Kill Switch</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3" data-runtime-kill-switch-form onSubmit={submitTrigger}>
          <SelectField idPrefix="runtime-kill-switch" label="Target Type" name="target_type" options={killSwitchTargets} />
          <Field idPrefix="runtime-kill-switch" label="Target ID" name="target_id" required />
          <Field defaultValue="target" idPrefix="runtime-kill-switch" label="Scope" name="scope" required />
          <Field idPrefix="runtime-kill-switch" label="Reason" name="reason" required />
          <Field
            aria-describedby="runtime-kill-switch-confirmation-help"
            idPrefix="runtime-kill-switch"
            label="Confirmation"
            name="confirmation"
            placeholder="KILL session:rtssn_123"
            required
          />
          <p className="text-xs text-muted-foreground" id="runtime-kill-switch-confirmation-help">
            Type KILL target_type:target_id exactly.
          </p>
          <Button type="submit" variant="destructive">Trigger</Button>
        </form>
        {events.length === 0 ? (
          <EmptyState title="No kill-switch events" description="Triggered events appear here." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Target</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((event) => (
                <TableRow data-runtime-kill-switch-event-row={event.id} key={event.id}>
                  <TableCell>
                    <strong>{event.target_type}</strong>
                    <small className="block text-muted-foreground">{event.target_id}</small>
                  </TableCell>
                  <TableCell>{event.scope}</TableCell>
                  <TableCell>{event.reason}</TableCell>
                  <TableCell><StatusBadge status={event.status} /></TableCell>
                  <TableCell>{event.created_at}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function Field({
  className,
  idPrefix,
  label,
  name,
  ...props
}: {
  className?: string;
  idPrefix: string;
  label: string;
  name: string;
} & InputHTMLAttributes<HTMLInputElement>) {
  const id = `${idPrefix}-${name}`;
  return (
    <div className={cn("grid gap-2", className)}>
      <Label className="text-xs" htmlFor={id}>{label}</Label>
      <Input id={id} name={name} {...props} />
    </div>
  );
}

function TextArea({
  className,
  idPrefix,
  label,
  name,
  ...props
}: {
  className?: string;
  idPrefix: string;
  label: string;
  name: string;
} & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = `${idPrefix}-${name}`;
  return (
    <div className={cn("grid gap-2", className)}>
      <Label className="text-xs" htmlFor={id}>{label}</Label>
      <textarea
        className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm"
        id={id}
        name={name}
        {...props}
      />
    </div>
  );
}

function SelectField({
  className,
  emptyLabel,
  idPrefix,
  label,
  name,
  options,
  value
}: {
  className?: string;
  emptyLabel?: string;
  idPrefix: string;
  label: string;
  name: string;
  options: string[];
  value?: string;
}) {
  const id = `${idPrefix}-${name}`;
  return (
    <div className={cn("grid gap-2", className)}>
      <Label className="text-xs" htmlFor={id}>{label}</Label>
      <select
        className="h-9 rounded-md border border-input bg-background px-3 text-sm"
        defaultValue={value ?? options[0]}
        id={id}
        name={name}
      >
        {options.map((option) => (
          <option key={`${name}-${option || "all"}`} value={option}>
            {option === "" && emptyLabel ? emptyLabel : option}
          </option>
        ))}
      </select>
    </div>
  );
}

function CheckboxField({
  defaultChecked = false,
  idPrefix,
  label,
  name
}: {
  defaultChecked?: boolean;
  idPrefix: string;
  label: string;
  name: string;
}) {
  const id = `${idPrefix}-${name}`;
  return (
    <label className="flex items-center gap-2 self-end text-sm" htmlFor={id}>
      <input defaultChecked={defaultChecked} id={id} name={name} type="checkbox" />
      {label}
    </label>
  );
}

function Metadata({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words text-sm font-medium">{value}</dd>
    </div>
  );
}

function optionalText(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className="rounded-md border bg-muted p-2 text-muted-foreground">{icon}</div>
        <div>
          <div className="text-sm text-muted-foreground">{label}</div>
          <div className="text-2xl font-semibold">{value}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function InlineMetric({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <div className="flex items-center gap-3 rounded-md border p-3">
      <div className="text-muted-foreground">{icon}</div>
      <div>
        <div className="text-sm text-muted-foreground">{label}</div>
        <div className="text-xl font-semibold">{value}</div>
      </div>
    </div>
  );
}

export function runtimeSessionPayloadFromForm(form: HTMLFormElement) {
  return {
    agent_id: formString(form, "agent_id"),
    ring: formNumber(form, "ring", 2),
    sponsor_user_id: emptyToNull(formString(form, "sponsor_user_id")),
    metadata: {}
  };
}

export function runtimeSessionEndPayloadFromForm(form: HTMLFormElement) {
  return { reason: emptyToNull(formString(form, "reason")) };
}

export function runtimeActionPayloadFromForm(form: HTMLFormElement) {
  return {
    action_name: formString(form, "action_name"),
    resource_type: formString(form, "resource_type", "runtime-action"),
    reversibility: formString(form, "reversibility", "none"),
    is_read_only: formBoolean(form, "is_read_only"),
    is_admin: formBoolean(form, "is_admin")
  };
}

export function runtimeRingRulePayloadFromForm(form: HTMLFormElement) {
  return {
    action_pattern: formString(form, "action_pattern"),
    required_ring: formNumber(form, "required_ring", 2),
    min_trust_score: formNumber(form, "min_trust_score", 0),
    enabled: formBoolean(form, "enabled")
  };
}

export function runtimeSagaPayloadFromForm(form: HTMLFormElement) {
  return {
    name: formString(form, "name"),
    runtime_session_id: emptyToNull(formString(form, "runtime_session_id")),
    correlation_id: emptyToNull(formString(form, "correlation_id"))
  };
}

export function runtimeSagaStepPayloadFromForm(form: HTMLFormElement) {
  return {
    step_order: formNumber(form, "step_order", 1),
    name: formString(form, "name"),
    action_name: formString(form, "action_name"),
    target_agent_id: formString(form, "target_agent_id"),
    required_capability: emptyToNull(formString(form, "required_capability")),
    timeout_seconds: formNumber(form, "timeout_seconds", 300),
    retry_count: formNumber(form, "retry_count", 0),
    compensation_action: emptyToNull(formString(form, "compensation_action"))
  };
}

export function runtimeSagaExecutePayloadFromForm(form: HTMLFormElement) {
  return {
    runtime_session_id: emptyToNull(formString(form, "runtime_session_id")),
    failure_actions: splitList(formString(form, "failure_actions"))
  };
}

export function runtimeSagaCancelPayloadFromForm(form: HTMLFormElement) {
  return { reason: emptyToNull(formString(form, "reason")) };
}

export function runtimeSandboxProfilePayloadFromForm(form: HTMLFormElement) {
  const timeout = optionalFormInteger(form, "timeout_seconds");
  const memory = optionalFormInteger(form, "memory_mb");
  const networkEgress = emptyToNull(formString(form, "network_egress"));
  return {
    name: formString(form, "name"),
    provider_type: formString(form, "provider_type", "subprocess"),
    allowed_imports: splitList(formString(form, "allowed_imports")),
    blocked_imports: splitList(formString(form, "blocked_imports")),
    allowed_paths: splitList(formString(form, "allowed_paths")),
    network_policy: networkEgress ? { egress: networkEgress } : {},
    resource_limits: {
      ...(timeout !== null ? { timeout_seconds: timeout } : {}),
      ...(memory !== null ? { memory_mb: memory } : {})
    }
  };
}

export function runtimeSandboxTestPayloadFromForm(form: HTMLFormElement) {
  return {
    code: formString(form, "code"),
    agent_id: emptyToNull(formString(form, "agent_id")),
    action_name: emptyToNull(formString(form, "action_name"))
  };
}

export function runtimeKillSwitchPayloadFromForm(form: HTMLFormElement) {
  const targetType = formString(form, "target_type");
  const targetId = formString(form, "target_id");
  const confirmation = formString(form, "confirmation");
  const expectedConfirmation = killSwitchConfirmationPhrase(targetType, targetId);
  if (confirmation !== expectedConfirmation) {
    throw new Error(`Confirmation must exactly match ${expectedConfirmation}.`);
  }
  return {
    target_type: targetType,
    target_id: targetId,
    scope: formString(form, "scope", "target"),
    reason: formString(form, "reason"),
    confirmation
  };
}

export function killSwitchConfirmationPhrase(targetType: string, targetId: string) {
  return `KILL ${targetType}:${targetId}`;
}

function nextSagaStepOrder(steps: RuntimeSaga["steps"] = []) {
  return steps.reduce((maxOrder, step) => Math.max(maxOrder, Number(step.step_order ?? 0)), 0) + 1;
}

function formString(form: HTMLFormElement, name: string, fallback = "") {
  const value = new FormData(form).get(name);
  return typeof value === "string" ? value.trim() : fallback;
}

function formNumber(form: HTMLFormElement, name: string, fallback: number) {
  return parseRequiredNumberField(formString(form, name), humanizeFieldName(name), {
    emptyFallback: fallback,
    integer: true
  });
}

function optionalFormInteger(form: HTMLFormElement, name: string) {
  return parseOptionalNumberField(formString(form, name), humanizeFieldName(name), {
    integer: true
  });
}

function formBoolean(form: HTMLFormElement, name: string) {
  const value = new FormData(form).get(name);
  return value === "on" || value === "true";
}

function splitList(value: string) {
  return value
    .split(/[,\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function emptyToNull(value: string) {
  const stripped = value.trim();
  return stripped || null;
}

function humanizeFieldName(name: string) {
  return name
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
