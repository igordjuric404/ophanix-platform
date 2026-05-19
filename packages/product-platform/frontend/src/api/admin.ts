import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient, type TenantContext } from "./client";
import { scopedQueryKey, useTenantQueryScope } from "./queryScope";
import type {
  ApiKey,
  ApiKeyCreateRequest,
  ApiKeyCreateResponse,
  Environment,
  EnvironmentCreateRequest
} from "./types";

export function createEnvironment(body: EnvironmentCreateRequest, tenantContext?: TenantContext) {
  return apiClient.request<Environment>("/environments", {
    method: "POST",
    body,
    tenantContext
  });
}

export function listApiKeys(tenantContext?: TenantContext, signal?: AbortSignal) {
  return apiClient.request<ApiKey[]>("/api-keys", {
    signal,
    tenantContext
  });
}

export function createApiKey(body: ApiKeyCreateRequest, tenantContext?: TenantContext) {
  return apiClient.request<ApiKeyCreateResponse>("/api-keys", {
    method: "POST",
    body,
    tenantContext
  });
}

export function revokeApiKey(keyId: string, tenantContext?: TenantContext) {
  return apiClient.request<null>(`/api-keys/${encodeURIComponent(keyId)}`, {
    method: "DELETE",
    tenantContext
  });
}

export function useApiKeys() {
  const scope = useTenantQueryScope();
  return useQuery({
    queryKey: scopedQueryKey(["admin", "api-keys"], scope),
    queryFn: ({ signal }) => listApiKeys(scope.context, signal)
  });
}

export function useAdminMutation() {
  const queryClient = useQueryClient();
  const scope = useTenantQueryScope();

  return useMutation({
    mutationFn: (task: (tenantContext: TenantContext) => Promise<unknown>) => task(scope.context),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: scopedQueryKey(["admin"], scope) }),
        queryClient.invalidateQueries({ queryKey: scopedQueryKey(["admin", "api-keys"], scope) }),
        queryClient.invalidateQueries({ queryKey: ["tenant", "environments"] })
      ]);
    }
  });
}
