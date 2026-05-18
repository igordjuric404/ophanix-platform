import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";

export type MeshParams = Record<string, string | number | boolean | null | undefined>;

export interface MeshMessage {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  source_agent_id: string;
  target_agent_id: string;
  source_agent_name?: string | null;
  target_agent_name?: string | null;
  source_trust_tier?: string | null;
  target_trust_tier?: string | null;
  protocol: string;
  action: string;
  decision: string;
  latency_ms: number;
  correlation_id?: string | null;
  payload_summary?: Record<string, unknown>;
  created_at: string;
}

export interface MeshHandoff {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  source_agent_id: string;
  target_agent_id: string;
  source_agent_name?: string | null;
  target_agent_name?: string | null;
  task_type: string;
  required_capabilities?: string[];
  trust_result: string;
  policy_result: string;
  status: string;
  reason: string;
  correlation_id?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface MeshTopologyNode {
  agent_id: string;
  name?: string | null;
  status?: string | null;
  trust_tier?: string | null;
  message_count?: number;
}

export interface MeshTopologyEdge {
  source_agent_id: string;
  target_agent_id: string;
  protocol: string;
  volume: number;
  denied_count: number;
  deny_rate: number;
  average_latency_ms: number;
}

export interface MeshTopology {
  nodes: MeshTopologyNode[];
  edges: MeshTopologyEdge[];
  message_count: number;
  generated_at?: string | null;
  cached?: boolean;
}

export interface ProtocolBridgeRoute {
  id: string;
  bridge_id: string;
  source_protocol: string;
  target_protocol: string;
  source_agent_id?: string | null;
  target_agent_id?: string | null;
  source_agent_name?: string | null;
  target_agent_name?: string | null;
  policy_binding_id?: string | null;
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ProtocolBridgeHealthCheck {
  id: string;
  bridge_id: string;
  status: string;
  latency_ms: number;
  message: string;
  checked_at: string;
}

export interface ProtocolBridge {
  id: string;
  organization_id?: string | null;
  environment_id?: string | null;
  name: string;
  bridge_type: string;
  status: string;
  config?: Record<string, unknown>;
  current_health?: ProtocolBridgeHealthCheck | null;
  routes?: ProtocolBridgeRoute[];
  created_at?: string | null;
  updated_at?: string | null;
}

export function createMeshMessage(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<MeshMessage>("/mesh/messages", { method: "POST", body, tenantContext });
}

export function listMeshMessages(params: MeshParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<MeshMessage[]>(`/mesh/messages${queryString(params)}`, {
    tenantContext
  });
}

export function createMeshHandoff(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<MeshHandoff>("/mesh/handoffs", { method: "POST", body, tenantContext });
}

export function listMeshHandoffs(params: MeshParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<MeshHandoff[]>(`/mesh/handoffs${queryString(params)}`, {
    tenantContext
  });
}

export function getMeshTopology(params: MeshParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<MeshTopology>(`/mesh/topology${queryString(params)}`, {
    tenantContext
  });
}

export function createProtocolBridge(body: Record<string, unknown>, tenantContext?: TenantContext) {
  return apiClient.request<ProtocolBridge>("/mesh/protocol-bridges", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listProtocolBridges(params: MeshParams = {}, tenantContext?: TenantContext) {
  return apiClient.request<ProtocolBridge[]>(`/mesh/protocol-bridges${queryString(params)}`, {
    tenantContext
  });
}

export function getProtocolBridge(bridgeId: string, tenantContext?: TenantContext) {
  return apiClient.request<ProtocolBridge>(
    `/mesh/protocol-bridges/${encodeURIComponent(bridgeId)}`,
    { tenantContext }
  );
}

export function patchProtocolBridge(
  bridgeId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<ProtocolBridge>(
    `/mesh/protocol-bridges/${encodeURIComponent(bridgeId)}`,
    { method: "PATCH", body, tenantContext }
  );
}

export function createProtocolBridgeRoute(
  bridgeId: string,
  body: Record<string, unknown>,
  tenantContext?: TenantContext
) {
  return apiClient.request<ProtocolBridgeRoute>(
    `/mesh/protocol-bridges/${encodeURIComponent(bridgeId)}/routes`,
    { method: "POST", body, tenantContext }
  );
}

export function runProtocolBridgeHealthCheck(bridgeId: string, tenantContext?: TenantContext) {
  return apiClient.request<ProtocolBridgeHealthCheck>(
    `/mesh/protocol-bridges/${encodeURIComponent(bridgeId)}/health-check`,
    { method: "POST", tenantContext }
  );
}

export function useMeshMessages(params: MeshParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["mesh", "messages", params], scope),
    queryFn: () => listMeshMessages(params, scope.context)
  });
}

export function useMeshHandoffs(params: MeshParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["mesh", "handoffs", params], scope),
    queryFn: () => listMeshHandoffs(params, scope.context)
  });
}

export function useMeshTopology(params: MeshParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["mesh", "topology", params], scope),
    queryFn: () => getMeshTopology(params, scope.context)
  });
}

export function useProtocolBridges(params: MeshParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["mesh", "protocol-bridges", params], scope),
    queryFn: () => listProtocolBridges(params, scope.context)
  });
}

export function useProtocolBridgeDetail(bridgeId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(bridgeId),
    queryKey: scopedQueryKey(["mesh", "protocol-bridges", bridgeId], scope),
    queryFn: () => getProtocolBridge(bridgeId as string, scope.context)
  });
}

export function useMeshMutation() {
  const queryClient = useQueryClient();
  const scope = useTenantQueryScope();
  return useMutation({
    mutationFn: async (task: (tenantContext: TenantContext) => Promise<unknown>) =>
      task(scope.context),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["mesh"], scope) });
      void queryClient.invalidateQueries({ queryKey: scopedQueryKey(["agents"], scope) });
    }
  });
}
