import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";

export interface DiscoveryScanner {
  id: string;
  scanner_type: string;
  name: string;
  description?: string | null;
  status?: string | null;
  available?: boolean | null;
  required_config?: string[];
  optional_config?: string[];
}

export interface DiscoveryTarget {
  id: string;
  scanner_type: string;
  target_type: string;
  target_value: string;
  schedule_mode?: string | null;
  schedule_enabled?: boolean | null;
  next_run_at?: string | null;
  enabled?: boolean | null;
}

export interface DiscoveryRawFinding {
  id: string;
  fingerprint: string;
  raw_payload_json?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface DiscoveryRun {
  id: string;
  scanner_type?: string | null;
  target_id?: string | null;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  raw_finding_count?: number | null;
  high_risk_count?: number | null;
  summary_json?: Record<string, unknown> | null;
  raw_findings?: DiscoveryRawFinding[];
}

export interface DiscoveryEvidence {
  id: string;
  evidence_type: string;
  evidence_value: string;
  confidence?: number | null;
  created_at?: string | null;
}

export interface DiscoveryFinding {
  id: string;
  fingerprint: string;
  detected_name: string;
  agent_type?: string | null;
  source?: string | null;
  owner_hint?: string | null;
  registry_agent_id?: string | null;
  status: string;
  risk_score?: number | null;
  risk_level?: string | null;
  risk_factors?: string[];
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  evidence?: DiscoveryEvidence[];
}

export type DiscoveryParams = Record<string, string | number | boolean | null | undefined>;

export function listDiscoveryScanners(tenantContext?: TenantContext) {
  return apiClient.request<DiscoveryScanner[]>("/discovery/scanners", { tenantContext });
}

export function listDiscoveryTargets(tenantContext?: TenantContext) {
  return apiClient.request<DiscoveryTarget[]>("/discovery/targets", { tenantContext });
}

export function createDiscoveryTarget(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<DiscoveryTarget>("/discovery/targets", {
    method: "POST",
    body,
    tenantContext
  });
}

export function patchDiscoveryTargetSchedule(
  targetId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<DiscoveryTarget>(
    `/discovery/targets/${encodeURIComponent(targetId)}/schedule`,
    { method: "PATCH", body, tenantContext }
  );
}

export function createDiscoveryRun(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<DiscoveryRun>("/discovery/runs", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listDiscoveryRuns(tenantContext?: TenantContext) {
  return apiClient.request<DiscoveryRun[]>("/discovery/runs", { tenantContext });
}

export function getDiscoveryRun(runId: string, tenantContext?: TenantContext) {
  return apiClient.request<DiscoveryRun>(`/discovery/runs/${encodeURIComponent(runId)}`, {
    tenantContext
  });
}

export function listDiscoveryFindings(
  params: DiscoveryParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<DiscoveryFinding[]>(
    `/discovery/findings${queryString(params)}`,
    { tenantContext }
  );
}

export function getDiscoveryFinding(findingId: string, tenantContext?: TenantContext) {
  return apiClient.request<DiscoveryFinding>(
    `/discovery/findings/${encodeURIComponent(findingId)}`,
    { tenantContext }
  );
}

export function reconcileDiscoveryRun(runId: string, tenantContext?: TenantContext) {
  return apiClient.request<Record<string, unknown>>(
    `/discovery/reconcile-run/${encodeURIComponent(runId)}`,
    { method: "POST", tenantContext }
  );
}

export function assignDiscoveryFindingOwner(
  findingId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<DiscoveryFinding>(
    `/discovery/findings/${encodeURIComponent(findingId)}/assign-owner`,
    { method: "POST", body, tenantContext }
  );
}

export function registerDiscoveryFindingAgent(
  findingId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Record<string, unknown>>(
    `/discovery/findings/${encodeURIComponent(findingId)}/register-agent`,
    { method: "POST", body, tenantContext }
  );
}

export function suppressDiscoveryFinding(
  findingId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<DiscoveryFinding>(
    `/discovery/findings/${encodeURIComponent(findingId)}/suppress`,
    { method: "POST", body, tenantContext }
  );
}

export function markDiscoveryFindingDecommissioned(
  findingId: string,
  tenantContext?: TenantContext
) {
  return apiClient.request<DiscoveryFinding>(
    `/discovery/findings/${encodeURIComponent(findingId)}/mark-decommissioned`,
    { method: "POST", tenantContext }
  );
}

export function useDiscoveryScanners() {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["discovery", "scanners"], scope),
    queryFn: () => listDiscoveryScanners(scope.context)
  });
}

export function useDiscoveryTargets() {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["discovery", "targets"], scope),
    queryFn: () => listDiscoveryTargets(scope.context)
  });
}

export function useDiscoveryRuns() {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["discovery", "runs"], scope),
    queryFn: () => listDiscoveryRuns(scope.context)
  });
}

export function useDiscoveryFindings(params: DiscoveryParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["discovery", "findings", params], scope),
    queryFn: () => listDiscoveryFindings(params, scope.context)
  });
}

export function useDiscoveryMutation() {
  const queryClient = useQueryClient();
  const scope = useTenantQueryScope();
  return useMutation({
    mutationFn: async (task: (tenantContext: TenantContext) => Promise<unknown>) =>
      task(scope.context),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["discovery"], scope) });
    }
  });
}
