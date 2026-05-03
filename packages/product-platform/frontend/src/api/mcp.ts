import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString } from "./client";

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

export function createMcpServer(body: Record<string, unknown>) {
  return apiClient.request<McpServer>("/mcp/servers", { method: "POST", body });
}

export function listMcpServers(params: McpParams = {}) {
  return apiClient.request<McpServer[]>(`/mcp/servers${queryString(params)}`);
}

export function getMcpServer(serverId: string) {
  return apiClient.request<McpServer>(`/mcp/servers/${encodeURIComponent(serverId)}`);
}

export function patchMcpServer(serverId: string, body: Record<string, unknown>) {
  return apiClient.request<McpServer>(`/mcp/servers/${encodeURIComponent(serverId)}`, {
    method: "PATCH",
    body
  });
}

export function discoverMcpServerTools(serverId: string) {
  return apiClient.request<McpToolDiscovery>(
    `/mcp/servers/${encodeURIComponent(serverId)}/discover-tools`,
    { method: "POST" }
  );
}

export function listMcpTools(params: McpParams = {}) {
  return apiClient.request<McpTool[]>(`/mcp/tools${queryString(params)}`);
}

export function getMcpTool(toolId: string) {
  return apiClient.request<McpTool>(`/mcp/tools/${encodeURIComponent(toolId)}`);
}

export function runMcpSecurityScan(serverId: string) {
  return apiClient.request<McpScanRun>(`/mcp/servers/${encodeURIComponent(serverId)}/scan`, {
    method: "POST"
  });
}

export function listMcpScans(params: McpParams = {}) {
  return apiClient.request<McpScanRun[]>(`/mcp/scans${queryString(params)}`);
}

export function getMcpScan(scanId: string) {
  return apiClient.request<McpScanRun>(`/mcp/scans/${encodeURIComponent(scanId)}`);
}

export function listMcpFindings(params: McpParams = {}) {
  return apiClient.request<McpFinding[]>(`/mcp/findings${queryString(params)}`);
}

export function acceptMcpFindingRisk(findingId: string, body: Record<string, unknown>) {
  return apiClient.request<McpFinding>(
    `/mcp/findings/${encodeURIComponent(findingId)}/accept-risk`,
    { method: "POST", body }
  );
}

export function resolveMcpFinding(findingId: string, body: Record<string, unknown>) {
  return apiClient.request<McpFinding>(`/mcp/findings/${encodeURIComponent(findingId)}/resolve`, {
    method: "POST",
    body
  });
}

export function markMcpFindingFalsePositive(findingId: string, body: Record<string, unknown>) {
  return apiClient.request<McpFinding>(
    `/mcp/findings/${encodeURIComponent(findingId)}/false-positive`,
    { method: "POST", body }
  );
}

export function createMcpProxyCall(body: Record<string, unknown>) {
  return apiClient.request<McpToolCall>("/mcp/proxy/call", { method: "POST", body });
}

export function listMcpTraffic(params: McpParams = {}) {
  return apiClient.request<McpToolCall[]>(`/mcp/traffic${queryString(params)}`);
}

export function listMcpApprovals(params: McpParams = {}) {
  return apiClient.request<McpApproval[]>(`/mcp/approvals${queryString(params)}`);
}

export function approveMcpApproval(approvalId: string, body: Record<string, unknown>) {
  return apiClient.request<McpApproval>(
    `/mcp/approvals/${encodeURIComponent(approvalId)}/approve`,
    { method: "POST", body }
  );
}

export function denyMcpApproval(approvalId: string, body: Record<string, unknown>) {
  return apiClient.request<McpApproval>(`/mcp/approvals/${encodeURIComponent(approvalId)}/deny`, {
    method: "POST",
    body
  });
}

export function listMcpRateLimits(params: McpParams = {}) {
  return apiClient.request<McpRateLimit[]>(`/mcp/rate-limits${queryString(params)}`);
}

export function createMcpRateLimit(body: Record<string, unknown>) {
  return apiClient.request<McpRateLimit>("/mcp/rate-limits", { method: "POST", body });
}

export function useMcpServers(params: McpParams = {}) {
  return useQuery({
    queryKey: ["mcp", "servers", params],
    queryFn: () => listMcpServers(params)
  });
}

export function useMcpTools(params: McpParams = {}) {
  return useQuery({
    queryKey: ["mcp", "tools", params],
    queryFn: () => listMcpTools(params)
  });
}

export function useMcpToolDetail(toolId: string | null) {
  return useQuery({
    enabled: Boolean(toolId),
    queryKey: ["mcp", "tools", toolId],
    queryFn: () => getMcpTool(toolId as string)
  });
}

export function useMcpScans(params: McpParams = {}) {
  return useQuery({
    queryKey: ["mcp", "scans", params],
    queryFn: () => listMcpScans(params)
  });
}

export function useMcpScanDetail(scanId: string | null) {
  return useQuery({
    enabled: Boolean(scanId),
    queryKey: ["mcp", "scans", scanId],
    queryFn: () => getMcpScan(scanId as string)
  });
}

export function useMcpFindings(params: McpParams = {}) {
  return useQuery({
    queryKey: ["mcp", "findings", params],
    queryFn: () => listMcpFindings(params)
  });
}

export function useMcpTraffic(params: McpParams = {}) {
  return useQuery({
    queryKey: ["mcp", "traffic", params],
    queryFn: () => listMcpTraffic(params)
  });
}

export function useMcpApprovals(params: McpParams = {}) {
  return useQuery({
    queryKey: ["mcp", "approvals", params],
    queryFn: () => listMcpApprovals(params)
  });
}

export function useMcpRateLimits(params: McpParams = {}) {
  return useQuery({
    queryKey: ["mcp", "rate-limits", params],
    queryFn: () => listMcpRateLimits(params)
  });
}

export function useMcpMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mcp"] });
      void queryClient.invalidateQueries({ queryKey: ["policies"] });
      void queryClient.invalidateQueries({ queryKey: ["trust"] });
    }
  });
}
