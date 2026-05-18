import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { apiClient, setApiTenantContext } from "./client";
import type { AuthResponse, DevLoginRequest, UserPrincipal } from "./types";

export const currentUserQueryKey = ["auth", "me"] as const;

export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserQueryKey,
    queryFn: () => apiClient.request<UserPrincipal>("/auth/me"),
    retry: false
  });
}

export function useDevLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: DevLoginRequest) =>
      apiClient.request<AuthResponse>("/auth/dev-login", {
        method: "POST",
        body: body as unknown as BodyInit
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
    mutationFn: () => apiClient.request<null>("/auth/logout", { method: "POST" }),
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
