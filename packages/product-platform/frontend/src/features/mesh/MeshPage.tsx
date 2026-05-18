import {
  Activity,
  ArrowRight,
  GitBranch,
  Network,
  RefreshCw,
  Route,
  ShieldAlert
} from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import { useAgents, type AgentSummary } from "../../api/agents";
import {
  createProtocolBridge,
  createProtocolBridgeRoute,
  patchProtocolBridge,
  runProtocolBridgeHealthCheck,
  useMeshHandoffs,
  useMeshMessages,
  useMeshMutation,
  useMeshTopology,
  useProtocolBridgeDetail,
  useProtocolBridges,
  type MeshHandoff,
  type MeshMessage,
  type MeshParams,
  type MeshTopology,
  type ProtocolBridge,
  type ProtocolBridgeHealthCheck
} from "../../api/mesh";
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

const routeProtocols = ["a2a", "mcp", "iatp", "acp"];
const bridgeTypes = ["mcp", "a2a", "iatp", "acp", "custom"];
const bridgeStatuses = ["configured", "active", "disabled", "limited", "error"];

export function MeshPage() {
  const [topologyFilters, setTopologyFilters] = useState<MeshParams>({});
  const [messageFilters, setMessageFilters] = useState<MeshParams>({});
  const [handoffFilters, setHandoffFilters] = useState<MeshParams>({});
  const [bridgeFilters, setBridgeFilters] = useState<MeshParams>({});
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [selectedHandoffId, setSelectedHandoffId] = useState<string | null>(null);
  const [selectedBridgeId, setSelectedBridgeId] = useState<string | null>(null);
  const [healthResult, setHealthResult] = useState<ProtocolBridgeHealthCheck | null>(null);
  const { feedback, runWithFeedback } = useActionFeedback();

  const topologyQuery = useMeshTopology(topologyFilters);
  const messagesQuery = useMeshMessages(messageFilters);
  const handoffsQuery = useMeshHandoffs(handoffFilters);
  const bridgesQuery = useProtocolBridges(bridgeFilters);
  const agentsQuery = useAgents();
  const mutation = useMeshMutation();

  const topology = topologyQuery.data ?? { nodes: [], edges: [], message_count: 0 };
  const messages = messagesQuery.data ?? [];
  const handoffs = handoffsQuery.data ?? [];
  const bridges = bridgesQuery.data ?? [];
  const activeBridgeId = selectedBridgeId ?? bridges[0]?.id ?? null;
  const bridgeDetailQuery = useProtocolBridgeDetail(activeBridgeId);
  const selectedBridge =
    bridgeDetailQuery.data ?? bridges.find((bridge) => bridge.id === activeBridgeId) ?? null;
  const selectedMessage = messages.find((item) => item.id === selectedMessageId) ?? messages[0] ?? null;
  const selectedHandoff = handoffs.find((item) => item.id === selectedHandoffId) ?? handoffs[0] ?? null;

  async function runTask(label: string, task: () => Promise<unknown>) {
    await runWithFeedback(() => mutation.mutateAsync(task), {
      errorMessage: `${label} failed`,
      successMessage: label
    });
  }

  return (
    <>
      <PageHeader
        title="Mesh"
        description="Agent mesh topology, message flow, handoffs, and protocol bridge controls."
      />
      <div className="space-y-6 p-6">
        <ActionFeedback feedback={feedback} />
        <QueryErrorSummary
          items={[
            { error: topologyQuery.error, isError: topologyQuery.isError, label: "Topology", onRetry: () => void topologyQuery.refetch() },
            { error: messagesQuery.error, isError: messagesQuery.isError, label: "Messages", onRetry: () => void messagesQuery.refetch() },
            { error: handoffsQuery.error, isError: handoffsQuery.isError, label: "Handoffs", onRetry: () => void handoffsQuery.refetch() },
            { error: bridgesQuery.error, isError: bridgesQuery.isError, label: "Protocol bridges", onRetry: () => void bridgesQuery.refetch() },
            { error: agentsQuery.error, isError: agentsQuery.isError, label: "Agents", onRetry: () => void agentsQuery.refetch() },
            { error: bridgeDetailQuery.error, isError: bridgeDetailQuery.isError, label: "Bridge detail", onRetry: () => void bridgeDetailQuery.refetch() }
          ]}
        />
        <MeshSummary bridges={bridges} handoffs={handoffs} messages={messages} topology={topology} />
        <MeshTopologyPanel
          filters={topologyFilters}
          isLoading={topologyQuery.isLoading}
          onFilter={setTopologyFilters}
          topology={topology}
        />
        <ProtocolBridgesPanel
          agents={agentsQuery.data ?? []}
          bridges={bridges}
          filters={bridgeFilters}
          healthResult={healthResult}
          onCreate={(payload) =>
            runTask("Protocol bridge registered", async () => {
              const bridge = (await createProtocolBridge(payload)) as ProtocolBridge;
              setSelectedBridgeId(bridge.id);
              setHealthResult(null);
              return bridge;
            })
          }
          onFilter={setBridgeFilters}
          onPatch={(bridgeId, payload) =>
            runTask("Protocol bridge updated", () => patchProtocolBridge(bridgeId, payload))
          }
          onRouteCreate={(bridgeId, payload) =>
            runTask("Protocol bridge route added", () => createProtocolBridgeRoute(bridgeId, payload))
          }
          onRunHealth={async (bridgeId) => {
            const result = await runWithFeedback<ProtocolBridgeHealthCheck>(
              () =>
                mutation.mutateAsync(() =>
                  runProtocolBridgeHealthCheck(bridgeId)
                ) as Promise<ProtocolBridgeHealthCheck>,
              {
                errorMessage: "Protocol bridge health check failed",
                successMessage: "Protocol bridge health check completed"
              }
            );
            if (!result) {
              return;
            }
            setHealthResult(result);
          }}
          onSelect={(bridgeId) => {
            setSelectedBridgeId(bridgeId);
            setHealthResult(null);
          }}
          selectedBridge={selectedBridge}
        />
        <div className="grid gap-6 2xl:grid-cols-2">
          <MeshMessagesPanel
            filters={messageFilters}
            messages={messages}
            onFilter={setMessageFilters}
            onSelect={setSelectedMessageId}
            selectedMessage={selectedMessage}
          />
          <MeshHandoffsPanel
            filters={handoffFilters}
            handoffs={handoffs}
            onFilter={setHandoffFilters}
            onSelect={setSelectedHandoffId}
            selectedHandoff={selectedHandoff}
          />
        </div>
      </div>
    </>
  );
}

