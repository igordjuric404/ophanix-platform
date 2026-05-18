import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { apiClient, setApiTenantContext, type TenantContext } from "./client";
import type { AuthResponse, DevLoginRequest, UserPrincipal } from "./types";

export const currentUserQueryKey = ["auth", "me"] as const;
const tenantNeutralContext: TenantContext = { organizationId: null, environmentId: null };

export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserQueryKey,
    queryFn: ({ signal }) =>
      apiClient.request<UserPrincipal>("/auth/me", { signal, tenantContext: tenantNeutralContext }),
    retry: false
  });
}

export function useDevLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: DevLoginRequest) =>
      apiClient.request<AuthResponse>("/auth/dev-login", {
        method: "POST",
        body,
        tenantContext: tenantNeutralContext
      }),
    onSuccess: async (response) => {
      await clearSessionServerState(queryClient);
      queryClient.setQueryData(currentUserQueryKey, response.user);
    }
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.request<null>("/auth/logout", {
        method: "POST",
        tenantContext: tenantNeutralContext
      }),
    onSettled: async () => {
      await clearSessionServerState(queryClient);
    }
  });
}

async function clearSessionServerState(queryClient: QueryClient) {
  await queryClient.cancelQueries();
  setApiTenantContext({ organizationId: null, environmentId: null });
  queryClient.removeQueries();
}
