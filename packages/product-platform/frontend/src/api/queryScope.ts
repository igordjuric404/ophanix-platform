import { useMemo, useSyncExternalStore } from "react";

import {
  getApiTenantContext,
  subscribeApiTenantContext,
  type TenantContext
} from "./client";

export interface TenantQueryScope {
  context: TenantContext;
  key: {
    organizationId: string;
    environmentId: string;
  };
}

const emptyTenantScope = "__none__";

export function tenantQueryScopeKey(context: TenantContext): TenantQueryScope["key"] {
  return {
    organizationId: context.organizationId ?? emptyTenantScope,
    environmentId: context.environmentId ?? emptyTenantScope
  };
}

export function scopedQueryKey(baseKey: readonly unknown[], scope: TenantQueryScope) {
  return ["tenant-scope", scope.key, ...baseKey] as const;
}

export function useTenantQueryScope(): TenantQueryScope {
  const context = useSyncExternalStore(
    subscribeApiTenantContext,
    getApiTenantContext,
    getApiTenantContext
  );

  return useMemo(
    () => ({
      context,
      key: tenantQueryScopeKey(context)
    }),
    [context]
  );
}
