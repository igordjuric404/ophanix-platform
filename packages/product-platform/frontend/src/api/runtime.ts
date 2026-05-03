import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString } from "./client";

export type RuntimeParams = Record<string, string | number | boolean | null | undefined>;

export interface RuntimeRingDecision {
  id: string;
  runtime_action_id: string;
  session_id: string;
  agent_id: string;
  action_name: string;
  resource_type: string;
  agent_trust_score: number;
  required_ring: number;
  assigned_ring: number;
  result: string;
  reason: string;
  created_at: string;
}

export interface RuntimeAction {
  id: string;
  session_id: string;
  action_name: string;
  resource_type: string;
  required_ring?: number | null;
  decision: string;
  reason: string;
  latency_ms: number;
  correlation_id?: string | null;
  created_at: string;
  ring_decision?: RuntimeRingDecision | null;
}

export interface RuntimeSession {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  agent_id: string;
  agent_name?: string | null;
  state: string;
  ring: number;
  sponsor_user_id?: string | null;
  started_at: string;
  ended_at?: string | null;
  metadata?: Record<string, unknown>;
  actions?: RuntimeAction[];
}

export interface RuntimeRingRule {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  action_pattern: string;
  required_ring: number;
  min_trust_score: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface RuntimeSagaStep {
  id: string;
  saga_id: string;
  step_order: number;
  name: string;
  action_name: string;
  target_agent_id: string;
  target_agent_name?: string | null;
  required_capability?: string | null;
  timeout_seconds: number;
  retry_count: number;
  compensation_action?: string | null;
  status: string;
  result?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface RuntimeSagaEvent {
  id: string;
  saga_id: string;
  step_id?: string | null;
  event_type: string;
  message: string;
  payload?: Record<string, unknown>;
  created_at: string;
}

export interface RuntimeSaga {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  runtime_session_id?: string | null;
  name: string;
  status: string;
  created_by: string;
  started_at?: string | null;
  finished_at?: string | null;
  correlation_id?: string | null;
  created_at: string;
  updated_at: string;
  steps?: RuntimeSagaStep[];
  events?: RuntimeSagaEvent[];
}

export interface RuntimeSagaExecution {
  saga_id: string;
  runtime_session_id?: string | null;
  status: string;
  message: string;
  executed_step_ids: string[];
  compensated_step_ids: string[];
  failed_step_id?: string | null;
  saga: RuntimeSaga;
}

export interface RuntimeSandboxProfile {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  name: string;
  provider_type: string;
  allowed_imports: string[];
  blocked_imports: string[];
  allowed_paths: string[];
  network_policy?: Record<string, unknown>;
  resource_limits?: Record<string, unknown>;
  status: string;
  provider_warning?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RuntimeSandboxViolation {
  line: number;
  column: number;
  violation_type: string;
  description: string;
  severity: string;
}

export interface RuntimeSandboxDecision {
  id?: string | null;
  profile_id: string;
  agent_id?: string | null;
  action_name?: string | null;
  decision: string;
  reason: string;
  violations: RuntimeSandboxViolation[];
  provider_warning?: string | null;
  created_at?: string | null;
}

export interface RuntimeKillSwitchEvent {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  target_type: string;
  target_id: string;
  scope: string;
  reason: string;
  actor_id: string;
  status: string;
  created_at: string;
}

export function createRuntimeSession(body: Record<string, unknown>) {
  return apiClient.request<RuntimeSession>("/runtime/sessions", { method: "POST", body });
}

export function listRuntimeSessions(params: RuntimeParams = {}) {
  return apiClient.request<RuntimeSession[]>(`/runtime/sessions${queryString(params)}`);
}

export function getRuntimeSession(sessionId: string) {
  return apiClient.request<RuntimeSession>(`/runtime/sessions/${encodeURIComponent(sessionId)}`);
}

export function endRuntimeSession(sessionId: string, body: Record<string, unknown> = {}) {
  return apiClient.request<RuntimeSession>(
    `/runtime/sessions/${encodeURIComponent(sessionId)}/end`,
    { method: "POST", body }
  );
}

export function createRuntimeAction(sessionId: string, body: Record<string, unknown>) {
  return apiClient.request<RuntimeAction>(
    `/runtime/sessions/${encodeURIComponent(sessionId)}/actions`,
    { method: "POST", body }
  );
}

export function listRuntimeRingDecisions(params: RuntimeParams = {}) {
  return apiClient.request<RuntimeRingDecision[]>(
    `/runtime/ring-decisions${queryString(params)}`
  );
}

export function listRuntimeRingRules(params: RuntimeParams = {}) {
  return apiClient.request<RuntimeRingRule[]>(`/runtime/ring-rules${queryString(params)}`);
}

export function createRuntimeRingRule(body: Record<string, unknown>) {
  return apiClient.request<RuntimeRingRule>("/runtime/ring-rules", { method: "POST", body });
}

export function createRuntimeSaga(body: Record<string, unknown>) {
  return apiClient.request<RuntimeSaga>("/runtime/sagas", { method: "POST", body });
}

export function listRuntimeSagas(params: RuntimeParams = {}) {
  return apiClient.request<RuntimeSaga[]>(`/runtime/sagas${queryString(params)}`);
}

export function getRuntimeSaga(sagaId: string) {
  return apiClient.request<RuntimeSaga>(`/runtime/sagas/${encodeURIComponent(sagaId)}`);
}

export function addRuntimeSagaStep(sagaId: string, body: Record<string, unknown>) {
  return apiClient.request<RuntimeSagaStep>(
    `/runtime/sagas/${encodeURIComponent(sagaId)}/steps`,
    { method: "POST", body }
  );
}

export function executeRuntimeSaga(sagaId: string, body: Record<string, unknown>) {
  return apiClient.request<RuntimeSagaExecution>(
    `/runtime/sagas/${encodeURIComponent(sagaId)}/execute`,
    { method: "POST", body }
  );
}

export function cancelRuntimeSaga(sagaId: string, body: Record<string, unknown>) {
  return apiClient.request<RuntimeSaga>(`/runtime/sagas/${encodeURIComponent(sagaId)}/cancel`, {
    method: "POST",
    body
  });
}

export function createRuntimeSandboxProfile(body: Record<string, unknown>) {
  return apiClient.request<RuntimeSandboxProfile>("/runtime/sandbox-profiles", {
    method: "POST",
    body
  });
}

export function listRuntimeSandboxProfiles(params: RuntimeParams = {}) {
  return apiClient.request<RuntimeSandboxProfile[]>(
    `/runtime/sandbox-profiles${queryString(params)}`
  );
}

export function patchRuntimeSandboxProfile(profileId: string, body: Record<string, unknown>) {
  return apiClient.request<RuntimeSandboxProfile>(
    `/runtime/sandbox-profiles/${encodeURIComponent(profileId)}`,
    { method: "PATCH", body }
  );
}

export function testRuntimeSandboxProfile(profileId: string, body: Record<string, unknown>) {
  return apiClient.request<RuntimeSandboxDecision>(
    `/runtime/sandbox-profiles/${encodeURIComponent(profileId)}/test`,
    { method: "POST", body }
  );
}

export function triggerRuntimeKillSwitch(body: Record<string, unknown>) {
  return apiClient.request<RuntimeKillSwitchEvent>("/runtime/kill-switch", {
    method: "POST",
    body
  });
}

export function listRuntimeKillSwitchEvents(params: RuntimeParams = {}) {
  return apiClient.request<RuntimeKillSwitchEvent[]>(
    `/runtime/kill-switch/events${queryString(params)}`
  );
}

export function useRuntimeSessions(params: RuntimeParams = {}) {
  return useQuery({
    queryKey: ["runtime", "sessions", params],
    queryFn: () => listRuntimeSessions(params)
  });
}

export function useRuntimeSessionDetail(sessionId: string | null) {
  return useQuery({
    enabled: Boolean(sessionId),
    queryKey: ["runtime", "sessions", sessionId],
    queryFn: () => getRuntimeSession(sessionId as string)
  });
}

export function useRuntimeRingDecisions(params: RuntimeParams = {}) {
  return useQuery({
    queryKey: ["runtime", "ring-decisions", params],
    queryFn: () => listRuntimeRingDecisions(params)
  });
}

export function useRuntimeRingRules(params: RuntimeParams = {}) {
  return useQuery({
    queryKey: ["runtime", "ring-rules", params],
    queryFn: () => listRuntimeRingRules(params)
  });
}

export function useRuntimeSagas(params: RuntimeParams = {}) {
  return useQuery({
    queryKey: ["runtime", "sagas", params],
    queryFn: () => listRuntimeSagas(params)
  });
}

export function useRuntimeSagaDetail(sagaId: string | null) {
  return useQuery({
    enabled: Boolean(sagaId),
    queryKey: ["runtime", "sagas", sagaId],
    queryFn: () => getRuntimeSaga(sagaId as string)
  });
}

export function useRuntimeSandboxProfiles(params: RuntimeParams = {}) {
  return useQuery({
    queryKey: ["runtime", "sandbox-profiles", params],
    queryFn: () => listRuntimeSandboxProfiles(params)
  });
}

export function useRuntimeKillSwitchEvents(params: RuntimeParams = {}) {
  return useQuery({
    queryKey: ["runtime", "kill-switch-events", params],
    queryFn: () => listRuntimeKillSwitchEvents(params)
  });
}

export function useRuntimeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["runtime"] });
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
      void queryClient.invalidateQueries({ queryKey: ["trust"] });
      void queryClient.invalidateQueries({ queryKey: ["policies"] });
    }
  });
}
