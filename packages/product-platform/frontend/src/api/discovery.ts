import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString } from "./client";

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

export function listDiscoveryScanners() {
  return apiClient.request<DiscoveryScanner[]>("/discovery/scanners");
}

export function listDiscoveryTargets() {
  return apiClient.request<DiscoveryTarget[]>("/discovery/targets");
}

export function createDiscoveryTarget(body: Record<string, unknown>) {
  return apiClient.request<DiscoveryTarget>("/discovery/targets", {
    method: "POST",
    body
  });
}

export function patchDiscoveryTargetSchedule(targetId: string, body: Record<string, unknown>) {
  return apiClient.request<DiscoveryTarget>(
    `/discovery/targets/${encodeURIComponent(targetId)}/schedule`,
    { method: "PATCH", body }
  );
}

export function createDiscoveryRun(body: Record<string, unknown>) {
  return apiClient.request<DiscoveryRun>("/discovery/runs", {
    method: "POST",
    body
  });
}

export function listDiscoveryRuns() {
  return apiClient.request<DiscoveryRun[]>("/discovery/runs");
}

export function getDiscoveryRun(runId: string) {
  return apiClient.request<DiscoveryRun>(`/discovery/runs/${encodeURIComponent(runId)}`);
}

export function listDiscoveryFindings(params: DiscoveryParams = {}) {
  return apiClient.request<DiscoveryFinding[]>(
    `/discovery/findings${queryString(params)}`
  );
}

export function getDiscoveryFinding(findingId: string) {
  return apiClient.request<DiscoveryFinding>(
    `/discovery/findings/${encodeURIComponent(findingId)}`
  );
}

export function reconcileDiscoveryRun(runId: string) {
  return apiClient.request<Record<string, unknown>>(
    `/discovery/reconcile-run/${encodeURIComponent(runId)}`,
    { method: "POST" }
  );
}

export function assignDiscoveryFindingOwner(findingId: string, body: Record<string, unknown>) {
  return apiClient.request<DiscoveryFinding>(
    `/discovery/findings/${encodeURIComponent(findingId)}/assign-owner`,
    { method: "POST", body }
  );
}

export function registerDiscoveryFindingAgent(findingId: string, body: Record<string, unknown>) {
  return apiClient.request<Record<string, unknown>>(
    `/discovery/findings/${encodeURIComponent(findingId)}/register-agent`,
    { method: "POST", body }
  );
}

export function suppressDiscoveryFinding(findingId: string, body: Record<string, unknown>) {
  return apiClient.request<DiscoveryFinding>(
    `/discovery/findings/${encodeURIComponent(findingId)}/suppress`,
    { method: "POST", body }
  );
}

export function markDiscoveryFindingDecommissioned(findingId: string) {
  return apiClient.request<DiscoveryFinding>(
    `/discovery/findings/${encodeURIComponent(findingId)}/mark-decommissioned`,
    { method: "POST" }
  );
}

export function useDiscoveryScanners() {
  return useQuery({ queryKey: ["discovery", "scanners"], queryFn: listDiscoveryScanners });
}

export function useDiscoveryTargets() {
  return useQuery({ queryKey: ["discovery", "targets"], queryFn: listDiscoveryTargets });
}

export function useDiscoveryRuns() {
  return useQuery({ queryKey: ["discovery", "runs"], queryFn: listDiscoveryRuns });
}

export function useDiscoveryFindings(params: DiscoveryParams = {}) {
  return useQuery({
    queryKey: ["discovery", "findings", params],
    queryFn: () => listDiscoveryFindings(params)
  });
}

export function useDiscoveryMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["discovery"] });
    }
  });
}
