export const selectedEnvironmentStorageKey = "ophanix.selectedEnvironmentId";

export function readSelectedEnvironmentId(storage: Storage = window.localStorage) {
  return storage.getItem(selectedEnvironmentStorageKey);
}

export function writeSelectedEnvironmentId(
  environmentId: string,
  storage: Storage = window.localStorage
) {
  storage.setItem(selectedEnvironmentStorageKey, environmentId);
}

