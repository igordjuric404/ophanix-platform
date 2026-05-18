import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";

export type McpParams = Record<string, string | number | boolean | null | undefined>;

export interface McpServer {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  name: string;
  endpoint_url: string;
  owner_user_id: string;
  owner_display_name?: string | null;
  owner_email?: string | null;
  auth_type: string;
  status: string;
  policy_pack_id?: string | null;
  tool_count: number;
  created_at: string;
  updated_at: string;
  last_discovered_at?: string | null;
}

export interface McpToolVersion {
  id: string;
  tool_id: string;
  schema: Record<string, unknown>;
  schema_hash: string;
  definition?: Record<string, unknown>;
  discovered_at: string;
  scan_status: string;
}

export interface McpTool {
  id: string;
  server_id: string;
  server_name?: string | null;
  name: string;
  description: string;
  current_version_id?: string | null;
  current_version?: McpToolVersion | null;
  versions?: McpToolVersion[];
  risk_level: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface McpToolDiscovery {
  server_id: string;
  discovered_count: number;
  tools: McpTool[];
}

export interface McpScanRun {
  id: string;
  server_id: string;
  server_name?: string | null;
  status: string;
  started_at: string;
  finished_at?: string | null;
  summary?: Record<string, unknown>;
  error_message?: string | null;
  findings?: McpFinding[];
}

export interface McpFinding {
  id: string;
  scan_run_id: string;
  server_id?: string | null;
  server_name?: string | null;
  tool_id: string;
  tool_name?: string | null;
  tool_version_id?: string | null;
  finding_type: string;
  severity: string;
  title: string;
  description: string;
  evidence?: Record<string, unknown>;
  recommendation: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface McpToolCall {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  server_id: string;
  server_name?: string | null;
  tool_id: string;
  tool_name?: string | null;
  source_agent_id: string;
  source_agent_name?: string | null;
  params_summary?: Record<string, unknown>;
  decision: string;
  reason: string;
  matched_policy_id?: string | null;
  matched_policy_version_id?: string | null;
  trust_threshold_id?: string | null;
  trust_score?: number | null;
  gateway_stage?: string | null;
  response?: Record<string, unknown> | null;
  sanitizer_action?: string | null;
  latency_ms: number;
  correlation_id?: string | null;
  created_at: string;
}

export interface McpApproval {
  id: string;
  tool_call_id: string;
  status: string;
  requested_by_agent_id: string;
  requested_by_agent_name?: string | null;
  approved_by_user_id?: string | null;
  decision_reason?: string | null;
  requested_at: string;
  decided_at?: string | null;
  tool_call?: McpToolCall | null;
}

export interface McpRateLimit {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  target_type: string;
  target_id: string;
  window_seconds: number;
  max_calls: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export function createMcpServer(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<McpServer>("/mcp/servers", { method: "POST", body, tenantContext });
}

export function listMcpServers(params: McpParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<McpServer[]>(`/mcp/servers${queryString(params)}`, {
    tenantContext
  });
}

export function getMcpServer(serverId: string, tenantContext?: TenantContext) {
  return apiClient.request<McpServer>(`/mcp/servers/${encodeURIComponent(serverId)}`, {
    tenantContext
  });
}

export function patchMcpServer(
  serverId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<McpServer>(`/mcp/servers/${encodeURIComponent(serverId)}`, {
    method: "PATCH",
    body,
    tenantContext
  });
}

export function discoverMcpServerTools(serverId: string, tenantContext?: TenantContext) {
  return apiClient.request<McpToolDiscovery>(
    `/mcp/servers/${encodeURIComponent(serverId)}/discover-tools`,
    { method: "POST", tenantContext }
  );
}

export function listMcpTools(params: McpParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<McpTool[]>(`/mcp/tools${queryString(params)}`, { tenantContext });
}

export function getMcpTool(toolId: string, tenantContext?: TenantContext) {
  return apiClient.request<McpTool>(`/mcp/tools/${encodeURIComponent(toolId)}`, {
    tenantContext
  });
}

export function runMcpSecurityScan(serverId: string, tenantContext?: TenantContext) {
  return apiClient.request<McpScanRun>(`/mcp/servers/${encodeURIComponent(serverId)}/scan`, {
    method: "POST",
    tenantContext
  });
}

export function listMcpScans(params: McpParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<McpScanRun[]>(`/mcp/scans${queryString(params)}`, { tenantContext });
}

export function getMcpScan(scanId: string, tenantContext?: TenantContext) {
  return apiClient.request<McpScanRun>(`/mcp/scans/${encodeURIComponent(scanId)}`, {
    tenantContext
  });
}

export function listMcpFindings(params: McpParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<McpFinding[]>(`/mcp/findings${queryString(params)}`, {
    tenantContext
  });
}

export function acceptMcpFindingRisk(
  findingId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<McpFinding>(
    `/mcp/findings/${encodeURIComponent(findingId)}/accept-risk`,
    { method: "POST", body, tenantContext }
  );
}

export function resolveMcpFinding(
  findingId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<McpFinding>(`/mcp/findings/${encodeURIComponent(findingId)}/resolve`, {
    method: "POST",
    body,
    tenantContext
  });
}

export function markMcpFindingFalsePositive(
  findingId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<McpFinding>(
    `/mcp/findings/${encodeURIComponent(findingId)}/false-positive`,
    { method: "POST", body, tenantContext }
  );
}

export function createMcpProxyCall(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<McpToolCall>("/mcp/proxy/call", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listMcpTraffic(params: McpParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<McpToolCall[]>(`/mcp/traffic${queryString(params)}`, {
    tenantContext
  });
}

export function listMcpApprovals(params: McpParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<McpApproval[]>(`/mcp/approvals${queryString(params)}`, {
    tenantContext
  });
}

export function approveMcpApproval(
  approvalId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<McpApproval>(
    `/mcp/approvals/${encodeURIComponent(approvalId)}/approve`,
    { method: "POST", body, tenantContext }
  );
}

export function denyMcpApproval(
  approvalId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<McpApproval>(`/mcp/approvals/${encodeURIComponent(approvalId)}/deny`, {
    method: "POST",
    body,
    tenantContext
  });
}

export function listMcpRateLimits(params: McpParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<McpRateLimit[]>(`/mcp/rate-limits${queryString(params)}`, {
    tenantContext
  });
}

export function createMcpRateLimit(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<McpRateLimit>("/mcp/rate-limits", {
    method: "POST",
    body,
    tenantContext
  });
}

export function useMcpServers(params: McpParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["mcp", "servers", params], scope),
    queryFn: () => listMcpServers(params, scope.context)
  });
}

export function useMcpTools(params: McpParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["mcp", "tools", params], scope),
    queryFn: () => listMcpTools(params, scope.context)
  });
}

