import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString } from "./client";

export type DemoParams = Record<string, string | number | boolean | null | undefined>;

export interface DemoRequiredService {
  key: string;
  label: string;
  required: boolean;
  health_endpoint?: string | null;
  evidence_route?: string | null;
}

export interface DemoProofLink {
  area: string;
  label: string;
  route: string;
  resource_hint?: string | null;
}

export interface DemoEvidenceLink {
  area: string;
  label: string;
  route: string;
  resource_id?: string | null;
  correlation_id?: string | null;
}

export interface DemoProofChecklistItem {
  area: string;
  label: string;
  status: string;
  route: string;
  expected_result: string;
  actual_result?: string | null;
}

export interface DemoScenarioStep {
  id: string;
  scenario_id: string;
  step_order: number;
  title: string;
  expected_result: string;
  action_type: string;
  action_config: Record<string, unknown>;
  proof_links: DemoProofLink[];
  created_at: string;
  updated_at: string;
}

export interface DemoScenarioSummary {
  id: string;
  organization_id: string;
  environment_id: string;
  name: string;
  slug: string;
  description: string;
  value_proof: string;
  status: string;
  required_services: DemoRequiredService[];
  created_at: string;
  updated_at: string;
}

export interface DemoScenarioDetail extends DemoScenarioSummary {
  steps: DemoScenarioStep[];
}

export interface DemoStepRun {
  id: string;
  demo_run_id: string;
  demo_step_id: string;
  status: string;
  result: Record<string, unknown>;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at: string;
  step?: DemoScenarioStep | null;
  actual_result?: string | null;
  evidence_links: DemoEvidenceLink[];
  proof_checklist: DemoProofChecklistItem[];
}

export interface DemoRun {
  id: string;
  organization_id: string;
  environment_id: string;
  scenario_id: string;
  status: string;
  started_by: string;
  started_at: string;
  finished_at?: string | null;
  summary: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  scenario?: DemoScenarioSummary | null;
  step_runs: DemoStepRun[];
}

export interface DemoResetRun {
  id: string;
  organization_id: string;
  environment_id: string;
  status: string;
  requested_by: string;
  started_at: string;
  finished_at?: string | null;
  summary: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DemoBaselineCheck {
  key: string;
  label: string;
  status: string;
  required: boolean;
  detail: string;
  count: number;
  expected_count?: number | null;
  missing: string[];
}

export interface DemoBaselineStatus {
  organization_id: string;
  environment_id: string;
  overall_status: string;
  checked_at: string;
  checks: DemoBaselineCheck[];
  missing_items: string[];
}

export function listDemoScenarios(params: DemoParams = {}) {
  return apiClient.request<DemoScenarioSummary[]>(`/demo/scenarios${queryString(params)}`);
}

export function getDemoScenario(scenarioId: string) {
  return apiClient.request<DemoScenarioDetail>(
    `/demo/scenarios/${encodeURIComponent(scenarioId)}`
  );
}

export function startDemoRun(scenarioId: string) {
  return apiClient.request<DemoRun>(`/demo/scenarios/${encodeURIComponent(scenarioId)}/runs`, {
    method: "POST"
  });
}

export function getDemoRun(runId: string) {
  return apiClient.request<DemoRun>(`/demo/runs/${encodeURIComponent(runId)}`);
}

export function continueDemoRun(runId: string) {
  return apiClient.request<DemoRun>(`/demo/runs/${encodeURIComponent(runId)}/continue`, {
    method: "POST"
  });
}

export function cancelDemoRun(runId: string) {
  return apiClient.request<DemoRun>(`/demo/runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST"
  });
}

export function resetDemoEnvironment(body: Record<string, unknown>) {
  return apiClient.request<DemoResetRun>("/demo/reset", { method: "POST", body });
}

export function listDemoResetRuns(params: DemoParams = {}) {
  return apiClient.request<DemoResetRun[]>(`/demo/reset-runs${queryString(params)}`);
}

export function getDemoResetRun(resetId: string) {
  return apiClient.request<DemoResetRun>(`/demo/reset-runs/${encodeURIComponent(resetId)}`);
}

export function getDemoBaselineStatus() {
  return apiClient.request<DemoBaselineStatus>("/demo/baseline-status");
}

export function useDemoScenarios(params: DemoParams = {}) {
  return useQuery({
    queryKey: ["demo", "scenarios", params],
    queryFn: () => listDemoScenarios(params)
  });
}

export function useDemoScenario(scenarioId: string | null) {
  return useQuery({
    enabled: Boolean(scenarioId),
    queryKey: ["demo", "scenarios", scenarioId],
    queryFn: () => getDemoScenario(scenarioId as string)
  });
}

export function useDemoRun(runId: string | null) {
  return useQuery({
    enabled: Boolean(runId),
    queryKey: ["demo", "runs", runId],
    queryFn: () => getDemoRun(runId as string)
  });
}

export function useDemoResetRuns(params: DemoParams = {}) {
  return useQuery({
    queryKey: ["demo", "reset-runs", params],
    queryFn: () => listDemoResetRuns(params)
  });
}

export function useDemoResetRun(resetId: string | null) {
  return useQuery({
    enabled: Boolean(resetId),
    queryKey: ["demo", "reset-runs", resetId],
    queryFn: () => getDemoResetRun(resetId as string)
  });
}

export function useDemoBaselineStatus() {
  return useQuery({
    queryKey: ["demo", "baseline-status"],
    queryFn: getDemoBaselineStatus
  });
}

export function useDemoMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["demo"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
      void queryClient.invalidateQueries({ queryKey: ["system"] });
    }
  });
}
