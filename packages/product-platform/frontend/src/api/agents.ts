import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";

export interface AgentSummary {
  id: string;
  name: string;
  status: string;
  framework?: string | null;
  runtime_type?: string | null;
  endpoint_url?: string | null;
  owner_user_id?: string | null;
  sponsor_user_id?: string | null;
  trust_tier?: string | null;
  trust_score?: number | null;
  credential_status?: string | null;
  credential_expires_at?: string | null;
  last_heartbeat_at?: string | null;
  capability_count?: number | null;
}

export interface AgentIdentity {
  did?: string | null;
  public_key_fingerprint?: string | null;
  key_type?: string | null;
  identity_status?: string | null;
}

export interface AgentCapability {
  capability_name: string;
  resource_type?: string | null;
  status?: string | null;
}

export interface AgentLifecycleEvent {
  id: string;
  agent_id?: string | null;
  previous_state?: string | null;
  next_state?: string | null;
  actor_id?: string | null;
  reason?: string | null;
  metadata_json?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface AgentAuditEvent {
  id: string;
  event_type: string;
  severity?: string | null;
  created_at?: string | null;
}

export interface AgentDetail {
  summary: AgentSummary;
  identity?: AgentIdentity | null;
  capabilities?: AgentCapability[];
  protocols?: Array<{ protocol: string; endpoint?: string | null; status?: string | null }>;
  latest_heartbeat?: { observed_at?: string | null; status?: string | null } | null;
  lifecycle_events?: AgentLifecycleEvent[];
  auditEvents?: AgentAuditEvent[];
}

export interface CredentialScope {
  scope: string;
  resource_type?: string | null;
  resource_id?: string | null;
}

export interface AgentCredential {
  id: string;
  agent_id?: string | null;
  credential_type?: string | null;
  issuer?: string | null;
  status: string;
  issued_at?: string | null;
  expires_at?: string | null;
  revoked_at?: string | null;
  last_used_at?: string | null;
  scopes?: CredentialScope[];
}

export type AgentListParams = Record<string, string | number | boolean | null | undefined>;

export function listAgents(params: AgentListParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<AgentSummary[]>(`/agents${queryString(params)}`, { tenantContext });
}

export function getAgent(agentId: string, tenantContext?: TenantContext) {
  return apiClient.request<AgentDetail>(`/agents/${encodeURIComponent(agentId)}`, {
    tenantContext
  });
}

export function getAgentTimeline(agentId: string, tenantContext?: TenantContext) {
  return apiClient.request<AgentLifecycleEvent[]>(
    `/agents/${encodeURIComponent(agentId)}/timeline`,
    { tenantContext }
  );
}

export function getAgentAudit(agentId: string, tenantContext?: TenantContext) {
  return apiClient.request<AgentAuditEvent[]>(`/agents/${encodeURIComponent(agentId)}/audit`, {
    tenantContext
  });
}

export function createAgentRegistrationDraft(
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<AgentDetail | AgentSummary>("/agents/registration-drafts", {
    method: "POST",
    body,
    tenantContext
  });
}

export function updateAgentRegistrationDraft(
  draftId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<AgentDetail | AgentSummary>(
    `/agents/registration-drafts/${encodeURIComponent(draftId)}`,
    { method: "PATCH", body, tenantContext }
  );
}

export function createAgentIdentity(draftId: string, tenantContext?: TenantContext) {
  return apiClient.request<Record<string, unknown>>(
    `/agents/registration-drafts/${encodeURIComponent(draftId)}/identity`,
    { method: "POST", tenantContext }
  );
}

export function simulateAgentRegistrationDraft(draftId: string, tenantContext?: TenantContext) {
  return apiClient.request<Record<string, unknown>>(
    `/agents/registration-drafts/${encodeURIComponent(draftId)}/simulate`,
    { method: "POST", tenantContext }
  );
}

export function submitAgentRegistrationDraft(draftId: string, tenantContext?: TenantContext) {
  return apiClient.request<AgentSummary>(
    `/agents/registration-drafts/${encodeURIComponent(draftId)}/submit`,
    { method: "POST", tenantContext }
  );
}

export function approveAgent(
  agentId: string,
  body: Record<string, unknown> = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<AgentSummary>(`/agents/${encodeURIComponent(agentId)}/approve`, {
    method: "POST",
    body,
    tenantContext
  });
}

export function activateAgent(
  agentId: string,
  body: Record<string, unknown> = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<AgentSummary>(`/agents/${encodeURIComponent(agentId)}/activate`, {
    method: "POST",
    body,
    tenantContext
  });
}

export function runLifecycleAction(
  agentId: string,
  action: "reject" | "suspend" | "resume" | "change-owner" | "decommission" | "heartbeat",
  body: Record<string, unknown> = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<AgentSummary>(`/agents/${encodeURIComponent(agentId)}/${action}`, {
    method: "POST",
    body,
    tenantContext
  });
}

export function runOrphanDetection(tenantContext?: TenantContext) {
  return apiClient.request<Record<string, unknown>>("/agents/orphan-detection/run", {
    method: "POST",
    tenantContext
  });
}

export function listAgentCredentials(
  agentId: string,
  params: AgentListParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<AgentCredential[]>(
    `/agents/${encodeURIComponent(agentId)}/credentials${queryString(params)}`,
    { tenantContext }
  );
}

export function issueAgentCredential(
  agentId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Record<string, unknown>>(
    `/agents/${encodeURIComponent(agentId)}/credentials`,
    { method: "POST", body, tenantContext }
  );
}

export function rotateCredential(
  credentialId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Record<string, unknown>>(
    `/credentials/${encodeURIComponent(credentialId)}/rotate`,
    { method: "POST", body, tenantContext }
  );
}

export function revokeCredential(
  credentialId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Record<string, unknown>>(
    `/credentials/${encodeURIComponent(credentialId)}/revoke`,
    { method: "POST", body, tenantContext }
  );
}

export function verifyCredential(
  credentialId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<Record<string, unknown>>(
    `/credentials/${encodeURIComponent(credentialId)}/verify`,
    { method: "POST", body, tenantContext }
  );
}

export function listExpiringCredentials(
  params: AgentListParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<AgentCredential[]>(`/credentials/expiring${queryString(params)}`, {
    tenantContext
  });
}

export function useAgents(params: AgentListParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["agents", params], scope),
    queryFn: () => listAgents(params, scope.context)
  });
}

