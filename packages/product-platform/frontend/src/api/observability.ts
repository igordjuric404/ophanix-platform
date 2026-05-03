import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString } from "./client";

export type ObservabilityParams = Record<string, string | number | boolean | null | undefined>;

export interface SloMeasurement {
  id: string;
  slo_id: string;
  value: number;
  good_events: number;
  total_events: number;
  error_budget_remaining: number;
  burn_rate: number;
  status: string;
  metadata: Record<string, unknown>;
  measured_at: string;
}

export interface SloObjective {
  id: string;
  organization_id: string;
  environment_id: string;
  name: string;
  target_type: string;
  target_id: string;
  sli: string;
  target_value: number;
  window: string;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  measurements: SloMeasurement[];
}

export interface CostBudget {
  id: string;
  organization_id: string;
  environment_id: string;
  target_type: string;
  target_id: string;
  period: string;
  amount_limit: number;
  used_amount: number;
  action_on_breach: string;
  breach_action: string;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface CostEvent {
  id: string;
  organization_id: string;
  environment_id: string;
  target_type: string;
  target_id: string;
  provider: string;
  model: string;
  amount: number;
  units: number;
  correlation_id?: string | null;
  created_at: string;
}

export interface CostDashboard {
  budgets: CostBudget[];
  events: CostEvent[];
  total_amount: number;
  by_target: Record<string, number>;
  by_provider: Record<string, number>;
  by_model: Record<string, number>;
}

export interface Incident {
  id: string;
  organization_id: string;
  environment_id: string;
  severity: string;
  status: string;
  title: string;
  summary: string;
  owner_user_id?: string | null;
  correlation_id?: string | null;
  source_event_id?: string | null;
  resolution_note?: string | null;
  started_at: string;
  acknowledged_at?: string | null;
  resolved_at?: string | null;
  updated_at: string;
  related_event_ids: string[];
}

export interface ChaosExperiment {
  id: string;
  organization_id: string;
  environment_id: string;
  name: string;
  fault_type: string;
  target_type: string;
  target_id: string;
  blast_radius: Record<string, unknown>;
  guardrails: Record<string, unknown>;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ChaosRun {
  id: string;
  experiment_id: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  result: Record<string, unknown>;
}

export interface RolloutEvent {
  id: string;
  rollout_id: string;
  stage: number;
  decision: string;
  metrics: Record<string, unknown>;
  created_at: string;
}

export interface Rollout {
  id: string;
  organization_id: string;
  environment_id: string;
  name: string;
  target_type: string;
  target_id: string;
  strategy: string;
  status: string;
  current_stage: number;
  config: Record<string, unknown>;
  created_by: string;
  created_at: string;
  updated_at: string;
  events: RolloutEvent[];
}

export function createObservabilitySlo(body: Record<string, unknown>) {
  return apiClient.request<SloObjective>("/observability/slo", { method: "POST", body });
}

export function listObservabilitySlos(params: ObservabilityParams = {}) {
  return apiClient.request<SloObjective[]>(`/observability/slo${queryString(params)}`);
}

export function createObservabilitySloMeasurement(sloId: string, body: Record<string, unknown>) {
  return apiClient.request<SloMeasurement>(
    `/observability/slo/${encodeURIComponent(sloId)}/measurements`,
    { method: "POST", body }
  );
}

export function createObservabilityCostBudget(body: Record<string, unknown>) {
  return apiClient.request<CostBudget>("/observability/cost-budgets", { method: "POST", body });
}

export function listObservabilityCostBudgets(params: ObservabilityParams = {}) {
  return apiClient.request<CostBudget[]>(
    `/observability/cost-budgets${queryString(params)}`
  );
}

export function createObservabilityCostEvent(body: Record<string, unknown>) {
  return apiClient.request<CostEvent>("/observability/cost-events", { method: "POST", body });
}

export function getObservabilityCosts() {
  return apiClient.request<CostDashboard>("/observability/costs");
}

export function createObservabilityIncident(body: Record<string, unknown>) {
  return apiClient.request<Incident>("/observability/incidents", { method: "POST", body });
}

export function createObservabilityIncidentFromEvent(body: Record<string, unknown>) {
  return apiClient.request<Incident>("/observability/incidents/from-event", {
    method: "POST",
    body
  });
}

export function listObservabilityIncidents(params: ObservabilityParams = {}) {
  return apiClient.request<Incident[]>(`/observability/incidents${queryString(params)}`);
}

export function acknowledgeObservabilityIncident(incidentId: string) {
  return apiClient.request<Incident>(
    `/observability/incidents/${encodeURIComponent(incidentId)}/ack`,
    { method: "POST" }
  );
}

export function resolveObservabilityIncident(incidentId: string, body: Record<string, unknown>) {
  return apiClient.request<Incident>(
    `/observability/incidents/${encodeURIComponent(incidentId)}/resolve`,
    { method: "POST", body }
  );
}

export function createObservabilityChaosExperiment(body: Record<string, unknown>) {
  return apiClient.request<ChaosExperiment>("/observability/chaos/experiments", {
    method: "POST",
    body
  });
}

export function listObservabilityChaosExperiments(params: ObservabilityParams = {}) {
  return apiClient.request<ChaosExperiment[]>(
    `/observability/chaos/experiments${queryString(params)}`
  );
}

export function runObservabilityChaosExperiment(
  experimentId: string,
  body: Record<string, unknown>
) {
  return apiClient.request<ChaosRun>(
    `/observability/chaos/experiments/${encodeURIComponent(experimentId)}/run`,
    { method: "POST", body }
  );
}

export function stopObservabilityChaosRun(runId: string) {
  return apiClient.request<ChaosRun>(
    `/observability/chaos/runs/${encodeURIComponent(runId)}/stop`,
    { method: "POST" }
  );
}

export function createObservabilityRollout(body: Record<string, unknown>) {
  return apiClient.request<Rollout>("/observability/rollouts", { method: "POST", body });
}

export function listObservabilityRollouts(params: ObservabilityParams = {}) {
  return apiClient.request<Rollout[]>(`/observability/rollouts${queryString(params)}`);
}

export function advanceObservabilityRollout(rolloutId: string, body: Record<string, unknown>) {
  return apiClient.request<Rollout>(
    `/observability/rollouts/${encodeURIComponent(rolloutId)}/advance`,
    { method: "POST", body }
  );
}

export function rollbackObservabilityRollout(rolloutId: string, body: Record<string, unknown>) {
  return apiClient.request<Rollout>(
    `/observability/rollouts/${encodeURIComponent(rolloutId)}/rollback`,
    { method: "POST", body }
  );
}

export function useObservabilitySlos(params: ObservabilityParams = {}) {
  return useQuery({
    queryKey: ["observability", "slos", params],
    queryFn: () => listObservabilitySlos(params)
  });
}

export function useObservabilityCosts() {
  return useQuery({
    queryKey: ["observability", "costs"],
    queryFn: getObservabilityCosts
  });
}

export function useObservabilityIncidents(params: ObservabilityParams = {}) {
  return useQuery({
    queryKey: ["observability", "incidents", params],
    queryFn: () => listObservabilityIncidents(params)
  });
}

export function useObservabilityChaosExperiments(params: ObservabilityParams = {}) {
  return useQuery({
    queryKey: ["observability", "chaos-experiments", params],
    queryFn: () => listObservabilityChaosExperiments(params)
  });
}

export function useObservabilityRollouts(params: ObservabilityParams = {}) {
  return useQuery({
    queryKey: ["observability", "rollouts", params],
    queryFn: () => listObservabilityRollouts(params)
  });
}

export function useObservabilityMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["observability"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    }
  });
}