function MeshSummary({
  bridges,
  handoffs,
  messages,
  topology
}: {
  bridges: ProtocolBridge[];
  handoffs: MeshHandoff[];
  messages: MeshMessage[];
  topology: MeshTopology;
}) {
  const denied = messages.filter((item) => isDenied(item.decision)).length;
  const blocked = handoffs.filter((item) => isDenied(item.status) || isDenied(item.trust_result)).length;
  const limited = bridges.filter((bridge) => bridge.status === "limited").length;

  return (
    <section className="grid gap-4 md:grid-cols-4" data-mesh-summary>
      <MetricCard icon={<Network className="h-4 w-4" />} label="Nodes" value={topology.nodes.length} />
      <MetricCard icon={<Activity className="h-4 w-4" />} label="Messages" value={topology.message_count} />
      <MetricCard icon={<ShieldAlert className="h-4 w-4" />} label="Blocked Flow" value={denied + blocked} />
      <MetricCard icon={<GitBranch className="h-4 w-4" />} label="Limited Bridges" value={limited} />
    </section>
  );
}

function MeshTopologyPanel({
  filters,
  isLoading,
  onFilter,
  topology
}: {
  filters: MeshParams;
  isLoading: boolean;
  onFilter: (params: MeshParams) => void;
  topology: MeshTopology;
}) {
  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter(meshTopologyParamsFromForm(event.currentTarget));
  }

  return (
    <Card data-mesh-topology>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <div>
          <CardTitle>Live Edges</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            {topology.generated_at ? `Generated ${topology.generated_at}` : "Topology refresh pending"}
          </p>
        </div>
        <Badge tone={topology.cached ? "warning" : "default"}>
          {topology.message_count ?? 0} messages
        </Badge>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={onSubmit}>
          <Field compact defaultValue={String(filters.start_time ?? "")} label="Start Time" name="start_time" />
          <Field compact defaultValue={String(filters.end_time ?? "")} label="End Time" name="end_time" />
          <Button className="self-end" type="submit">
            Filter
          </Button>
        </form>
        {topology.nodes.length === 0 && topology.edges.length === 0 ? (
          <EmptyState
            title={isLoading ? "Loading topology" : "No topology"}
            description={isLoading ? "Fetching mesh edges." : "Mesh messages will create nodes and edges."}
          />
        ) : (
          <div className="grid gap-6 xl:grid-cols-[minmax(18rem,0.8fr)_minmax(0,1.2fr)]">
            <section>
              <h3 className="font-semibold">Nodes</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                {topology.nodes.map((node) => (
                  <article
                    className="rounded-md border p-3"
                    data-topology-node={node.agent_id}
                    key={node.agent_id}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <strong>{node.name ?? node.agent_id}</strong>
                        <div className="text-xs text-muted-foreground">{node.agent_id}</div>
                      </div>
                      <StatusBadge status={node.status ?? "unknown"} />
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                      <Badge tone={toneForTrustTier(node.trust_tier ?? "")}>
                        {node.trust_tier ?? "unscored"}
                      </Badge>
                      <Badge tone="muted">{node.message_count ?? 0} messages</Badge>
                    </div>
                  </article>
                ))}
              </div>
            </section>
            <section>
              <h3 className="font-semibold">Edges</h3>
              <div className="mt-3 space-y-3">
                {topology.edges.length === 0 ? (
                  <EmptyState title="No edges" description="No routed traffic for this range." />
                ) : (
                  topology.edges.map((edge) => (
                    <article
                      className="rounded-md border p-4"
                      data-topology-edge={`${edge.source_agent_id}:${edge.target_agent_id}:${edge.protocol}`}
                      key={`${edge.source_agent_id}:${edge.target_agent_id}:${edge.protocol}`}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <strong>{edge.source_agent_id}</strong>
                        <ArrowRight className="h-4 w-4 text-muted-foreground" />
                        <strong>{edge.target_agent_id}</strong>
                        <Badge tone="muted">{edge.protocol}</Badge>
                      </div>
                      <div className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
                        <Metadata label="Volume" value={edge.volume} />
                        <Metadata label="Denied" value={`${edge.denied_count} (${percent(edge.deny_rate)})`} />
                        <Metadata label="Latency" value={`${Math.round(edge.average_latency_ms)} ms avg`} />
                      </div>
                    </article>
                  ))
                )}
              </div>
            </section>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ProtocolBridgesPanel({
  agents,
  bridges,
  filters,
  healthResult,
  onCreate,
  onFilter,
  onPatch,
  onRouteCreate,
  onRunHealth,
  onSelect,
  selectedBridge
}: {
  agents: AgentSummary[];
  bridges: ProtocolBridge[];
  filters: MeshParams;
  healthResult: ProtocolBridgeHealthCheck | null;
  onCreate: (payload: Record<string, unknown>) => void;
  onFilter: (params: MeshParams) => void;
  onPatch: (bridgeId: string, payload: Record<string, unknown>) => void;
  onRouteCreate: (bridgeId: string, payload: Record<string, unknown>) => void;
  onRunHealth: (bridgeId: string) => void;
  onSelect: (bridgeId: string) => void;
  selectedBridge: ProtocolBridge | null;
}) {
  function onCreateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate(protocolBridgePayloadFromForm(event.currentTarget));
  }

  function onFilterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter(protocolBridgeParamsFromForm(event.currentTarget));
  }

  return (
    <Card data-protocol-bridges>
      <CardHeader className="flex flex-row items-center gap-3">
        <Route className="h-5 w-5 text-muted-foreground" />
        <CardTitle>Bridge Control</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3 lg:grid-cols-[1.1fr_0.7fr_1.4fr_1fr_0.7fr_auto]" onSubmit={onCreateSubmit}>
          <Field compact label="Name" name="name" placeholder="MCP Claims Bridge" required />
          <Field compact label="Type" name="bridge_type">
            <BridgeTypeSelect name="bridge_type" />
          </Field>
          <Field compact label="Endpoint" name="endpoint" placeholder="https://mcp.local/rpc" type="url" />
          <Field compact label="Secret ID" name="secret_id" />
          <Field compact label="Status" name="status">
            <BridgeStatusSelect defaultValue="configured" name="status" />
          </Field>
          <Button className="self-end" type="submit">
            Register
          </Button>
        </form>
        <form className="grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={onFilterSubmit}>
          <Field compact label="Bridge Type" name="bridge_type">
            <BridgeTypeSelect defaultValue={String(filters.bridge_type ?? "")} includeAny name="bridge_type" />
          </Field>
          <Field compact label="Bridge Status" name="status">
            <BridgeStatusSelect defaultValue={String(filters.status ?? "")} includeAny name="status" />
          </Field>
          <Button className="self-end" type="submit" variant="outline">
            Filter
          </Button>
        </form>
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
          <div className="overflow-x-auto">
            {bridges.length === 0 ? (
              <EmptyState title="No bridges" description="Register a protocol bridge to manage routes." />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Bridge</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Health</TableHead>
                    <TableHead>Checked</TableHead>
                    <TableHead>Detail</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {bridges.map((bridge) => (
                    <TableRow data-protocol-bridge-row={bridge.id} key={bridge.id}>
                      <TableCell>
                        <strong>{bridge.name}</strong>
                        <div className="text-xs text-muted-foreground">{bridge.bridge_type}</div>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={bridge.status} />
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={bridge.current_health?.status ?? "not checked"} />
                      </TableCell>
                      <TableCell>{bridge.current_health?.checked_at ?? "not checked"}</TableCell>
                      <TableCell>
                        <Button onClick={() => onSelect(bridge.id)} variant="outline">
                          Details
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
          <ProtocolBridgeDetail
            agents={agents}
            bridge={selectedBridge}
            healthResult={healthResult}
            onPatch={onPatch}
            onRouteCreate={onRouteCreate}
            onRunHealth={onRunHealth}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function ProtocolBridgeDetail({
  agents,
  bridge,
  healthResult,
  onPatch,
  onRouteCreate,
  onRunHealth
}: {
  agents: AgentSummary[];
  bridge: ProtocolBridge | null;
  healthResult: ProtocolBridgeHealthCheck | null;
  onPatch: (bridgeId: string, payload: Record<string, unknown>) => void;
  onRouteCreate: (bridgeId: string, payload: Record<string, unknown>) => void;
  onRunHealth: (bridgeId: string) => void;
}) {
  if (!bridge) {
    return <EmptyState title="No bridge selected" description="Register or select a bridge." />;
  }
  const activeBridge = bridge;
  const latestHealth = healthResult?.bridge_id === activeBridge.id ? healthResult : activeBridge.current_health;

  function onPatchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onPatch(activeBridge.id, protocolBridgePatchPayloadFromForm(event.currentTarget));
  }

  function onRouteSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onRouteCreate(activeBridge.id, protocolBridgeRoutePayloadFromForm(event.currentTarget));
  }

  return (
    <section className="rounded-md border p-4" data-protocol-bridge-detail={activeBridge.id}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-muted-foreground">Bridge Detail</div>
          <h3 className="font-semibold">{activeBridge.name}</h3>
        </div>
        <StatusBadge status={activeBridge.status} />
      </div>
      <div
        className="mt-4 feedback-warning"
        data-protocol-bridge-limited-warning
      >
        <strong>Limited runtime</strong>
        <p className="mt-1">
          AgentMesh bridge adapters are placeholder/pass-through implementations, so runtime
          delivery is limited and not reported as healthy.
        </p>
      </div>
      <dl className="mt-4 grid gap-3 text-sm">
        <Metadata label="Type" value={activeBridge.bridge_type} />
        <Metadata label="Endpoint" value={stringConfig(activeBridge, "endpoint") ?? stringConfig(activeBridge, "url") ?? "not configured"} />
        <Metadata label="Routes" value={activeBridge.routes?.length ?? 0} />
      </dl>
      <section className="mt-5" data-protocol-bridge-health-panel>
        <div className="flex items-center justify-between gap-3">
          <h4 className="font-semibold">Health</h4>
          <Button onClick={() => onRunHealth(activeBridge.id)} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Run Check
          </Button>
        </div>
        <div className="mt-3 rounded-md border p-3 text-sm">
          <strong>{latestHealth?.status ?? "not checked"}</strong>
          <p className="mt-1 text-muted-foreground">
            {latestHealth?.message ?? "No health check has been recorded."}
          </p>
        </div>
      </section>
      <form className="mt-5 grid gap-3 md:grid-cols-[1fr_1fr_auto]" onSubmit={onPatchSubmit}>
        <Field compact defaultValue={activeBridge.name} label="Edit Name" name="name" />
        <Field compact label="Edit Status" name="status">
          <BridgeStatusSelect defaultValue={activeBridge.status} name="status" />
        </Field>
        <Button className="self-end" type="submit" variant="outline">
          Save
        </Button>
      </form>
      <section className="mt-5">
        <h4 className="font-semibold">Routes</h4>
        {activeBridge.routes?.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Protocol</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Target</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activeBridge.routes.map((route) => (
                <TableRow data-protocol-bridge-route-row={route.id} key={route.id}>
                  <TableCell>
                    {route.source_protocol} to {route.target_protocol}
                  </TableCell>
                  <TableCell>{route.source_agent_name ?? route.source_agent_id ?? "any"}</TableCell>
                  <TableCell>{route.target_agent_name ?? route.target_agent_id ?? "any"}</TableCell>
                  <TableCell>{route.enabled ? "enabled" : "disabled"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState title="No routes" description="Add a route through this bridge." />
        )}
        <form className="mt-4 grid gap-3 md:grid-cols-2" onSubmit={onRouteSubmit}>
          <Field compact label="Source Protocol" name="source_protocol">
            <RouteProtocolSelect defaultValue="a2a" name="source_protocol" />
          </Field>
          <Field compact label="Target Protocol" name="target_protocol">
            <RouteProtocolSelect defaultValue="mcp" name="target_protocol" />
          </Field>
          <Field compact label="Source Agent" name="source_agent_id">
            <AgentSelect agents={agents} name="source_agent_id" />
          </Field>
          <Field compact label="Target Agent" name="target_agent_id">
            <AgentSelect agents={agents} name="target_agent_id" />
          </Field>
          <Field compact className="md:col-span-2" label="Policy Binding" name="policy_binding_id" />
          <Button className="md:col-span-2" type="submit">
            Add Route
          </Button>
        </form>
      </section>
    </section>
  );
}

function MeshMessagesPanel({
  filters,
  messages,
  onFilter,
  onSelect,
  selectedMessage
}: {
  filters: MeshParams;
  messages: MeshMessage[];
  onFilter: (params: MeshParams) => void;
  onSelect: (messageId: string) => void;
  selectedMessage: MeshMessage | null;
}) {
  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter(meshMessageParamsFromForm(event.currentTarget));
  }

  return (
    <Card data-mesh-messages>
      <CardHeader>
        <CardTitle>Message Feed</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="grid gap-3 md:grid-cols-3" onSubmit={onSubmit}>
          <Field compact defaultValue={String(filters.source_agent_id ?? "")} label="Message Source" name="source_agent_id" />
          <Field compact defaultValue={String(filters.target_agent_id ?? "")} label="Message Target" name="target_agent_id" />
          <Field compact defaultValue={String(filters.protocol ?? "")} label="Protocol" name="protocol" />
          <Field compact defaultValue={String(filters.decision ?? "")} label="Decision" name="decision" />
          <Field compact defaultValue={String(filters.action ?? "")} label="Action" name="action" />
          <Button className="self-end" type="submit">
            Filter
          </Button>
        </form>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
          {messages.length === 0 ? (
            <EmptyState title="No messages" description="Awaiting mesh traffic." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Route</TableHead>
                  <TableHead>Protocol</TableHead>
                  <TableHead>Decision</TableHead>
                  <TableHead>Latency</TableHead>
                  <TableHead>Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {messages.map((item) => (
                  <TableRow data-mesh-message-row={item.id} key={item.id}>
                    <TableCell>
                      <strong>{item.source_agent_name ?? item.source_agent_id}</strong>
                      <div className="text-xs text-muted-foreground">
                        to {item.target_agent_name ?? item.target_agent_id}
                      </div>
                    </TableCell>
                    <TableCell>{item.protocol}</TableCell>
                    <TableCell>
                      <StatusBadge status={item.decision} />
                    </TableCell>
                    <TableCell>{item.latency_ms} ms</TableCell>
                    <TableCell>
                      <Button onClick={() => onSelect(item.id)} variant="outline">
                        Details
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          <MeshMessageDetail message={selectedMessage} />
        </div>
      </CardContent>
    </Card>
  );
}

function MeshMessageDetail({ message }: { message: MeshMessage | null }) {
  if (!message) {
    return <EmptyState title="No message selected" description="Select a message row." />;
  }
  return (
    <section className="rounded-md border p-4" data-mesh-message-detail={message.id}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-muted-foreground">Message Detail</div>
          <h3 className="font-semibold">{message.action}</h3>
        </div>
        <StatusBadge status={message.decision} />
      </div>
      <dl className="mt-4 grid gap-3 text-sm">
        <Metadata label="Route" value={`${message.source_agent_id} to ${message.target_agent_id}`} />
        <Metadata label="Protocol" value={message.protocol} />
        <Metadata label="Correlation" value={message.correlation_id ?? "none"} />
      </dl>
      <pre className="mt-4 max-h-48 overflow-auto rounded-md bg-muted p-3 text-xs">
        {JSON.stringify(message.payload_summary ?? {}, null, 2)}
      </pre>
    </section>
  );
}

function MeshHandoffsPanel({
  filters,
  handoffs,
  onFilter,
  onSelect,
  selectedHandoff
}: {
  filters: MeshParams;
  handoffs: MeshHandoff[];
  onFilter: (params: MeshParams) => void;
  onSelect: (handoffId: string) => void;
  selectedHandoff: MeshHandoff | null;
}) {
  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter(meshHandoffParamsFromForm(event.currentTarget));
  }

  return (
    <Card data-mesh-handoffs>
      <CardHeader>
        <CardTitle>Task Transfers</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]" onSubmit={onSubmit}>
          <Field compact defaultValue={String(filters.source_agent_id ?? "")} label="Handoff Source" name="source_agent_id" />
          <Field compact defaultValue={String(filters.target_agent_id ?? "")} label="Handoff Target" name="target_agent_id" />
          <Field compact defaultValue={String(filters.status ?? "")} label="Status" name="status" />
          <Button className="self-end" type="submit">
            Filter
          </Button>
        </form>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
          {handoffs.length === 0 ? (
            <EmptyState title="No handoffs" description="Awaiting transfer attempts." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Route</TableHead>
                  <TableHead>Task</TableHead>
                  <TableHead>Trust / Policy</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {handoffs.map((item) => (
                  <TableRow data-mesh-handoff-row={item.id} key={item.id}>
                    <TableCell>
                      <strong>{item.source_agent_name ?? item.source_agent_id}</strong>
                      <div className="text-xs text-muted-foreground">
                        to {item.target_agent_name ?? item.target_agent_id}
                      </div>
                    </TableCell>
                    <TableCell>{item.task_type}</TableCell>
                    <TableCell>
                      {item.trust_result} / {item.policy_result}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={item.status} />
                    </TableCell>
                    <TableCell>
                      <Button onClick={() => onSelect(item.id)} variant="outline">
                        Details
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          <MeshHandoffDetail handoff={selectedHandoff} />
        </div>
      </CardContent>
    </Card>
  );
}

function MeshHandoffDetail({ handoff }: { handoff: MeshHandoff | null }) {
  if (!handoff) {
    return <EmptyState title="No handoff selected" description="Select a handoff row." />;
  }
  return (
    <section className="rounded-md border p-4" data-mesh-handoff-detail={handoff.id}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-muted-foreground">Handoff Detail</div>
          <h3 className="font-semibold">{handoff.task_type}</h3>
        </div>
        <StatusBadge status={handoff.status} />
      </div>
      <dl className="mt-4 grid gap-3 text-sm">
        <Metadata label="Route" value={`${handoff.source_agent_id} to ${handoff.target_agent_id}`} />
        <Metadata label="Reason" value={handoff.reason} />
        <Metadata label="Correlation" value={handoff.correlation_id ?? "none"} />
        <Metadata label="Capabilities" value={(handoff.required_capabilities ?? []).join(", ") || "none"} />
      </dl>
      <pre className="mt-4 max-h-48 overflow-auto rounded-md bg-muted p-3 text-xs">
        {JSON.stringify(handoff.metadata ?? {}, null, 2)}
      </pre>
    </section>
  );
}

function Field({
  children,
  className,
  compact,
  label,
  name,
  ...props
}: {
  children?: ReactNode;
  className?: string;
  compact?: boolean;
  label: string;
  name: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <Label className={cn("grid gap-1.5", className)}>
      <span className={cn("font-medium", compact && "text-xs text-muted-foreground")}>{label}</span>
      {children ?? <Input name={name} {...props} />}
    </Label>
  );
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-3 p-5">
        <div>
          <div className="text-sm text-muted-foreground">{label}</div>
          <div className="mt-1 text-2xl font-semibold">{value}</div>
        </div>
        <div className="rounded-md border bg-muted p-2 text-muted-foreground">{icon}</div>
      </CardContent>
    </Card>
  );
}

function Metadata({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-words font-medium">{value}</dd>
    </div>
  );
}

function BridgeTypeSelect({
  defaultValue = "mcp",
  includeAny,
  name
}: {
  defaultValue?: string;
  includeAny?: boolean;
  name: string;
}) {
  return (
    <select
      className="h-10 rounded-md border border-input bg-background px-3 text-sm"
      defaultValue={defaultValue}
      name={name}
    >
      {includeAny ? <option value="">Any</option> : null}
      {bridgeTypes.map((type) => (
        <option key={type} value={type}>
          {type.toUpperCase()}
        </option>
      ))}
    </select>
  );
}

function BridgeStatusSelect({
  defaultValue = "configured",
  includeAny,
  name
}: {
  defaultValue?: string;
  includeAny?: boolean;
  name: string;
}) {
  return (
    <select
      className="h-10 rounded-md border border-input bg-background px-3 text-sm"
      defaultValue={defaultValue}
      name={name}
    >
      {includeAny ? <option value="">Any</option> : null}
      {bridgeStatuses.map((status) => (
        <option key={status} value={status}>
          {status}
        </option>
      ))}
    </select>
  );
}

function RouteProtocolSelect({ defaultValue, name }: { defaultValue: string; name: string }) {
  return (
    <select
      className="h-10 rounded-md border border-input bg-background px-3 text-sm"
      defaultValue={defaultValue}
      name={name}
    >
      {routeProtocols.map((protocol) => (
        <option key={protocol} value={protocol}>
          {protocol.toUpperCase()}
        </option>
      ))}
    </select>
  );
}

function AgentSelect({ agents, name }: { agents: AgentSummary[]; name: string }) {
  return (
    <select className="h-10 rounded-md border border-input bg-background px-3 text-sm" name={name}>
      <option value="">Any agent</option>
      {agents.map((agent) => (
        <option key={agent.id} value={agent.id}>
          {agent.name ?? agent.id}
        </option>
      ))}
    </select>
  );
}

export function meshTopologyParamsFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return compactParams({
    start_time: String(values.start_time ?? ""),
    end_time: String(values.end_time ?? "")
  });
}

export function meshMessageParamsFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return compactParams({
    source_agent_id: String(values.source_agent_id ?? ""),
    target_agent_id: String(values.target_agent_id ?? ""),
    protocol: String(values.protocol ?? ""),
    decision: String(values.decision ?? ""),
    action: String(values.action ?? "")
  });
}

export function meshHandoffParamsFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return compactParams({
    source_agent_id: String(values.source_agent_id ?? ""),
    target_agent_id: String(values.target_agent_id ?? ""),
    status: String(values.status ?? "")
  });
}

export function protocolBridgeParamsFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return compactParams({
    bridge_type: String(values.bridge_type ?? ""),
    status: String(values.status ?? "")
  });
}

export function protocolBridgePayloadFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  const config: Record<string, string> = {};
  const endpoint = String(values.endpoint ?? "").trim();
  const secretId = String(values.secret_id ?? "").trim();
  if (endpoint) {
    config.endpoint = endpoint;
  }
  if (secretId) {
    config.secret_id = secretId;
  }
  return {
    name: String(values.name ?? "").trim(),
    bridge_type: String(values.bridge_type ?? "mcp").trim().toLowerCase(),
    status: String(values.status ?? "configured").trim().toLowerCase(),
    config
  };
}

export function protocolBridgePatchPayloadFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return compactParams({
    name: String(values.name ?? "").trim(),
    status: String(values.status ?? "").trim().toLowerCase()
  });
}

export function protocolBridgeRoutePayloadFromForm(form: HTMLFormElement) {
  const values = Object.fromEntries(new FormData(form));
  return {
    source_protocol: normalizeRouteProtocol(values.source_protocol),
    target_protocol: normalizeRouteProtocol(values.target_protocol),
    source_agent_id: blankToNull(values.source_agent_id),
    target_agent_id: blankToNull(values.target_agent_id),
    policy_binding_id: blankToNull(values.policy_binding_id),
    enabled: true
  };
}

function compactParams(params: MeshParams) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}

function blankToNull(value: FormDataEntryValue | undefined) {
  const text = String(value ?? "").trim();
  return text || null;
}

function normalizeRouteProtocol(value: FormDataEntryValue | undefined) {
  const protocol = String(value ?? "").trim().toLowerCase();
  if (!routeProtocols.includes(protocol)) {
    throw new Error("Unsupported route protocol.");
  }
  return protocol;
}

function stringConfig(bridge: ProtocolBridge, key: string) {
  const value = bridge.config?.[key];
  return typeof value === "string" ? value : null;
}

function percent(value: number) {
  return `${Math.round(Number(value ?? 0) * 100)}%`;
}

function isDenied(value: string) {
  const normalized = value.toLowerCase();
  return ["deny", "denied", "blocked", "escalate", "escalated"].includes(normalized);
}

function toneForTrustTier(tier: string): "default" | "success" | "warning" | "danger" | "muted" {
  if (tier === "verified_partner" || tier === "trusted") {
    return "success";
  }
  if (tier === "standard") {
    return "default";
  }
  if (tier === "probationary") {
    return "warning";
  }
  if (tier === "untrusted") {
    return "danger";
  }
  return "muted";
}
