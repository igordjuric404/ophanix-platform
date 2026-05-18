import {
  createContext,
  createElement,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode
} from "react";

import { getApiTenantContext, subscribeApiTenantContext, type TenantContext } from "./client";

export interface TenantQueryScope {
  context: TenantContext;
  key: {
    organizationId: string;
    environmentId: string;
  };
}

const emptyTenantScope = "__none__";
const TenantQueryScopeContext = createContext<TenantContext | null>(null);

export function tenantQueryScopeKey(context: TenantContext): TenantQueryScope["key"] {
  return {
    organizationId: context.organizationId ?? emptyTenantScope,
    environmentId: context.environmentId ?? emptyTenantScope
  };
}

export function scopedQueryKey(baseKey: readonly unknown[], scope: TenantQueryScope) {
  return ["tenant-scope", scope.key, ...baseKey] as const;
}

export function TenantQueryScopeProvider({
  children,
  context
}: {
  children: ReactNode;
  context: TenantContext;
}) {
  return createElement(TenantQueryScopeContext.Provider, { value: context }, children);
}

export function useTenantQueryScope(): TenantQueryScope {
  const providedContext = useContext(TenantQueryScopeContext);
  const externalContext = useSyncExternalStore(
    subscribeApiTenantContext,
    getApiTenantContext,
    getApiTenantContext
  );
  const context = providedContext ?? externalContext;

  return useMemo(
    () => ({
      context,
      key: tenantQueryScopeKey(context)
    }),
    [context]
  );
}
