import { KeyRound, Play, RotateCcw, Search, ShieldCheck, UserCheck } from "lucide-react";
import { useState, type FormEvent, type InputHTMLAttributes } from "react";

import {
  activateAgent,
  approveAgent,
  createAgentRegistrationDraft,
  issueAgentCredential,
  rotateCredential,
  runLifecycleAction,
  runOrphanDetection,
  revokeCredential,
  useAgentAudit,
  useAgentCredentials,
  useAgentDetail,
  useAgentMutation,
  useAgentTimeline,
  useAgents,
  useExpiringCredentials,
  type AgentAuditEvent,
  type AgentCredential,
  type AgentDetail,
  type AgentLifecycleEvent,
  type AgentListParams,
  type AgentSummary
} from "../../api/agents";
import { useDetailDrawer } from "../../app/drawerContext";
import { PageHeader } from "../../components/layout/PageHeader";
import { EmptyState } from "../../components/shared/EmptyState";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { cn } from "../../lib/utils";

const registrationSteps = [
  "Agent Details",
  "Runtime And Framework",
  "Identity",
  "Capabilities",
  "Policies",
  "Bootstrap"
];

const detailTabs = [
  "Overview",
  "Identity",
  "Credentials",
  "Lifecycle",
  "Audit",
  "Runtime",
  "Policies",
  "Trust",
  "Integrations"
];

