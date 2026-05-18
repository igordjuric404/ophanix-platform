import {
  CheckCircle2,
  KeyRound,
  Radar,
  RefreshCw,
  Server,
  ShieldAlert
} from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import type { TenantContext } from "../../api/client";
import {
  acceptMcpFindingRisk,
  approveMcpApproval,
  createMcpProxyCall,
  createMcpRateLimit,
  createMcpServer,
  denyMcpApproval,
  discoverMcpServerTools,
  markMcpFindingFalsePositive,
  resolveMcpFinding,
  runMcpSecurityScan,
  useMcpApprovals,
  useMcpFindings,
  useMcpMutation,
  useMcpRateLimits,
  useMcpScans,
  useMcpServers,
  useMcpToolDetail,
  useMcpTools,
  useMcpTraffic,
  type McpApproval,
  type McpFinding,
  type McpParams,
  type McpRateLimit,
  type McpScanRun,
  type McpServer,
  type McpTool,
  type McpToolCall
} from "../../api/mcp";
import { PageHeader } from "../../components/layout/PageHeader";
import {
  ActionFeedback,
  actionErrorMessage,
  useActionFeedback
} from "../../components/shared/ActionFeedback";
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
import { parseJsonObjectField } from "../../lib/forms";
import { cn } from "../../lib/utils";

const authTypes = ["none", "api_key", "bearer", "oauth", "mtls", "custom"];
const serverStatuses = ["registered", "active", "disabled", "error"];
const findingStatuses = ["", "open", "accepted_risk", "resolved", "false_positive"];
const findingSeverities = ["", "critical", "warning", "info"];
const trafficDecisions = ["", "allowed", "denied", "escalated"];
const rateLimitTargets = ["agent", "mcp-server", "mcp-tool"];