export function useAgentDetail(agentId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(agentId),
    queryKey: scopedQueryKey(["agents", agentId, "detail"], scope),
    queryFn: () => getAgent(agentId as string, scope.context)
  });
}

export function useAgentTimeline(agentId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(agentId),
    queryKey: scopedQueryKey(["agents", agentId, "timeline"], scope),
    queryFn: () => getAgentTimeline(agentId as string, scope.context)
  });
}

export function useAgentAudit(agentId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(agentId),
    queryKey: scopedQueryKey(["agents", agentId, "audit"], scope),
    queryFn: () => getAgentAudit(agentId as string, scope.context)
  });
}

export function useAgentCredentials(agentId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(agentId),
    queryKey: scopedQueryKey(["agents", agentId, "credentials"], scope),
    queryFn: () => listAgentCredentials(agentId as string, {}, scope.context)
  });
}

export function useExpiringCredentials() {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["credentials", "expiring"], scope),
    queryFn: () => listExpiringCredentials({ threshold_hours: 24 }, scope.context)
  });
}

export function useAgentMutation() {
  const queryClient = useQueryClient();
  const scope = useTenantQueryScope();
  return useMutation({
    mutationFn: async (task: (tenantContext: TenantContext) => Promise<unknown>) =>
      task(scope.context),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["agents"], scope) });
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["credentials"], scope) });
    }
  });
}
