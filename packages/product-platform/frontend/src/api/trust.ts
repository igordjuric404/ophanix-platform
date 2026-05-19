import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";

export type TrustParams = Record<string, string | number | boolean | null | undefined>;

export type TrustDimensionName =
  | "policy_compliance"
  | "resource_efficiency"
  | "output_quality"
  | "security_posture"
  | "collaboration_health";

export interface TrustDimensionScore {
  score: number;
  signal_count: number;
}

export interface TrustScoreExplanation {
  schema_version: string;
  source_event_versions: string[];
  input_event_count: number;
  dimensions: Record<TrustDimensionName, TrustDimensionScore>;
}

export interface TrustScore {
  schema_version: string;
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  agent_id: string;
  agent_name?: string | null;
  score: number;
  tier: string;
  dimensions: Record<TrustDimensionName, TrustDimensionScore>;
  explanation: TrustScoreExplanation;
  calculated_at: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TrustEvent {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  agent_id: string;
  agent_name?: string | null;
  source_event_id?: string | null;
  dimension: string;
  delta: number;
  reason: string;
  score_before: number;
  score_after: number;
  created_at: string;
}

export interface TrustRule {
  id: string;
  organization_id?: string | null;
  event_type: string;
  dimension: string;
  delta: number;
  min_delta: number;
  max_delta: number;
  enabled: boolean;
  config?: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TrustRecalculationRun {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  status: string;
  started_at: string;
  finished_at?: string | null;
  summary?: Record<string, unknown>;
}

export interface TrustThreshold {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  threshold_type: string;
  target_type: string;
  target_id?: string | null;
  min_score: number;
  required_tier: string;
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TrustHandshake {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  source_agent_id: string;
  target_agent_id: string;
  purpose: string;
  threshold_type: string;
  target_type: string;
  target_id?: string | null;
  required_score: number;
  required_tier: string;
  source_score: number;
  target_score: number;
  result: string;
  reason: string;
  correlation_id?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface TrustCard {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  agent_id: string;
  issuer: string;
  card: Record<string, unknown>;
  signature: string;
  status: string;
  valid_from: string;
  valid_until: string;
  issued_at: string;
  revoked_at?: string | null;
  revocation_reason?: string | null;
}

export interface TrustCardVerification {
  trust_card_id: string;
  agent_id: string;
  status: string;
  verified: boolean;
  reason: string;
  checked_at: string;
}

export interface AgentTrustCard {
  agent_id: string;
  card?: TrustCard | null;
  warning?: string | null;
}

export function listTrustScores(tenantContext?: TenantContext, signal?: AbortSignal) {
  return apiClient.request<TrustScore[]>("/trust/scores", { signal, tenantContext });
}

export function getTrustScore(agentId: string, tenantContext?: TenantContext) {
  return apiClient.request<TrustScore>(`/trust/scores/${encodeURIComponent(agentId)}`, {
    tenantContext
  });
}

export function listTrustEvents(
  params: TrustParams = {},
  tenantContext?: TenantContext,
  signal?: AbortSignal
) {
  return apiClient.request<TrustEvent[]>(`/trust/events${queryString(params)}`, {
    signal,
    tenantContext
  });
}

export function recalculateTrust(
  body: Record<string, unknown> = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<TrustRecalculationRun>("/trust/recalculate", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listTrustRules(
  params: TrustParams = {},
  tenantContext?: TenantContext,
  signal?: AbortSignal
) {
  return apiClient.request<TrustRule[]>(`/trust/rules${queryString(params)}`, {
    signal,
    tenantContext
  });
}

export function patchTrustRule(
  ruleId: string,
  body: Record<string, unknown> = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<TrustRule>(`/trust/rules/${encodeURIComponent(ruleId)}`, {
    method: "PATCH",
    body,
    tenantContext
  });
}

export function listTrustThresholds(
  params: TrustParams = {},
  tenantContext?: TenantContext,
  signal?: AbortSignal
) {
  return apiClient.request<TrustThreshold[]>(`/trust/thresholds${queryString(params)}`, {
    signal,
    tenantContext
  });
}

export function createTrustThreshold(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<TrustThreshold>("/trust/thresholds", {
    method: "POST",
    body,
    tenantContext
  });
}

export function patchTrustThreshold(
  thresholdId: string,
  body: Record<string, unknown> = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<TrustThreshold>(`/trust/thresholds/${encodeURIComponent(thresholdId)}`, {
    method: "PATCH",
    body,
    tenantContext
  });
}

export function listTrustHandshakes(
  params: TrustParams = {},
  tenantContext?: TenantContext,
  signal?: AbortSignal
) {
  return apiClient.request<TrustHandshake[]>(`/trust/handshakes${queryString(params)}`, {
    signal,
    tenantContext
  });
}

export function simulateTrustHandshake(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<TrustHandshake>("/trust/handshakes/simulate", {
    method: "POST",
    body,
    tenantContext
  });
}

export function recordTrustHandshake(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<TrustHandshake>("/trust/handshakes/record", {
    method: "POST",
    body,
    tenantContext
  });
}

export function issueTrustCard(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<TrustCard>("/trust/cards", { method: "POST", body, tenantContext });
}

export function listTrustCards(
  params: TrustParams = {},
  tenantContext?: TenantContext,
  signal?: AbortSignal
) {
  return apiClient.request<TrustCard[]>(`/trust/cards${queryString(params)}`, {
    signal,
    tenantContext
  });
}

export function getTrustCard(cardId: string, tenantContext?: TenantContext, signal?: AbortSignal) {
  return apiClient.request<TrustCard>(`/trust/cards/${encodeURIComponent(cardId)}`, {
    signal,
    tenantContext
  });
}

export function verifyTrustCard(cardId: string, tenantContext?: TenantContext) {
  return apiClient.request<TrustCardVerification>(
    `/trust/cards/${encodeURIComponent(cardId)}/verify`,
    { method: "POST", tenantContext }
  );
}

export function revokeTrustCard(
  cardId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<TrustCard>(`/trust/cards/${encodeURIComponent(cardId)}/revoke`, {
    method: "POST",
    body,
    tenantContext
  });
}

export function getAgentTrustCard(
  agentId: string,
  tenantContext?: TenantContext,
  signal?: AbortSignal
) {
  return apiClient.request<AgentTrustCard>(`/agents/${encodeURIComponent(agentId)}/trust-card`, {
    signal,
    tenantContext
  });
}

export function useTrustScores() {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["trust", "scores"], scope),
    queryFn: ({ signal }) => listTrustScores(scope.context, signal)
  });
}

export function useTrustEvents(params: TrustParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["trust", "events", params], scope),
    queryFn: ({ signal }) => listTrustEvents(params, scope.context, signal)
  });
}

