import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, queryString } from "./client";

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

export function createMeshMessage(body: Record<string, unknown>) {
  return apiClient.request<MeshMessage>("/mesh/messages", { method: "POST", body });
}

export function listMeshMessages(params: MeshParams = {}) {
  return apiClient.request<MeshMessage[]>(`/mesh/messages${queryString(params)}`);
}

export function createMeshHandoff(body: Record<string, unknown>) {
  return apiClient.request<MeshHandoff>("/mesh/handoffs", { method: "POST", body });
}

export function listMeshHandoffs(params: MeshParams = {}) {
  return apiClient.request<MeshHandoff[]>(`/mesh/handoffs${queryString(params)}`);
}

export function getMeshTopology(params: MeshParams = {}) {
  return apiClient.request<MeshTopology>(`/mesh/topology${queryString(params)}`);
}

export function createProtocolBridge(body: Record<string, unknown>) {
  return apiClient.request<ProtocolBridge>("/mesh/protocol-bridges", { method: "POST", body });
}

export function listProtocolBridges(params: MeshParams = {}) {
  return apiClient.request<ProtocolBridge[]>(`/mesh/protocol-bridges${queryString(params)}`);
}

export function getProtocolBridge(bridgeId: string) {
  return apiClient.request<ProtocolBridge>(
    `/mesh/protocol-bridges/${encodeURIComponent(bridgeId)}`
  );
}

export function patchProtocolBridge(bridgeId: string, body: Record<string, unknown>) {
  return apiClient.request<ProtocolBridge>(
    `/mesh/protocol-bridges/${encodeURIComponent(bridgeId)}`,
    { method: "PATCH", body }
  );
}

export function createProtocolBridgeRoute(bridgeId: string, body: Record<string, unknown>) {
  return apiClient.request<ProtocolBridgeRoute>(
    `/mesh/protocol-bridges/${encodeURIComponent(bridgeId)}/routes`,
    { method: "POST", body }
  );
}

export function runProtocolBridgeHealthCheck(bridgeId: string) {
  return apiClient.request<ProtocolBridgeHealthCheck>(
    `/mesh/protocol-bridges/${encodeURIComponent(bridgeId)}/health-check`,
    { method: "POST" }
  );
}

export function useMeshMessages(params: MeshParams = {}) {
  return useQuery({
    queryKey: ["mesh", "messages", params],
    queryFn: () => listMeshMessages(params)
  });
}

export function useMeshHandoffs(params: MeshParams = {}) {
  return useQuery({
    queryKey: ["mesh", "handoffs", params],
    queryFn: () => listMeshHandoffs(params)
  });
}

export function useMeshTopology(params: MeshParams = {}) {
  return useQuery({
    queryKey: ["mesh", "topology", params],
    queryFn: () => getMeshTopology(params)
  });
}

export function useProtocolBridges(params: MeshParams = {}) {
  return useQuery({
    queryKey: ["mesh", "protocol-bridges", params],
    queryFn: () => listProtocolBridges(params)
  });
}

export function useProtocolBridgeDetail(bridgeId: string | null) {
  return useQuery({
    enabled: Boolean(bridgeId),
    queryKey: ["mesh", "protocol-bridges", bridgeId],
    queryFn: () => getProtocolBridge(bridgeId as string)
  });
}

export function useMeshMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (task: () => Promise<unknown>) => task(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mesh"] });
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
    }
  });
}