export function useMcpToolDetail(toolId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(toolId),
    queryKey: scopedQueryKey(["mcp", "tools", toolId], scope),
    queryFn: () => getMcpTool(toolId as string, scope.context)
  });
}

export function useMcpScans(params: McpParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["mcp", "scans", params], scope),
    queryFn: () => listMcpScans(params, scope.context)
  });
}

export function useMcpScanDetail(scanId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(scanId),
    queryKey: scopedQueryKey(["mcp", "scans", scanId], scope),
    queryFn: () => getMcpScan(scanId as string, scope.context)
  });
}

export function useMcpFindings(params: McpParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["mcp", "findings", params], scope),
    queryFn: () => listMcpFindings(params, scope.context)
  });
}

export function useMcpTraffic(params: McpParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["mcp", "traffic", params], scope),
    queryFn: () => listMcpTraffic(params, scope.context)
  });
}

export function useMcpApprovals(params: McpParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["mcp", "approvals", params], scope),
    queryFn: () => listMcpApprovals(params, scope.context)
  });
}

export function useMcpRateLimits(params: McpParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["mcp", "rate-limits", params], scope),
    queryFn: () => listMcpRateLimits(params, scope.context)
  });
}

export function useMcpMutation() {
  const queryClient = useQueryClient();
  const scope = useTenantQueryScope();
  return useMutation({
    mutationFn: async (task: (tenantContext: TenantContext) => Promise<unknown>) =>
      task(scope.context),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["mcp"], scope) });
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["policies"], scope) });
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["trust"], scope) });
    }
  });
}
