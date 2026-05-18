import { useQuery } from "@tanstack/react-query";

import { apiClient, createApiClient } from "./client";
import type { Environment, Organization, SystemDependency, VersionInfo } from "./types";

const rootApiClient = createApiClient({ baseUrl: "" });

export function useSystemDependencies() {
  return useQuery({
    queryKey: ["system", "dependencies"],
    queryFn: ({ signal }) => apiClient.request<SystemDependency[]>("/system/dependencies", { signal })
  });
}

export function useVersionInfo() {
  return useQuery({
    queryKey: ["system", "version"],
    queryFn: ({ signal }) => rootApiClient.request<VersionInfo>("/version", { signal })
  });
}

export function useOrganizations() {
  return useQuery({
    queryKey: ["tenant", "organizations"],
    queryFn: ({ signal }) => apiClient.request<Organization[]>("/organizations", { signal })
  });
}

export function useEnvironments() {
  return useQuery({
    queryKey: ["tenant", "environments"],
    queryFn: ({ signal }) => apiClient.request<Environment[]>("/environments", { signal })
  });
}