export function AgentsPage() {
  const [filters, setFilters] = useState<AgentListParams>({ sort: "-last_heartbeat" });
  const [selectedAgentId, setSelectedAgentId] = useState(() => readAgentIdFromUrl());
  const [activeTab, setActiveTab] = useState("Overview");
  const [message, setMessage] = useState<string | null>(null);

  const agentsQuery = useAgents(filters);
  const agents = agentsQuery.data ?? [];
  const activeAgentId = selectedAgentId ?? agents[0]?.id ?? null;
  const detailQuery = useAgentDetail(activeAgentId);
  const timelineQuery = useAgentTimeline(activeAgentId);
  const auditQuery = useAgentAudit(activeAgentId);
  const credentialsQuery = useAgentCredentials(activeAgentId);
  const expiringQuery = useExpiringCredentials();
  const mutation = useAgentMutation();

  function selectAgent(agentId: string) {
    setSelectedAgentId(agentId);
    const url = new URL(window.location.href);
    url.searchParams.set("agent_id", agentId);
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}`);
  }

  async function handleRegistrationSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const draft = (await mutation.mutateAsync(() =>
      createAgentRegistrationDraft({
        name: formString(form, "name"),
        description: formString(form, "description"),
        framework: formString(form, "framework"),
        runtime_type: formString(form, "runtime_type"),
        endpoint_url: formString(form, "endpoint_url"),
        owner_user_id: formString(form, "owner_user_id"),
        sponsor_user_id: formString(form, "sponsor_user_id"),
        capabilities: [
          {
            capability_name: formString(form, "capability_name"),
            resource_type: formString(form, "resource_type")
          }
        ].filter((capability) => capability.capability_name),
        policy_selections: formString(form, "policy_pack")
          ? [{ policy_pack: formString(form, "policy_pack") }]
          : []
      })
    )) as AgentDetail | AgentSummary;
    const id = "id" in draft ? String(draft.id) : "draft";
    setSelectedAgentId(id);
    setMessage(`Registration draft ${id} created`);
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setFilters({
      status: formString(form, "status"),
      capability: formString(form, "capability"),
      framework: formString(form, "framework"),
      sort: formString(form, "sort") || "-last_heartbeat"
    });
  }

  async function runTask(label: string, task: () => Promise<unknown>) {
    await mutation.mutateAsync(task);
    setMessage(label);
  }

  return (
    <>
      <PageHeader
        title="Agents"
        description="Register, inspect, operate, and credential governed agents."
      />
      <div className="space-y-6 p-6">
        {message ? (
          <div className="feedback-success" role="status">
            {message}
          </div>
        ) : null}
        <AgentRegistrationWizard onSubmit={handleRegistrationSubmit} isPending={mutation.isPending} />
        <AgentInventory
          agents={agents}
          isLoading={agentsQuery.isLoading}
          onFilter={applyFilters}
          onSelect={selectAgent}
          selectedAgentId={activeAgentId}
        />
        <LifecycleOverview agents={agents} onSelect={selectAgent} />
        <AgentOperations
          activeAgentId={activeAgentId}
          agents={agents}
          credentials={credentialsQuery.data ?? []}
          detail={detailQuery.data ?? null}
          expiringCredentials={expiringQuery.data ?? []}
          isLoading={detailQuery.isLoading}
          onRunTask={runTask}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          timeline={timelineQuery.data ?? detailQuery.data?.lifecycle_events ?? []}
          auditEvents={auditQuery.data ?? detailQuery.data?.auditEvents ?? []}
        />
      </div>
    </>
  );
}

function AgentRegistrationWizard({
  isPending,
  onSubmit
}: {
  isPending: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="rounded-lg border bg-card p-5" data-agent-registration-form>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Register Agent</h2>
          <p className="text-sm text-muted-foreground">
            Draft identity, capabilities, policies, and bootstrap material.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {registrationSteps.map((step, index) => (
            <Badge key={step} tone={index === 0 ? "success" : "muted"}>
              {step}
            </Badge>
          ))}
        </div>
      </div>
      <form className="mt-5 grid gap-4 md:grid-cols-4" onSubmit={onSubmit}>
        <Field label="Name" name="name" required defaultValue="Claims Assistant" />
        <Field label="Owner" name="owner_user_id" required defaultValue="owner_1" />
        <Field label="Sponsor" name="sponsor_user_id" required defaultValue="sponsor_1" />
        <SelectField
          label="Framework"
          name="framework"
          options={["langgraph", "crewai", "autogen", "custom"]}
        />
        <SelectField
          label="Runtime"
          name="runtime_type"
          options={["service", "worker", "workflow", "desktop"]}
        />
        <Field label="Endpoint" name="endpoint_url" defaultValue="https://agent.example.test" />
        <Field label="Capability" name="capability_name" defaultValue="claims:read" />
        <Field label="Resource" name="resource_type" defaultValue="claim" />
        <Field className="md:col-span-2" label="Policy pack" name="policy_pack" defaultValue="baseline" />
        <Field
          className="md:col-span-2"
          label="Description"
          name="description"
          defaultValue="Governed agent registration draft"
        />
        <div className="flex items-end">
          <Button disabled={isPending} type="submit">
            <ShieldCheck className="h-4 w-4" />
            Create draft
          </Button>
        </div>
      </form>
    </section>
  );
}

function LifecycleOverview({
  agents,
  onSelect
}: {
  agents: AgentSummary[];
  onSelect: (agentId: string) => void;
}) {
  const pending = agents.filter((agent) => agent.status === "pending_approval");
  const active = agents.filter((agent) => agent.status === "active");
  const orphanCandidates = agents.filter((agent) => agent.status.includes("orphan"));

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Lifecycle Workspace</h2>
          <p className="text-sm text-muted-foreground">
            Approval queue, operational funnel, and orphan candidates.
          </p>
        </div>
        <div className="flex flex-wrap gap-2" data-lifecycle-funnel>
          <Badge tone="warning">{pending.length} pending</Badge>
          <Badge tone="success">{active.length} active</Badge>
          <Badge tone="danger">{orphanCandidates.length} orphan</Badge>
        </div>
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border p-4" data-approval-queue>
          <h3 className="font-semibold">Approval Queue</h3>
          {pending.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">No pending approvals</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {pending.map((agent) => (
                <li className="flex items-center justify-between gap-3 text-sm" key={agent.id}>
                  <span>{agent.name}</span>
                  <Button onClick={() => onSelect(agent.id)} type="button" variant="outline">
                    Open
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-lg border p-4" data-orphan-candidates>
          <h3 className="font-semibold">Orphan Candidates</h3>
          {orphanCandidates.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">No orphan candidates</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {orphanCandidates.map((agent) => (
                <li className="flex items-center justify-between gap-3 text-sm" key={agent.id}>
                  <span>{agent.name}</span>
                  <a className="font-medium text-primary" href={`/agents?agent_id=${agent.id}`}>
                    Detail
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

function AgentInventory({
  agents,
  isLoading,
  onFilter,
  onSelect,
  selectedAgentId
}: {
  agents: AgentSummary[];
  isLoading: boolean;
  onFilter: (event: FormEvent<HTMLFormElement>) => void;
  onSelect: (agentId: string) => void;
  selectedAgentId: string | null;
}) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Inventory</h2>
          <p className="text-sm text-muted-foreground">
            Filter registered agents by governance state, capability, and framework.
          </p>
        </div>
        <form className="flex flex-wrap items-end gap-3" onSubmit={onFilter}>
          <Field compact label="Status" name="status" placeholder="active" />
          <Field compact label="Capability" name="capability" placeholder="claims:read" />
          <SelectField compact label="Sort" name="sort" options={["-last_heartbeat", "name", "status"]} />
          <Button type="submit" variant="outline">
            <Search className="h-4 w-4" />
            Filter
          </Button>
        </form>
      </div>
      <div className="mt-5 overflow-x-auto">
        {isLoading ? (
          <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
            Loading agents
          </div>
        ) : agents.length === 0 ? (
          <EmptyState
            title="No agents registered"
            description="Register Agent to create the first governed registry record."
          />
        ) : (
          <table className="w-full min-w-[64rem] text-sm">
            <thead className="border-b text-left text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">Name</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Framework</th>
                <th className="py-2 pr-3 font-medium">Owner</th>
                <th className="py-2 pr-3 font-medium">Trust</th>
                <th className="py-2 pr-3 font-medium">Credential</th>
                <th className="py-2 pr-3 font-medium">Heartbeat</th>
                <th className="py-2 pr-3 font-medium">Capabilities</th>
                <th className="py-2 pr-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr
                  className={cn(
                    "border-b last:border-b-0",
                    selectedAgentId === agent.id ? "bg-accent/50" : ""
                  )}
                  data-agent-row={agent.id}
                  key={agent.id}
                >
                  <td className="py-3 pr-3 font-medium">{agent.name}</td>
                  <td className="py-3 pr-3">
                    <StatusBadge status={agent.status} />
                  </td>
                  <td className="py-3 pr-3">{agent.framework ?? "n/a"}</td>
                  <td className="py-3 pr-3">{agent.owner_user_id ?? "n/a"}</td>
                  <td className="py-3 pr-3">{agent.trust_tier ?? agent.trust_score ?? "n/a"}</td>
                  <td className="py-3 pr-3">{agent.credential_status ?? "pending"}</td>
                  <td className="py-3 pr-3">{agent.last_heartbeat_at ?? "n/a"}</td>
                  <td className="py-3 pr-3">{agent.capability_count ?? 0}</td>
                  <td className="py-3 pr-3">
                    <div className="flex flex-wrap gap-2">
                      <Button onClick={() => onSelect(agent.id)} type="button" variant="outline">
                        Open
                      </Button>
                      <Button disabled type="button" variant="ghost">
                        Suspend
                      </Button>
                      <Button disabled type="button" variant="ghost">
                        Rotate
                      </Button>
                      <Button disabled type="button" variant="ghost">
                        Decommission
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

function AgentOperations({
  activeAgentId,
  activeTab,
  agents,
  auditEvents,
  credentials,
  detail,
  expiringCredentials,
  isLoading,
  onRunTask,
  setActiveTab,
  timeline
}: {
  activeAgentId: string | null;
  activeTab: string;
  agents: AgentSummary[];
  auditEvents: AgentAuditEvent[];
  credentials: AgentCredential[];
  detail: AgentDetail | null;
  expiringCredentials: AgentCredential[];
  isLoading: boolean;
  onRunTask: (label: string, task: () => Promise<unknown>) => Promise<void>;
  setActiveTab: (tab: string) => void;
  timeline: AgentLifecycleEvent[];
}) {
  if (!activeAgentId) {
    return (
      <section className="rounded-lg border bg-card p-5">
        <EmptyState
          title="Select an agent"
          description="Inventory details, lifecycle actions, and credentials appear after selection."
        />
      </section>
    );
  }

  const summary = detail?.summary ?? agents.find((agent) => agent.id === activeAgentId) ?? null;

  return (
    <section className="rounded-lg border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{summary?.name ?? activeAgentId}</h2>
          <p className="text-sm text-muted-foreground">
            Identity, lifecycle, credentials, runtime context, and audit trail.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => onRunTask("Agent approved", () => approveAgent(activeAgentId))}
            type="button"
            variant="outline"
          >
            <UserCheck className="h-4 w-4" />
            Approve
          </Button>
          <Button
            onClick={() => onRunTask("Agent activated", () => activateAgent(activeAgentId))}
            type="button"
            variant="outline"
          >
            <Play className="h-4 w-4" />
            Activate
          </Button>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2" role="tablist">
        {detailTabs.map((tab) => (
          <button
            className={cn(
              "rounded-md px-3 py-2 text-sm font-medium",
              activeTab === tab ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
            )}
            key={tab}
            onClick={() => setActiveTab(tab)}
            role="tab"
            type="button"
          >
            {tab}
          </button>
        ))}
      </div>
      <div className="mt-5">
        {isLoading ? (
          <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
            Loading agent detail
          </div>
        ) : (
          <AgentDetailTab
            activeAgentId={activeAgentId}
            activeTab={activeTab}
            auditEvents={auditEvents}
            credentials={credentials}
            detail={detail}
            expiringCredentials={expiringCredentials}
            onRunTask={onRunTask}
            summary={summary}
            timeline={timeline}
          />
        )}
      </div>
    </section>
  );
}

function AgentDetailTab({
  activeAgentId,
  activeTab,
  auditEvents,
  credentials,
  detail,
  expiringCredentials,
  onRunTask,
  summary,
  timeline
}: {
  activeAgentId: string;
  activeTab: string;
  auditEvents: AgentAuditEvent[];
  credentials: AgentCredential[];
  detail: AgentDetail | null;
  expiringCredentials: AgentCredential[];
  onRunTask: (label: string, task: () => Promise<unknown>) => Promise<void>;
  summary: AgentSummary | null;
  timeline: AgentLifecycleEvent[];
}) {
  if (activeTab === "Identity") {
    return <IdentityTab detail={detail} />;
  }
  if (activeTab === "Credentials") {
    return (
      <CredentialsTab
        activeAgentId={activeAgentId}
        credentials={credentials}
        expiringCredentials={expiringCredentials}
        onRunTask={onRunTask}
      />
    );
  }
  if (activeTab === "Lifecycle") {
    return <LifecycleTab activeAgentId={activeAgentId} onRunTask={onRunTask} timeline={timeline} />;
  }
  if (activeTab === "Audit") {
    return <AuditTab auditEvents={auditEvents} />;
  }
  if (activeTab === "Runtime") {
    return (
      <PlaceholderTab
        title="Runtime"
        description="Runtime sessions, ring decisions, and sandbox events are linked from this agent."
        href="/runtime"
      />
    );
  }
  if (activeTab === "Policies" || activeTab === "Trust" || activeTab === "Integrations") {
    return (
      <PlaceholderTab
        title={activeTab}
        description={`${activeTab} data is connected as its dedicated product area is migrated.`}
        href={`/${activeTab.toLowerCase()}`}
      />
    );
  }
  return <OverviewTab detail={detail} summary={summary} />;
}

function OverviewTab({ detail, summary }: { detail: AgentDetail | null; summary: AgentSummary | null }) {
  const capabilities = detail?.capabilities ?? [];
  return (
    <div className="grid gap-4 md:grid-cols-3" data-agent-overview>
      <Metric label="Status" value={summary?.status ?? "unknown"} />
      <Metric label="Owner" value={summary?.owner_user_id ?? "n/a"} />
      <Metric label="Sponsor" value={summary?.sponsor_user_id ?? "n/a"} />
      <Metric label="Framework" value={summary?.framework ?? "n/a"} />
      <Metric label="Credential" value={summary?.credential_status ?? "pending"} />
      <Metric label="Last heartbeat" value={summary?.last_heartbeat_at ?? "n/a"} />
      <div className="rounded-lg border p-4 md:col-span-3">
        <h3 className="font-semibold">Capabilities</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {capabilities.length === 0 ? (
            <span className="text-sm text-muted-foreground">No capabilities requested</span>
          ) : (
            capabilities.map((capability) => (
              <Badge key={capability.capability_name} tone="muted">
                {capability.capability_name}
              </Badge>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function IdentityTab({ detail }: { detail: AgentDetail | null }) {
  const identity = detail?.identity;
  return (
    <div className="grid gap-4 md:grid-cols-2" data-agent-identity>
      <Metric label="DID" value={identity?.did ?? "Not issued"} />
      <Metric label="Public key fingerprint" value={identity?.public_key_fingerprint ?? "n/a"} />
      <Metric label="Key type" value={identity?.key_type ?? "n/a"} />
      <Metric label="Identity status" value={identity?.identity_status ?? "n/a"} />
    </div>
  );
}

function LifecycleTab({
  activeAgentId,
  onRunTask,
  timeline
}: {
  activeAgentId: string;
  onRunTask: (label: string, task: () => Promise<unknown>) => Promise<void>;
  timeline: AgentLifecycleEvent[];
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-[22rem_1fr]" data-agent-lifecycle>
      <div className="rounded-lg border p-4">
        <h3 className="font-semibold">Lifecycle Actions</h3>
        <form
          className="mt-4 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            const reason = formString(new FormData(event.currentTarget), "reason");
            void onRunTask("Agent suspended", () =>
              runLifecycleAction(activeAgentId, "suspend", { reason })
            );
          }}
        >
          <Label htmlFor="lifecycle-reason">Reason</Label>
          <Input id="lifecycle-reason" name="reason" required placeholder="Change request" />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="outline">
              Suspend
            </Button>
            <Button
              onClick={() =>
                onRunTask("Orphan detection queued", () => runOrphanDetection())
              }
              type="button"
              variant="outline"
            >
              <Search className="h-4 w-4" />
              Run orphan detection
            </Button>
          </div>
        </form>
      </div>
      <div className="rounded-lg border p-4">
        <h3 className="font-semibold">Timeline</h3>
        {timeline.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">No lifecycle events yet</p>
        ) : (
          <ol className="mt-3 space-y-3">
            {timeline.map((event) => (
              <li className="rounded-md bg-muted/50 p-3 text-sm" key={event.id}>
                <div className="font-medium">
                  {event.previous_state ?? "n/a"} {" -> "} {event.next_state ?? "n/a"}
                </div>
                <div className="text-muted-foreground">
                  {event.reason ?? "No reason"} {event.created_at ? `at ${event.created_at}` : ""}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

function CredentialsTab({
  activeAgentId,
  credentials,
  expiringCredentials,
  onRunTask
}: {
  activeAgentId: string;
  credentials: AgentCredential[];
  expiringCredentials: AgentCredential[];
  onRunTask: (label: string, task: () => Promise<unknown>) => Promise<void>;
}) {
  return (
    <div className="space-y-4" data-agent-credentials-table>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">Credentials</h3>
          <p className="text-sm text-muted-foreground">
            Issue, rotate, revoke, and review credential scope metadata.
          </p>
        </div>
        <Button
          onClick={() =>
            onRunTask("Credential issued", () =>
              issueAgentCredential(activeAgentId, { scopes: [{ scope: "claims:read" }] })
            )
          }
          type="button"
          variant="outline"
        >
          <KeyRound className="h-4 w-4" />
          Issue
        </Button>
      </div>
      {credentials.length === 0 ? (
        <EmptyState title="No credentials" description="Issue a credential to activate access." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[48rem] text-sm">
            <thead className="border-b text-left text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">Credential</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Issuer</th>
                <th className="py-2 pr-3 font-medium">Expires</th>
                <th className="py-2 pr-3 font-medium">Scopes</th>
                <th className="py-2 pr-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {credentials.map((credential) => (
                <tr className="border-b last:border-b-0" key={credential.id}>
                  <td className="py-3 pr-3 font-medium">{credential.id}</td>
                  <td className="py-3 pr-3">
                    <StatusBadge status={credential.status} />
                  </td>
                  <td className="py-3 pr-3">{credential.issuer ?? "n/a"}</td>
                  <td className="py-3 pr-3">{credential.expires_at ?? "n/a"}</td>
                  <td className="py-3 pr-3">{scopeSummary(credential.scopes)}</td>
                  <td className="py-3 pr-3">
                    <div className="flex flex-wrap gap-2">
                      <Button
                        onClick={() =>
                          onRunTask("Credential rotated", () =>
                            rotateCredential(credential.id, { reason: "scheduled" })
                          )
                        }
                        type="button"
                        variant="outline"
                      >
                        <RotateCcw className="h-4 w-4" />
                        Rotate
                      </Button>
                      <form
                        className="flex gap-2"
                        onSubmit={(event) => {
                          event.preventDefault();
                          const reason = formString(new FormData(event.currentTarget), "reason");
                          void onRunTask("Credential revoked", () =>
                            revokeCredential(credential.id, { reason })
                          );
                        }}
                      >
                        <Input className="w-32" name="reason" required placeholder="Reason" />
                        <Button type="submit" variant="outline">
                          Revoke
                        </Button>
                      </form>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="rounded-lg border p-4">
        <h3 className="font-semibold">Rotation Queue</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {expiringCredentials.length === 0 ? (
            <span className="text-sm text-muted-foreground">No credentials expiring soon</span>
          ) : (
            expiringCredentials.map((credential) => (
              <Badge key={credential.id} tone="warning">
                {credential.id} {credential.expires_at}
              </Badge>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function AuditTab({ auditEvents }: { auditEvents: AgentAuditEvent[] }) {
  const drawer = useDetailDrawer();
  return (
    <div className="space-y-3" data-agent-audit-events>
      {auditEvents.length === 0 ? (
        <EmptyState title="No audit events" description="Lifecycle and credential events appear here." />
      ) : (
        auditEvents.map((event) => (
          <button
            className="flex w-full items-center justify-between rounded-lg border p-4 text-left text-sm hover:bg-accent"
            data-related-event-id={event.id}
            key={event.id}
            onClick={() => void drawer.openAuditEvent(event.id)}
            type="button"
          >
            <span>
              <span className="block font-medium">{event.event_type}</span>
              <span className="block text-muted-foreground">{event.created_at ?? event.id}</span>
            </span>
            <StatusBadge status={event.severity ?? "info"} />
          </button>
        ))
      )}
    </div>
  );
}

function PlaceholderTab({
  description,
  href,
  title
}: {
  description: string;
  href: string;
  title: string;
}) {
  return (
    <div className="rounded-lg border p-4" data-agent-runtime-tab={title === "Runtime" ? true : undefined}>
      <h3 className="font-semibold">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      <a className="mt-3 inline-block text-sm font-medium text-primary" data-route={href} href={href}>
        Open {title}
      </a>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border p-4">
      <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
      <div className="mt-2 break-words text-sm font-medium">{value}</div>
    </div>
  );
}

function Field({
  className,
  compact,
  label,
  name,
  ...props
}: {
  className?: string;
  compact?: boolean;
  label: string;
  name: string;
} & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={cn("space-y-1", compact ? "w-36" : "", className)}>
      <Label htmlFor={name}>{label}</Label>
      <Input id={name} name={name} {...props} />
    </div>
  );
}

function SelectField({
  compact,
  label,
  name,
  options
}: {
  compact?: boolean;
  label: string;
  name: string;
  options: string[];
}) {
  return (
    <div className={cn("space-y-1", compact ? "w-40" : "")}>
      <Label htmlFor={name}>{label}</Label>
      <select
        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        id={name}
        name={name}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}

function formString(form: FormData, key: string) {
  return String(form.get(key) ?? "").trim();
}

function readAgentIdFromUrl() {
  if (typeof window === "undefined") {
    return null;
  }
  return new URLSearchParams(window.location.search).get("agent_id");
}

function scopeSummary(scopes: AgentCredential["scopes"]) {
  if (!scopes || scopes.length === 0) {
    return "n/a";
  }
  return scopes.map((scope) => scope.scope).join(", ");
}