export function McpPage() {
  const [findingFilters, setFindingFilters] = useState<McpParams>({});
  const [trafficFilters, setTrafficFilters] = useState<McpParams>({});
  const [approvalFilters, setApprovalFilters] = useState<McpParams>({ status: "pending" });
  const [selectedToolId, setSelectedToolId] = useState<string | null>(null);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const { feedback, runWithFeedback, setError } = useActionFeedback();

  const serversQuery = useMcpServers();
  const toolsQuery = useMcpTools();
  const scansQuery = useMcpScans();
  const findingsQuery = useMcpFindings(findingFilters);
  const trafficQuery = useMcpTraffic(trafficFilters);
  const approvalsQuery = useMcpApprovals(approvalFilters);
  const rateLimitsQuery = useMcpRateLimits();
  const mutation = useMcpMutation();

  const servers = serversQuery.data ?? [];
  const tools = toolsQuery.data ?? [];
  const scans = scansQuery.data ?? [];
  const findings = findingsQuery.data ?? [];
  const traffic = trafficQuery.data ?? [];
  const approvals = approvalsQuery.data ?? [];
  const rateLimits = rateLimitsQuery.data ?? [];
  const activeToolId = selectedToolId ?? tools[0]?.id ?? null;
  const selectedToolQuery = useMcpToolDetail(activeToolId);
  const selectedTool = selectedToolQuery.data ?? tools.find((tool) => tool.id === activeToolId) ?? null;
  const selectedFinding =
    findings.find((finding) => finding.id === selectedFindingId) ?? findings[0] ?? null;

  async function runTask(label: string, task: (tenantContext: TenantContext) => Promise<unknown>) {
    await runWithFeedback(() => mutation.mutateAsync(task), {
      errorMessage: `${label} failed`,
      successMessage: label
    });
  }

  return (
    <>
      <PageHeader
        title="MCP Security"
        description="MCP server registry, tool discovery, security scans, proxy approvals, and rate limits."
      />
      <div className="space-y-6 p-6">
        <ActionFeedback feedback={feedback} />
        <QueryErrorSummary
          items={[
            { error: serversQuery.error, isError: serversQuery.isError, label: "MCP servers", onRetry: () => void serversQuery.refetch() },
            { error: toolsQuery.error, isError: toolsQuery.isError, label: "MCP tools", onRetry: () => void toolsQuery.refetch() },
            { error: scansQuery.error, isError: scansQuery.isError, label: "MCP scans", onRetry: () => void scansQuery.refetch() },
            { error: findingsQuery.error, isError: findingsQuery.isError, label: "MCP findings", onRetry: () => void findingsQuery.refetch() },
            { error: trafficQuery.error, isError: trafficQuery.isError, label: "MCP traffic", onRetry: () => void trafficQuery.refetch() },
            { error: approvalsQuery.error, isError: approvalsQuery.isError, label: "MCP approvals", onRetry: () => void approvalsQuery.refetch() },
            { error: rateLimitsQuery.error, isError: rateLimitsQuery.isError, label: "MCP rate limits", onRetry: () => void rateLimitsQuery.refetch() },
            { error: selectedToolQuery.error, isError: selectedToolQuery.isError, label: "MCP tool detail", onRetry: () => void selectedToolQuery.refetch() }
          ]}
        />
        <McpSummary approvals={approvals} findings={findings} servers={servers} tools={tools} />
        <ServerRegistryPanel
          isLoading={serversQuery.isLoading}
          onCreate={(payload) =>
            runTask("MCP server registered", (tenantContext) =>
              createMcpServer(payload, tenantContext)
            )
          }
          onDiscover={(serverId) =>
            runTask("Tool discovery completed", (tenantContext) =>
              discoverMcpServerTools(serverId, tenantContext)
            )
          }
          onScan={(serverId) =>
            runTask("MCP security scan completed", (tenantContext) =>
              runMcpSecurityScan(serverId, tenantContext)
            )
          }
          scans={scans}
          servers={servers}
        />
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(24rem,0.8fr)]">
          <ToolRegistryPanel
            findings={findings}
            onSelect={setSelectedToolId}
            selectedTool={selectedTool}
            tools={tools}
          />
          <ScanHistoryPanel isLoading={scansQuery.isLoading} scans={scans} />
        </div>
        <FindingsPanel
          filters={findingFilters}
          findings={findings}
          onAction={(findingId, action, payload) =>
            runTask(`Finding ${action} submitted`, (tenantContext) => {
              if (action === "accepted") {
                return acceptMcpFindingRisk(findingId, payload, tenantContext);
              }
              if (action === "false-positive") {
                return markMcpFindingFalsePositive(findingId, payload, tenantContext);
              }
              return resolveMcpFinding(findingId, payload, tenantContext);
            })
          }
          onFilter={setFindingFilters}
          onSelect={setSelectedFindingId}
          selectedFinding={selectedFinding}
        />
        <TrafficPanel
          filters={trafficFilters}
          onFilter={setTrafficFilters}
          onInvalidInput={(error) => setError(actionErrorMessage(error, "Invalid MCP proxy input"))}
          onProxyCall={(payload) =>
            runTask("Proxy call evaluated", (tenantContext) =>
              createMcpProxyCall(payload, tenantContext)
            )
          }
          traffic={traffic}
        />
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.7fr)]">
          <ApprovalsPanel
            approvals={approvals}
            filters={approvalFilters}
            onDecision={(approvalId, decision, payload) =>
              runTask(`Approval ${decision}`, (tenantContext) =>
                decision === "approved"
                  ? approveMcpApproval(approvalId, payload, tenantContext)
                  : denyMcpApproval(approvalId, payload, tenantContext)
              )
            }
            onFilter={setApprovalFilters}
          />
          <RateLimitsPanel
            onCreate={(payload) =>
              runTask("Rate limit created", (tenantContext) =>
                createMcpRateLimit(payload, tenantContext)
              )
            }
            rateLimits={rateLimits}
          />
        </div>
      </div>
    </>
  );
}

function McpSummary({
  approvals,
  findings,
  servers,
  tools
}: {
  approvals: McpApproval[];
  findings: McpFinding[];
  servers: McpServer[];
  tools: McpTool[];
}) {
  const openFindings = findings.filter((finding) => finding.status === "open").length;
  const pendingApprovals = approvals.filter((approval) => approval.status === "pending").length;
  const criticalFindings = findings.filter((finding) => finding.severity === "critical").length;

  return (
    <section className="grid gap-4 md:grid-cols-4" data-mcp-summary>
      <MetricCard icon={<Server className="h-4 w-4" />} label="Servers" value={servers.length} />
      <MetricCard icon={<KeyRound className="h-4 w-4" />} label="Tools" value={tools.length} />
      <MetricCard icon={<ShieldAlert className="h-4 w-4" />} label="Open Findings" value={openFindings} />
      <MetricCard
        icon={<CheckCircle2 className="h-4 w-4" />}
        label="Pending Approvals"
        value={`${pendingApprovals} / ${criticalFindings} critical`}
      />
    </section>
  );
}

