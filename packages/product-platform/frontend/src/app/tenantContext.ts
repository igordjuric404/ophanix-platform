import { useEffect, useLayoutEffect, useMemo, useState } from "react";

import { useEnvironments, useOrganizations } from "../api/system";
import type { Environment, Organization, UserPrincipal } from "../api/types";
import { setApiTenantContext } from "../api/client";
import { readSelectedEnvironmentId, writeSelectedEnvironmentId } from "../lib/storage";

export interface TenantSelection {
  organizations: Organization[];
  environments: Environment[];
  selectedOrganization: Organization | null;
  selectedEnvironment: Environment | null;
  setSelectedEnvironmentId: (environmentId: string) => void;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
}

export function useTenantSelection(user: UserPrincipal): TenantSelection {
  const organizations = useOrganizations();
  const environments = useEnvironments();
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState(() =>
    typeof window === "undefined" ? null : readSelectedEnvironmentId()
  );

  const organizationItems = organizations.data ?? [];
  const environmentItems = environments.data ?? [];
  const selectedOrganization =
    organizationItems.find((organization) => organization.id === user.organization_id) ??
    organizationItems[0] ??
    null;
  const organizationEnvironments = selectedOrganization
    ? environmentItems.filter(
        (environment) => environment.organization_id === selectedOrganization.id
      )
    : environmentItems;
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
      writeSelectedEnvironmentId(selectedEnvironment.id);
    }
  }, [selectedEnvironment]);

  return {
    organizations: organizationItems,
    environments: environmentItems,
    selectedOrganization,
    selectedEnvironment,
    setSelectedEnvironmentId,
    isLoading: organizations.isLoading || environments.isLoading,
    isError: organizations.isError || environments.isError,
    error:
      organizations.error instanceof Error
        ? organizations.error
        : environments.error instanceof Error
          ? environments.error
          : null
  };
}
