import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./client";
import type { Environment, Organization, SystemDependency, VersionInfo } from "./types";

export function useSystemDependencies() {
  return useQuery({
    queryKey: ["system", "dependencies"],
    queryFn: () => apiClient.request<SystemDependency[]>("/system/dependencies")
  });
}

export function useVersionInfo() {
  return useQuery({
    queryKey: ["system", "version"],
    queryFn: () => apiClient.request<VersionInfo>("/version")
  });
}

export function useOrganizations() {
  return useQuery({
    queryKey: ["tenant", "organizations"],
    queryFn: () => apiClient.request<Organization[]>("/organizations")
  });
}

export function useEnvironments() {
  return useQuery({
    queryKey: ["tenant", "environments"],
    queryFn: () => apiClient.request<Environment[]>("/environments")
  });
}