function ServerRegistryPanel({
  isLoading,
  onCreate,
  onDiscover,
  onScan,
  scans,
  servers
}: {
  isLoading: boolean;
  onCreate: (payload: Record<string, unknown>) => void;
  onDiscover: (serverId: string) => void;
  onScan: (serverId: string) => void;
  scans: McpScanRun[];
  servers: McpServer[];
}) {
  const latestScanByServer = latestScanRunsByServer(scans);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate(mcpServerPayloadFromForm(event.currentTarget));
    event.currentTarget.reset();
  }

  return (
    <Card data-mcp-servers>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle>Server Registry</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              Register governed MCP endpoints and keep their tool catalogs current.
            </p>
          </div>
          <Badge tone="muted">{servers.length} servers</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3 lg:grid-cols-6" data-mcp-server-register-form onSubmit={onSubmit}>
          <Field idPrefix="mcp-server" label="Name" name="name" required />
          <Field idPrefix="mcp-server" label="Endpoint" name="endpoint_url" required type="url" />
          <Field idPrefix="mcp-server" label="Owner" name="owner_user_id" required />
          <SelectField idPrefix="mcp-server" label="Auth" name="auth_type" options={authTypes} />
          <SelectField idPrefix="mcp-server" label="Status" name="status" options={serverStatuses} />
          <div className="grid gap-2">
            <span className="text-xs font-medium">Action</span>
            <Button id="mcp-server-submit" type="submit">
              Register
            </Button>
          </div>
        </form>
        {servers.length === 0 ? (
          <EmptyState
            title={isLoading ? "Loading servers" : "No servers"}
            description={isLoading ? "Fetching MCP registry." : "Register a server to discover tools."}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Server</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Owner</TableHead>
                <TableHead>Tools</TableHead>
                <TableHead>Latest Scan</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {servers.map((server) => {
                const latestScan = latestScanByServer.get(server.id);
                return (
                  <TableRow data-mcp-server-row={server.id} key={server.id}>
                    <TableCell>
                      <strong>{server.name}</strong>
                      <small className="block text-muted-foreground">{server.endpoint_url}</small>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={server.status} />
                    </TableCell>
                    <TableCell>{server.owner_display_name ?? server.owner_user_id}</TableCell>
                    <TableCell>{server.tool_count}</TableCell>
                    <TableCell>
                      <StatusBadge status={latestScan?.status ?? "not_scanned"} />
                      <small className="mt-1 block text-muted-foreground">
                        {summaryNumber(latestScan?.summary, "finding_count")} findings
                      </small>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          data-mcp-discover-tools={server.id}
                          onClick={() => onDiscover(server.id)}
                          type="button"
                          variant="outline"
                        >
                          <RefreshCw className="h-4 w-4" />
                          Discover
                        </Button>
                        <Button
                          data-mcp-run-scan={server.id}
                          onClick={() => onScan(server.id)}
                          type="button"
                          variant="outline"
                        >
                          <Radar className="h-4 w-4" />
                          Scan
                        </Button>
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

function ToolRegistryPanel({
  findings,
  onSelect,
  selectedTool,
  tools
}: {
  findings: McpFinding[];
  onSelect: (toolId: string) => void;
  selectedTool: McpTool | null;
  tools: McpTool[];
}) {
  const findingCounts = openFindingCountsByTool(findings);

  return (
    <Card data-mcp-tools>
      <CardHeader>
        <CardTitle>Tool Registry</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {tools.length === 0 ? (
          <EmptyState title="No tools" description="Run discovery from a registered MCP server." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tool</TableHead>
                <TableHead>Schema Hash</TableHead>
                <TableHead>Risk</TableHead>
                <TableHead>Findings</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Detail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tools.map((tool) => (
                <TableRow data-mcp-tool-row={tool.id} key={tool.id}>
                  <TableCell>
                    <strong>{tool.name}</strong>
                    <small className="block text-muted-foreground">{tool.server_name ?? tool.server_id}</small>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {tool.current_version?.schema_hash ?? "not discovered"}
                  </TableCell>
                  <TableCell>
                    <Badge tone={riskTone(tool.risk_level)}>{tool.risk_level}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge tone={(findingCounts.get(tool.id) ?? 0) > 0 ? "warning" : "success"}>
                      {findingBadgeText(findingCounts.get(tool.id) ?? 0)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={tool.status} />
                  </TableCell>
                  <TableCell>
                    <Button
                      data-mcp-tool-detail-open={tool.id}
                      onClick={() => onSelect(tool.id)}
                      type="button"
                      variant="outline"
                    >
                      Details
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <ToolDetail tool={selectedTool} />
      </CardContent>
    </Card>
  );
}

function ToolDetail({ tool }: { tool: McpTool | null }) {
  if (!tool) {
    return (
      <div className="rounded-md border p-4" data-mcp-tool-detail>
        <EmptyState title="No tool selected" description="Select a tool to inspect schema history." />
      </div>
    );
  }
  const versions = tool.versions ?? [];
  return (
    <section className="rounded-md border p-4" data-mcp-tool-detail={tool.id}>
      <div className="grid gap-3 md:grid-cols-5">
        <Metadata label="Tool" value={tool.name} />
        <Metadata label="Server" value={tool.server_name ?? tool.server_id} />
        <Metadata label="Status" value={tool.status} />
        <Metadata label="Risk" value={tool.risk_level} />
        <Metadata label="Current Hash" value={tool.current_version?.schema_hash ?? "not discovered"} />
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <JsonPreview label="Schema" value={tool.current_version?.schema ?? {}} />
        <section data-mcp-tool-version-history>
          <h4 className="font-semibold">Version History</h4>
          {versions.length === 0 ? (
            <EmptyState title="No versions" description="Run discovery to create schema versions." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Discovered</TableHead>
                  <TableHead>Hash</TableHead>
                  <TableHead>Scan</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {versions.map((version) => (
                  <TableRow data-mcp-tool-version-row={version.id} key={version.id}>
                    <TableCell>{version.discovered_at}</TableCell>
                    <TableCell className="font-mono text-xs">{version.schema_hash}</TableCell>
                    <TableCell>
                      <StatusBadge status={version.scan_status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </section>
      </div>
    </section>
  );
}

function ScanHistoryPanel({ isLoading, scans }: { isLoading: boolean; scans: McpScanRun[] }) {
  return (
    <Card data-mcp-scans>
      <CardHeader>
        <CardTitle>Scan History</CardTitle>
      </CardHeader>
      <CardContent>
        {scans.length === 0 ? (
          <EmptyState
            title={isLoading ? "Loading scans" : "No scans"}
            description={isLoading ? "Fetching scan history." : "Run a server scan to populate findings."}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Server</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Tools</TableHead>
                <TableHead>Findings</TableHead>
                <TableHead>Finished</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scans.map((scan) => (
                <TableRow data-mcp-scan-row={scan.id} key={scan.id}>
                  <TableCell>
                    <strong>{scan.server_name ?? scan.server_id}</strong>
                    <small className="block text-muted-foreground">{scan.started_at}</small>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={scan.status} />
                  </TableCell>
                  <TableCell>{summaryNumber(scan.summary, "tools_scanned")}</TableCell>
                  <TableCell>{summaryNumber(scan.summary, "finding_count")}</TableCell>
                  <TableCell>{scan.finished_at ?? "running"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function FindingsPanel({
  filters,
  findings,
  onAction,
  onFilter,
  onSelect,
  selectedFinding
}: {
  filters: McpParams;
  findings: McpFinding[];
  onAction: (findingId: string, action: "accepted" | "resolved" | "false-positive", payload: Record<string, unknown>) => void;
  onFilter: (params: McpParams) => void;
  onSelect: (findingId: string) => void;
  selectedFinding: McpFinding | null;
}) {
  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter(mcpFindingFilterParamsFromForm(event.currentTarget));
  }

  return (
    <Card data-mcp-findings>
      <CardHeader>
        <CardTitle>Security Findings</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form
          className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_1fr_auto]"
          data-mcp-finding-filter-form
          onSubmit={onSubmit}
        >
          <SelectField
            emptyLabel="All statuses"
            idPrefix="mcp-finding-filter"
            label="Status"
            name="status"
            options={findingStatuses}
            value={String(filters.status ?? "")}
          />
          <SelectField
            emptyLabel="All severities"
            idPrefix="mcp-finding-filter"
            label="Severity"
            name="severity"
            options={findingSeverities}
            value={String(filters.severity ?? "")}
          />
          <Field
            defaultValue={String(filters.server_id ?? "")}
            idPrefix="mcp-finding-filter"
            label="Server"
            name="server_id"
          />
          <Field
            defaultValue={String(filters.tool_id ?? "")}
            idPrefix="mcp-finding-filter"
            label="Tool"
            name="tool_id"
          />
          <Button className="self-end" type="submit">
            Filter
          </Button>
        </form>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.8fr)]">
          {findings.length === 0 ? (
            <EmptyState title="No findings" description="Run a security scan to populate findings." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Finding</TableHead>
                  <TableHead>Tool</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {findings.map((finding) => (
                  <TableRow data-mcp-finding-row={finding.id} key={finding.id}>
                    <TableCell>
                      <strong>{finding.title}</strong>
                      <small className="block text-muted-foreground">{finding.finding_type}</small>
                    </TableCell>
                    <TableCell>
                      {finding.tool_name ?? finding.tool_id}
                      <small className="block text-muted-foreground">
                        {finding.server_name ?? finding.server_id}
                      </small>
                    </TableCell>
                    <TableCell>
                      <Badge tone={riskTone(finding.severity)}>{finding.severity}</Badge>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={finding.status} />
                    </TableCell>
                    <TableCell>{finding.created_at}</TableCell>
                    <TableCell>
                      <Button
                        data-mcp-finding-detail-open={finding.id}
                        onClick={() => onSelect(finding.id)}
                        type="button"
                        variant="outline"
                      >
                        Details
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          <FindingDetail finding={selectedFinding} onAction={onAction} />
        </div>
      </CardContent>
    </Card>
  );
}

function FindingDetail({
  finding,
  onAction
}: {
  finding: McpFinding | null;
  onAction: (findingId: string, action: "accepted" | "resolved" | "false-positive", payload: Record<string, unknown>) => void;
}) {
  if (!finding) {
    return (
      <div className="rounded-md border p-4" data-mcp-finding-detail>
        <EmptyState title="No finding selected" description="Open a finding to review evidence." />
      </div>
    );
  }
  const findingId = finding.id;

  function submitAction(action: "accepted" | "resolved" | "false-positive") {
    return (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      onAction(findingId, action, mcpFindingActionPayloadFromForm(event.currentTarget));
      event.currentTarget.reset();
    };
  }

  return (
    <section className="rounded-md border p-4" data-mcp-finding-detail={finding.id}>
      <div className="grid gap-3 md:grid-cols-2">
        <Metadata label="Finding" value={finding.title} />
        <Metadata label="Tool" value={finding.tool_name ?? finding.tool_id} />
        <Metadata label="Server" value={finding.server_name ?? finding.server_id ?? "n/a"} />
        <Metadata label="Tool Version" value={finding.tool_version_id ?? "unversioned"} />
      </div>
      <div className="mt-4 space-y-3 text-sm">
        <section>
          <h4 className="font-semibold">Description</h4>
          <p className="text-muted-foreground">{finding.description}</p>
        </section>
        <section>
          <h4 className="font-semibold">Recommendation</h4>
          <p className="text-muted-foreground">{finding.recommendation}</p>
        </section>
        <JsonPreview label="Evidence" value={finding.evidence ?? {}} />
      </div>
      <div className="mt-4 grid gap-3" data-mcp-finding-actions>
        <ActionForm
          buttonLabel="Accept Risk"
          dataAttribute="mcp-finding-accept-risk-form"
          label="Risk Reason"
          onSubmit={submitAction("accepted")}
          required
        />
        <ActionForm
          buttonLabel="Resolve"
          dataAttribute="mcp-finding-resolve-form"
          label="Resolution Note"
          onSubmit={submitAction("resolved")}
        />
        <ActionForm
          buttonLabel="False Positive"
          dataAttribute="mcp-finding-false-positive-form"
          label="False Positive Reason"
          onSubmit={submitAction("false-positive")}
          required
        />
      </div>
    </section>
  );
}

function TrafficPanel({
  filters,
  onFilter,
  onInvalidInput,
  onProxyCall,
  traffic
}: {
  filters: McpParams;
  onFilter: (params: McpParams) => void;
  onInvalidInput: (error: unknown) => void;
  onProxyCall: (payload: Record<string, unknown>) => void;
  traffic: McpToolCall[];
}) {
  function onFilterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter(mcpTrafficFilterParamsFromForm(event.currentTarget));
  }

  function onProxySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      onProxyCall(mcpProxyCallPayloadFromForm(event.currentTarget));
    } catch (error) {
      onInvalidInput(error);
      return;
    }
    event.currentTarget.reset();
  }

  return (
    <Card data-mcp-traffic>
      <CardHeader>
        <CardTitle>Proxy Traffic</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3 lg:grid-cols-5" data-mcp-proxy-call-form onSubmit={onProxySubmit}>
          <Field idPrefix="mcp-proxy" label="Source Agent" name="source_agent_id" required />
          <Field idPrefix="mcp-proxy" label="Server ID" name="server_id" required />
          <Field idPrefix="mcp-proxy" label="Tool ID" name="tool_id" required />
          <Field idPrefix="mcp-proxy" label="Correlation" name="correlation_id" />
          <TextArea
            className="lg:col-span-4"
            defaultValue='{"demo":true}'
            idPrefix="mcp-proxy"
            label="Params JSON"
            name="params"
          />
          <Button className="self-end" type="submit">
            Evaluate
          </Button>
        </form>
        <form
          className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_1fr_auto]"
          data-mcp-traffic-filter-form
          onSubmit={onFilterSubmit}
        >
          <SelectField
            emptyLabel="All decisions"
            idPrefix="mcp-traffic-filter"
            label="Decision"
            name="decision"
            options={trafficDecisions}
            value={String(filters.decision ?? "")}
          />
          <Field
            defaultValue={String(filters.server_id ?? "")}
            idPrefix="mcp-traffic-filter"
            label="Server"
            name="server_id"
          />
          <Field
            defaultValue={String(filters.tool_id ?? "")}
            idPrefix="mcp-traffic-filter"
            label="Tool"
            name="tool_id"
          />
          <Field
            defaultValue={String(filters.source_agent_id ?? "")}
            idPrefix="mcp-traffic-filter"
            label="Agent"
            name="source_agent_id"
          />
          <Button className="self-end" type="submit">
            Filter
          </Button>
        </form>
        {traffic.length === 0 ? (
          <EmptyState title="No traffic" description="Governed MCP proxy calls will appear here." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tool</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>Decision</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Policy</TableHead>
                <TableHead>Sanitizer</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {traffic.map((call) => (
                <TableRow data-mcp-traffic-row={call.id} key={call.id}>
                  <TableCell>
                    <strong>{call.tool_name ?? call.tool_id}</strong>
                    <small className="block text-muted-foreground">{call.server_name ?? call.server_id}</small>
                  </TableCell>
                  <TableCell>{call.source_agent_name ?? call.source_agent_id}</TableCell>
                  <TableCell>
                    <StatusBadge status={call.decision} />
                  </TableCell>
                  <TableCell>{call.reason}</TableCell>
                  <TableCell>{call.matched_policy_id ?? "none"}</TableCell>
                  <TableCell>{call.sanitizer_action ?? "none"}</TableCell>
                  <TableCell>{call.created_at}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function ApprovalsPanel({
  approvals,
  filters,
  onDecision,
  onFilter
}: {
  approvals: McpApproval[];
  filters: McpParams;
  onDecision: (approvalId: string, decision: "approved" | "denied", payload: Record<string, unknown>) => void;
  onFilter: (params: McpParams) => void;
}) {
  function onFilterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter({ status: emptyToNull(formString(event.currentTarget, "status")) });
  }

  return (
    <Card data-mcp-approvals>
      <CardHeader>
        <CardTitle>Approval Queue</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3 md:grid-cols-[1fr_auto]" onSubmit={onFilterSubmit}>
          <SelectField
            emptyLabel="All approvals"
            idPrefix="mcp-approval-filter"
            label="Status"
            name="status"
            options={["", "pending", "approved", "denied"]}
            value={String(filters.status ?? "")}
          />
          <Button className="self-end" type="submit">
            Filter
          </Button>
        </form>
        {approvals.length === 0 ? (
          <EmptyState title="No approvals" description="Escalated MCP calls will appear here." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tool</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Policy</TableHead>
                <TableHead>Trust</TableHead>
                <TableHead>Params</TableHead>
                <TableHead>Decision</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {approvals.map((approval) => {
                const call = approval.tool_call;
                const isPending = approval.status === "pending";
                return (
                  <TableRow data-mcp-approval-row={approval.id} key={approval.id}>
                    <TableCell>
                      <strong>{call?.tool_name ?? approval.tool_call_id}</strong>
                      <small className="block text-muted-foreground">{call?.server_name ?? ""}</small>
                    </TableCell>
                    <TableCell>{approval.requested_by_agent_name ?? approval.requested_by_agent_id}</TableCell>
                    <TableCell>
                      <StatusBadge status={approval.status} />
                    </TableCell>
                    <TableCell>{call?.matched_policy_id ?? "none"}</TableCell>
                    <TableCell>{call?.trust_score ?? "unknown"}</TableCell>
                    <TableCell>
                      <code className="text-xs">{JSON.stringify(call?.params_summary ?? {})}</code>
                    </TableCell>
                    <TableCell>
                      {isPending ? (
                        <div className="grid min-w-44 gap-2">
                          <DecisionForm
                            approvalId={approval.id}
                            buttonLabel="Approve"
                            label="Approve Reason"
                            onSubmit={(payload) => onDecision(approval.id, "approved", payload)}
                          />
                          <DecisionForm
                            approvalId={approval.id}
                            buttonLabel="Deny"
                            label="Deny Reason"
                            onSubmit={(payload) => onDecision(approval.id, "denied", payload)}
                            required
                          />
                        </div>
                      ) : (
                        <div className="min-w-44 text-sm text-muted-foreground">
                          {approval.decision_reason ?? approval.decided_at ?? "Decision recorded"}
                        </div>
                      )}
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

function RateLimitsPanel({
  onCreate,
  rateLimits
}: {
  onCreate: (payload: Record<string, unknown>) => void;
  rateLimits: McpRateLimit[];
}) {
  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate(mcpRateLimitPayloadFromForm(event.currentTarget));
    event.currentTarget.reset();
  }

  return (
    <Card data-mcp-rate-limits>
      <CardHeader>
        <CardTitle>Rate Limits</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3" data-mcp-rate-limit-form onSubmit={onSubmit}>
          <SelectField idPrefix="mcp-rate-limit" label="Target Type" name="target_type" options={rateLimitTargets} />
          <Field idPrefix="mcp-rate-limit" label="Target ID" name="target_id" required />
          <Field defaultValue="60" idPrefix="mcp-rate-limit" label="Window Seconds" min={1} name="window_seconds" type="number" />
          <Field defaultValue="60" idPrefix="mcp-rate-limit" label="Max Calls" min={1} name="max_calls" type="number" />
          <label className="flex items-center gap-2 text-sm">
            <input defaultChecked name="enabled" type="checkbox" />
            Enabled
          </label>
          <Button type="submit">Create</Button>
        </form>
        {rateLimits.length === 0 ? (
          <EmptyState title="No rate limits" description="Create a per-agent, server, or tool limit." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Target</TableHead>
                <TableHead>Window</TableHead>
                <TableHead>Max Calls</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rateLimits.map((limit) => (
                <TableRow data-mcp-rate-limit-row={limit.id} key={limit.id}>
                  <TableCell>
                    <strong>{limit.target_type}</strong>
                    <small className="block text-muted-foreground">{limit.target_id}</small>
                  </TableCell>
                  <TableCell>{limit.window_seconds}s</TableCell>
                  <TableCell>{limit.max_calls}</TableCell>
                  <TableCell>
                    <StatusBadge status={limit.enabled ? "enabled" : "disabled"} />
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

function DecisionForm({
  approvalId,
  buttonLabel,
  label,
  onSubmit,
  required = false
}: {
  approvalId: string;
  buttonLabel: string;
  label: string;
  onSubmit: (payload: Record<string, unknown>) => void;
  required?: boolean;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(mcpApprovalDecisionPayloadFromForm(event.currentTarget));
    event.currentTarget.reset();
  }

  return (
    <form className="grid gap-2" data-approval-id={approvalId} onSubmit={submit}>
      <Field
        idPrefix={`${approvalId}-${buttonLabel.toLowerCase()}`}
        label={label}
        name="reason"
        required={required}
      />
      <Button type="submit" variant={buttonLabel === "Deny" ? "destructive" : "outline"}>
        {buttonLabel}
      </Button>
    </form>
  );
}

function ActionForm({
  buttonLabel,
  dataAttribute,
  label,
  onSubmit,
  required = false
}: {
  buttonLabel: string;
  dataAttribute: string;
  label: string;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  required?: boolean;
}) {
  return (
    <form className="grid gap-2" data-form-kind={dataAttribute} onSubmit={onSubmit}>
      <Field idPrefix={dataAttribute} label={label} name="reason" required={required} />
      <Button type="submit" variant={buttonLabel === "False Positive" ? "outline" : "default"}>
        {buttonLabel}
      </Button>
    </form>
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
} & React.InputHTMLAttributes<HTMLInputElement>) {
  const id = `${idPrefix}-${name}`;
  return (
    <div className={cn("grid gap-2", className)}>
      <Label className="text-xs" htmlFor={id}>
        {label}
      </Label>
      <Input id={id} name={name} {...props} />
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
      <Label className="text-xs" htmlFor={id}>
        {label}
      </Label>
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
} & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = `${idPrefix}-${name}`;
  return (
    <div className={cn("grid gap-2", className)}>
      <Label className="text-xs" htmlFor={id}>
        {label}
      </Label>
      <textarea
        className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm"
        id={id}
        name={name}
        {...props}
      />
    </div>
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

function JsonPreview({ label, value }: { label: string; value: unknown }) {
  return (
    <section data-mcp-json-preview={label}>
      <h4 className="font-semibold">{label}</h4>
      <pre className="mt-2 max-h-72 overflow-auto rounded-md bg-muted p-3 text-xs">
        {JSON.stringify(value, null, 2)}
      </pre>
    </section>
  );
}

export function mcpServerPayloadFromForm(form: HTMLFormElement) {
  return {
    name: formString(form, "name"),
    endpoint_url: formString(form, "endpoint_url"),
    owner_user_id: formString(form, "owner_user_id"),
    auth_type: formString(form, "auth_type", "none").toLowerCase(),
    status: formString(form, "status", "registered").toLowerCase(),
    policy_pack_id: emptyToNull(formString(form, "policy_pack_id"))
  };
}

export function mcpFindingFilterParamsFromForm(form: HTMLFormElement) {
  return {
    status: emptyToNull(formString(form, "status")),
    severity: emptyToNull(formString(form, "severity")),
    server_id: emptyToNull(formString(form, "server_id")),
    tool_id: emptyToNull(formString(form, "tool_id"))
  };
}

export function mcpFindingActionPayloadFromForm(form: HTMLFormElement) {
  return {
    reason: emptyToNull(formString(form, "reason"))
  };
}

export function mcpTrafficFilterParamsFromForm(form: HTMLFormElement) {
  return {
    decision: emptyToNull(formString(form, "decision")),
    server_id: emptyToNull(formString(form, "server_id")),
    tool_id: emptyToNull(formString(form, "tool_id")),
    source_agent_id: emptyToNull(formString(form, "source_agent_id"))
  };
}

export function mcpProxyCallPayloadFromForm(form: HTMLFormElement) {
  return {
    source_agent_id: formString(form, "source_agent_id"),
    server_id: formString(form, "server_id"),
    tool_id: formString(form, "tool_id"),
    params: parseJsonObjectField(formString(form, "params"), "Params JSON", { emptyFallback: {} }),
    correlation_id: emptyToNull(formString(form, "correlation_id"))
  };
}

export function mcpApprovalDecisionPayloadFromForm(form: HTMLFormElement) {
  return mcpFindingActionPayloadFromForm(form);
}

export function mcpRateLimitPayloadFromForm(form: HTMLFormElement) {
  return {
    target_type: formString(form, "target_type"),
    target_id: formString(form, "target_id"),
    window_seconds: formNumber(form, "window_seconds", 60),
    max_calls: formNumber(form, "max_calls", 60),
    enabled: formBoolean(form, "enabled")
  };
}

function latestScanRunsByServer(scanRuns: McpScanRun[]) {
  const latest = new Map<string, McpScanRun>();
  for (const scan of scanRuns) {
    if (!latest.has(scan.server_id)) {
      latest.set(scan.server_id, scan);
    }
  }
  return latest;
}

function openFindingCountsByTool(findings: McpFinding[]) {
  const counts = new Map<string, number>();
  for (const finding of findings) {
    if (finding.status === "open") {
      counts.set(finding.tool_id, (counts.get(finding.tool_id) ?? 0) + 1);
    }
  }
  return counts;
}

function findingBadgeText(count: number) {
  return count === 0 ? "clear" : `${count} open`;
}

function summaryNumber(summary: Record<string, unknown> | undefined, key: string) {
  const value = summary?.[key];
  return typeof value === "number" || typeof value === "string" ? value : 0;
}

function riskTone(value: string): "default" | "success" | "warning" | "danger" | "muted" {
  const normalized = value.toLowerCase();
  if (normalized.includes("critical") || normalized.includes("high")) {
    return "danger";
  }
  if (normalized.includes("warn") || normalized.includes("medium") || normalized.includes("changed")) {
    return "warning";
  }
  if (normalized.includes("low") || normalized.includes("clear")) {
    return "success";
  }
  return "muted";
}

function formString(form: HTMLFormElement, name: string, fallback = "") {
  const value = new FormData(form).get(name);
  return typeof value === "string" ? value.trim() : fallback;
}

function formNumber(form: HTMLFormElement, name: string, fallback: number) {
  const parsed = Number.parseInt(formString(form, name, String(fallback)), 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formBoolean(form: HTMLFormElement, name: string) {
  const value = new FormData(form).get(name);
  return value === "on" || value === "true";
}

function emptyToNull(value: string) {
  const stripped = value.trim();
  return stripped || null;
}
