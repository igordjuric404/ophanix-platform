export const selectedEnvironmentStorageKey = "ophanix.selectedEnvironmentId";

export interface TenantStorageScope {
  organizationId?: string | null;
  userId?: string | null;
}

export function selectedEnvironmentStorageKeyFor(scope: TenantStorageScope = {}) {
  const userId = sanitizeStorageScopePart(scope.userId ?? "anonymous");
  const organizationId = sanitizeStorageScopePart(scope.organizationId ?? "no-organization");
  return `${selectedEnvironmentStorageKey}.${userId}.${organizationId}`;
}

export function readSelectedEnvironmentId(
  storage: Storage = window.localStorage,
  scope: TenantStorageScope = {}
) {
  const scopedValue = storage.getItem(selectedEnvironmentStorageKeyFor(scope));
  if (scopedValue) {
    return scopedValue;
  }
  return storage.getItem(selectedEnvironmentStorageKey);
}

export function writeSelectedEnvironmentId(
  environmentId: string,
  storage: Storage = window.localStorage,
  scope: TenantStorageScope = {}
) {
  storage.setItem(selectedEnvironmentStorageKeyFor(scope), environmentId);
}

function sanitizeStorageScopePart(value: string) {
  return value.trim().replace(/[^a-zA-Z0-9_.:-]+/g, "_") || "unknown";
}
