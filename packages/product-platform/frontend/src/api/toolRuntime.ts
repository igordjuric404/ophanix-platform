import { useQuery } from "@tanstack/react-query";

import { apiClient, queryString } from "./client";

export type ToolRuntimeParams = Record<string, string | number | boolean | null | undefined>;

export interface ToolRuntimeActionEvent {
  id: string;
  runtime_action_id: string;
  event_type: string;
  event_summary: Record<string, unknown>;
  created_at: string;
}

export interface ToolRuntimeAction {
  id: string;
  organization_id: string;
  environment_id: string;
  request_id: string;
  correlation_id?: string | null;
  agent_id?: string | null;
  credential_id?: string | null;
  tool_id?: string | null;
  permission_id?: string | null;
  decision_id?: string | null;
  action_status: string;
  reason_code?: string | null;
  upstream_status_code?: number | null;
  latency_ms?: number | null;
  payload_summary: Record<string, unknown>;
  response_summary?: Record<string, unknown> | null;
  redaction_applied: boolean;
  error_code?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ToolRuntimeActionDetail extends ToolRuntimeAction {
  events: ToolRuntimeActionEvent[];
}

export function listToolRuntimeActions(params: ToolRuntimeParams = {}) {
  return apiClient.request<ToolRuntimeAction[]>(
    `/tool-runtime/actions${queryString(params)}`
  );
}

export function getToolRuntimeAction(actionId: string) {
  return apiClient.request<ToolRuntimeActionDetail>(
    `/tool-runtime/actions/${encodeURIComponent(actionId)}`
  );
}

export function useToolRuntimeActions(params: ToolRuntimeParams = {}) {
  return useQuery({
    queryKey: ["tool-runtime", "actions", params],
    queryFn: () => listToolRuntimeActions(params)
  });
}

export function useToolRuntimeActionDetail(actionId: string | null) {
  return useQuery({
    enabled: Boolean(actionId),
    queryKey: ["tool-runtime", "actions", actionId],
    queryFn: () => getToolRuntimeAction(actionId as string)
  });
}
