import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";

export type ObservabilityParams = Record<string, string | number | boolean | null | undefined>;

export interface ObservabilityTrace {
  id: string;
  organization_id: string;
  environment_id: string;
  trace_id: string;
  name: string;
  status: string;
  agent_id?: string | null;
  runtime_session_id?: string | null;
  correlation_id?: string | null;
  metadata: Record<string, unknown>;
  started_at: string;
  ended_at?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ObservabilitySpan {
  id: string;
  trace_id: string;
  span_id: string;
  parent_span_id?: string | null;
  span_kind: string;
  name: string;
  status: string;
  start_time: string;
  end_time?: string | null;
  latency_ms?: number | null;
  resource_type?: string | null;
  resource_id?: string | null;
  attributes: Record<string, unknown>;
  created_at: string;
}

export interface ObservabilityEvalResult {
  id: string;
  organization_id: string;
  environment_id: string;
  trace_id: string;
  span_id?: string | null;
  dataset_id?: string | null;
  dataset_name?: string | null;
  evaluator_name: string;
  score?: number | null;
  label?: string | null;
  passed?: boolean | null;
  feedback: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_by?: string | null;
  created_at: string;
}

export interface ObservabilityTraceTimelineEntry {
  kind: string;
  id: string;
  name: string;
  status: string;
  timestamp: string;
  span_id?: string | null;
  parent_span_id?: string | null;
}

export interface ObservabilityTraceDetail {
  trace: ObservabilityTrace;
  spans: ObservabilitySpan[];
  runtime_sessions: Array<Record<string, unknown>>;
  runs: Array<Record<string, unknown>>;
  runtime_actions: Array<Record<string, unknown>>;
  tool_runtime_actions: Array<Record<string, unknown>>;
  mcp_tool_calls: Array<Record<string, unknown>>;
  policy_evaluations: Array<Record<string, unknown>>;
  eval_results: ObservabilityEvalResult[];
  annotations: Array<Record<string, unknown>>;
  feedback: Array<Record<string, unknown>>;
  artifacts: Array<Record<string, unknown>>;
  model_calls: Array<Record<string, unknown>>;
  timeline: ObservabilityTraceTimelineEntry[];
}

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
  source: string;
  source_resource_type?: string | null;
  source_resource_id?: string | null;
  trace_id?: string | null;
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
  source: string;
  source_resource_type?: string | null;
  source_resource_id?: string | null;
  trace_id?: string | null;
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
  source: string;
  source_resource_type?: string | null;
  source_resource_id?: string | null;
  trace_id?: string | null;
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

export interface TelemetryDerivationResponse {
  slo_measurements: SloMeasurement[];
  cost_events: CostEvent[];
  incidents: Incident[];
  examined_tool_runtime_actions: number;
  examined_runtime_actions: number;
  skipped_duplicate_cost_events: number;
}

export function listObservabilityTraces(
  params: ObservabilityParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<ObservabilityTrace[]>(
    `/observability/traces${queryString(params)}`,
    { tenantContext }
  );
}

export function getObservabilityTraceDetail(traceId: string, tenantContext?: TenantContext) {
  return apiClient.request<ObservabilityTraceDetail>(
    `/observability/traces/${encodeURIComponent(traceId)}`,
    { tenantContext }
  );
}

export function createObservabilityEvalResult(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<ObservabilityEvalResult>("/observability/eval-results", {
    method: "POST",
    body,
    tenantContext
  });
}

export function createObservabilitySlo(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<SloObjective>("/observability/slo", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listObservabilitySlos(
  params: ObservabilityParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<SloObjective[]>(`/observability/slo${queryString(params)}`, {
    tenantContext
  });
}

export function createObservabilitySloMeasurement(
  sloId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<SloMeasurement>(
    `/observability/slo/${encodeURIComponent(sloId)}/measurements`,
    { method: "POST", body, tenantContext }
  );
}

export function createObservabilityCostBudget(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<CostBudget>("/observability/cost-budgets", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listObservabilityCostBudgets(
  params: ObservabilityParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<CostBudget[]>(
    `/observability/cost-budgets${queryString(params)}`,
    { tenantContext }
  );
}

export function createObservabilityCostEvent(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<CostEvent>("/observability/cost-events", {
    method: "POST",
    body,
    tenantContext
  });
}

export function getObservabilityCosts(tenantContext?: TenantContext) {
  return apiClient.request<CostDashboard>("/observability/costs", { tenantContext });
}

export function deriveObservabilityTelemetry(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<TelemetryDerivationResponse>("/observability/telemetry/derive", {
    method: "POST",
    body,
    tenantContext
  });
}

export function createObservabilityIncident(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Incident>("/observability/incidents", {
    method: "POST",
    body,
    tenantContext
  });
}

export function createObservabilityIncidentFromEvent(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Incident>("/observability/incidents/from-event", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listObservabilityIncidents(
  params: ObservabilityParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<Incident[]>(`/observability/incidents${queryString(params)}`, {
    tenantContext
  });
}

export function acknowledgeObservabilityIncident(
  incidentId: string,
  tenantContext?: TenantContext
) {
  return apiClient.request<Incident>(
    `/observability/incidents/${encodeURIComponent(incidentId)}/ack`,
    { method: "POST", tenantContext }
  );
}

export function resolveObservabilityIncident(
  incidentId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Incident>(
    `/observability/incidents/${encodeURIComponent(incidentId)}/resolve`,
    { method: "POST", body, tenantContext }
  );
}

export function createObservabilityChaosExperiment(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<ChaosExperiment>("/observability/chaos/experiments", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listObservabilityChaosExperiments(
  params: ObservabilityParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<ChaosExperiment[]>(
    `/observability/chaos/experiments${queryString(params)}`,
    { tenantContext }
  );
}

export function runObservabilityChaosExperiment(
  experimentId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<ChaosRun>(
    `/observability/chaos/experiments/${encodeURIComponent(experimentId)}/run`,
    { method: "POST", body, tenantContext }
  );
}

export function stopObservabilityChaosRun(runId: string, tenantContext?: TenantContext) {
  return apiClient.request<ChaosRun>(
    `/observability/chaos/runs/${encodeURIComponent(runId)}/stop`,
    { method: "POST", tenantContext }
  );
}

export function createObservabilityRollout(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Rollout>("/observability/rollouts", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listObservabilityRollouts(
  params: ObservabilityParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<Rollout[]>(`/observability/rollouts${queryString(params)}`, {
    tenantContext
  });
}

export function advanceObservabilityRollout(
  rolloutId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Rollout>(
    `/observability/rollouts/${encodeURIComponent(rolloutId)}/advance`,
    { method: "POST", body, tenantContext }
  );
}

export function rollbackObservabilityRollout(
  rolloutId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Rollout>(
    `/observability/rollouts/${encodeURIComponent(rolloutId)}/rollback`,
    { method: "POST", body, tenantContext }
  );
}

export function useObservabilitySlos(params: ObservabilityParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["observability", "slos", params], scope),
    queryFn: () => listObservabilitySlos(params, scope.context)
  });
}

export function useObservabilityCosts() {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["observability", "costs"], scope),
    queryFn: () => getObservabilityCosts(scope.context)
  });
}

export function useObservabilityIncidents(params: ObservabilityParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["observability", "incidents", params], scope),
    queryFn: () => listObservabilityIncidents(params, scope.context)
  });
}

export function useObservabilityChaosExperiments(params: ObservabilityParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["observability", "chaos-experiments", params], scope),
    queryFn: () => listObservabilityChaosExperiments(params, scope.context)
  });
}

export function useObservabilityRollouts(params: ObservabilityParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["observability", "rollouts", params], scope),
    queryFn: () => listObservabilityRollouts(params, scope.context)
  });
}

export function useObservabilityTraces(params: ObservabilityParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["observability", "traces", params], scope),
    queryFn: () => listObservabilityTraces(params, scope.context)
  });
}

export function useObservabilityTraceDetail(traceId?: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(traceId),
    queryKey: scopedQueryKey(["observability", "trace-detail", traceId], scope),
    queryFn: () => getObservabilityTraceDetail(traceId ?? "", scope.context)
  });
}

export function useObservabilityMutation() {
  const queryClient = useQueryClient();
  const scope = useTenantQueryScope();
  return useMutation({
    mutationFn: async (task: (tenantContext: TenantContext) => Promise<unknown>) =>
      task(scope.context),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["observability"], scope) });
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["audit"], scope) });
    }
  });
}
