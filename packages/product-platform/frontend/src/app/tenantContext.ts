import { useEffect, useLayoutEffect, useMemo, useState } from "react";

import { useEnvironments, useOrganizations } from "../api/system";
import type { Environment, Organization, UserPrincipal } from "../api/types";
import { setApiTenantContext, type TenantContext } from "../api/client";
import { readSelectedEnvironmentId, writeSelectedEnvironmentId } from "../lib/storage";

export interface TenantSelection {
  organizations: Organization[];
  environments: Environment[];
  selectedOrganization: Organization | null;
  selectedEnvironment: Environment | null;
  tenantContext: TenantContext;
  setSelectedEnvironmentId: (environmentId: string) => void;
  isLoading: boolean;
  isError: boolean;
  isReady: boolean;
  error: Error | null;
}

export function useTenantSelection(user: UserPrincipal): TenantSelection {
  const organizations = useOrganizations();
  const environments = useEnvironments();
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState(() =>
    typeof window === "undefined"
      ? null
      : readSelectedEnvironmentId(window.localStorage, {
          organizationId: user.organization_id,
          userId: user.id
        })
  );

  const organizationItems = organizations.data ?? [];
  const environmentItems = environments.data ?? [];
  const selectedOrganization =
    organizationItems.find((organization) => organization.id === user.organization_id) ??
    organizationItems[0] ??
    null;
  const allowedEnvironmentIds =
    user.environment_ids === undefined ? null : new Set(user.environment_ids);
  const organizationEnvironments = selectedOrganization
    ? environmentItems.filter(
        (environment) =>
          environment.organization_id === selectedOrganization.id &&
          (allowedEnvironmentIds === null || allowedEnvironmentIds.has(environment.id))
      )
    : environmentItems.filter(
        (environment) => allowedEnvironmentIds === null || allowedEnvironmentIds.has(environment.id)
      );
  const selectedEnvironment =
    organizationEnvironments.find((environment) => environment.id === selectedEnvironmentId) ??
    organizationEnvironments[0] ??
    null;

  const apiTenantContext = useMemo(
    () => ({
      organizationId: selectedOrganization?.id ?? user.organization_id ?? null,
      environmentId: selectedEnvironment?.id ?? null
    }),
    [selectedEnvironment?.id, selectedOrganization?.id, user.organization_id]
  );

  useLayoutEffect(() => {
    setApiTenantContext(apiTenantContext);
  }, [apiTenantContext]);

  useEffect(() => {
    if (selectedEnvironment) {
      writeSelectedEnvironmentId(selectedEnvironment.id, window.localStorage, {
        organizationId: selectedOrganization?.id ?? user.organization_id,
        userId: user.id
      });
    }
  }, [selectedEnvironment, selectedOrganization?.id, user.id, user.organization_id]);

  return {
    organizations: organizationItems,
    environments: environmentItems,
    selectedOrganization,
    selectedEnvironment,
    tenantContext: apiTenantContext,
    setSelectedEnvironmentId,
    isLoading: organizations.isLoading || environments.isLoading,
    isError: organizations.isError || environments.isError,
    isReady: Boolean(selectedOrganization && selectedEnvironment),
    error:
      organizations.error instanceof Error
        ? organizations.error
        : environments.error instanceof Error
          ? environments.error
          : null
  };
}
