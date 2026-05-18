import { useQuery } from "@tanstack/react-query";

import { apiClient, queryString, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";

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

export function listToolRuntimeActions(
  params: ToolRuntimeParams = {},
  tenantContext?: TenantContext
) {
  return apiClient.request<ToolRuntimeAction[]>(
    `/tool-runtime/actions${queryString(params)}`,
    { tenantContext }
  );
}

export function getToolRuntimeAction(actionId: string, tenantContext?: TenantContext) {
  return apiClient.request<ToolRuntimeActionDetail>(
    `/tool-runtime/actions/${encodeURIComponent(actionId)}`,
    { tenantContext }
  );
}

export function useToolRuntimeActions(params: ToolRuntimeParams = {}) {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["tool-runtime", "actions", params], scope),
    queryFn: () => listToolRuntimeActions(params, scope.context)
  });
}

export function useToolRuntimeActionDetail(actionId: string | null) {
  const scope = useTenantQueryScope();
  return useQuery({
    enabled: Boolean(actionId),
    queryKey: scopedQueryKey(["tool-runtime", "actions", actionId], scope),
    queryFn: () => getToolRuntimeAction(actionId as string, scope.context)
  });
}