export function useTrustRules(params: TrustParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["trust", "rules", params], scope),
    queryFn: ({ signal }) => listTrustRules(params, scope.context, signal)
  });
}

export function useTrustThresholds(params: TrustParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["trust", "thresholds", params], scope),
    queryFn: ({ signal }) => listTrustThresholds(params, scope.context, signal)
  });
}

export function useTrustHandshakes(params: TrustParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["trust", "handshakes", params], scope),
    queryFn: ({ signal }) => listTrustHandshakes(params, scope.context, signal)
  });
}

export function useTrustCards(params: TrustParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["trust", "cards", params], scope),
    queryFn: ({ signal }) => listTrustCards(params, scope.context, signal)
  });
}

export function useTrustCardDetail(cardId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(cardId),
    queryKey: scopedQueryKey(["trust", "cards", cardId], scope),
    queryFn: ({ signal }) => getTrustCard(cardId as string, scope.context, signal)
  });
}

export function useAgentTrustCard(agentId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(agentId),
    queryKey: scopedQueryKey(["agents", agentId, "trust-card"], scope),
    queryFn: ({ signal }) => getAgentTrustCard(agentId as string, scope.context, signal)
  });
}

export function useTrustMutation() {
  const queryClient = useQueryClient();
  const scope = useTenantQueryScope();
  return useMutation({
    mutationFn: async (task: (tenantContext: TenantContext) => Promise<unknown>) =>
      task(scope.context),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["trust"], scope) });
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["agents"], scope) });
    }
  });
}
