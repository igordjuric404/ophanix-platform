import { LOGIN_ROUTE, normalizePath } from "./navigation.js";
import { ApiClientError } from "./apiClient.js";
import { createClosedDrawerState } from "./drawers.js";
import { canAccessRoute } from "./permissions.js";

export const STORAGE_ENVIRONMENT_KEY = "ophanix.selectedEnvironmentId";

export function createInitialAppState(overrides = {}) {
  return {
    authStatus: "authenticated",
    currentUser: {
      id: "local-placeholder",
      display_name: "Local User",
      email: "local@ophanix.dev",
      roles: ["Platform Admin"],
      organization_id: "org_default"
    },
    organizations: [
      {
        id: "org_default",
        name: "Ophanix Demo",
        slug: "ophanix-demo"
      }
    ],
    environments: [
      {
        id: "env_default",
        organization_id: "org_default",
        name: "Development",
        slug: "development",
        type: "development"
      }
    ],
    selectedOrganization: {
      id: "org_default",
      name: "Ophanix Demo",
      slug: "ophanix-demo"
    },
    selectedEnvironment: {
      id: "env_default",
      organization_id: "org_default",
      name: "Development",
      slug: "development",
      type: "development"
    },
    systemStatus: {
      status: "healthy",
      dependencies: [],
      version: null,
      message: "No dependency checks have reported issues."
    },
    notifications: [],
    drawer: createClosedDrawerState(),
    loadError: null,
    ...overrides
  };
}

export function createLoadingState() {
  return createInitialAppState({
    authStatus: "loading",
    currentUser: null,
    organizations: [],
    environments: [],
    selectedOrganization: null,
    selectedEnvironment: null
  });
}

export function createUnauthenticatedState() {
  return createInitialAppState({
    authStatus: "unauthenticated",
    currentUser: null,
    organizations: [],
    environments: [],
    selectedOrganization: null,
    selectedEnvironment: null
  });
}

export function createSystemStatus({ dependencies = [], version = null } = {}) {
  const requiredFailures = dependencies.filter(
    (dependency) => dependency.required && dependency.status !== "healthy"
  );
  const optionalFailures = dependencies.filter(
    (dependency) => !dependency.required && dependency.status !== "healthy"
  );
  const status = requiredFailures.length > 0 || optionalFailures.length > 0 ? "degraded" : "healthy";
  const message =
    status === "healthy"
      ? "All registered dependencies are healthy."
      : `${requiredFailures.length} required and ${optionalFailures.length} optional dependencies need attention.`;

  return { status, dependencies, version, message };
}

export function createSystemWarning(message) {
  return {
    status: "warning",
    dependencies: [],
    version: null,
    message
  };
}

export function createMemoryStorage(initialValues = {}) {
  const values = new Map(Object.entries(initialValues));
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key)
  };
}

export function selectTenant({ currentUser, organizations, environments, storedEnvironmentId }) {
  const selectedOrganization =
    organizations.find((organization) => organization.id === currentUser?.organization_id) ??
    organizations[0] ??
    null;
  const organizationEnvironments = selectedOrganization
    ? environments.filter((environment) => environment.organization_id === selectedOrganization.id)
    : environments;
  const selectedEnvironment =
    organizationEnvironments.find((environment) => environment.id === storedEnvironmentId) ??
    organizationEnvironments[0] ??
    null;

  return { selectedOrganization, selectedEnvironment };
}

export function createAuthenticatedState({ currentUser, organizations, environments, storage }) {
  const { selectedOrganization, selectedEnvironment } = selectTenant({
    currentUser,
    organizations,
    environments,
    storedEnvironmentId: storage?.getItem(STORAGE_ENVIRONMENT_KEY)
  });
  if (selectedEnvironment && storage) {
    storage.setItem(STORAGE_ENVIRONMENT_KEY, selectedEnvironment.id);
  }
  return createInitialAppState({
    authStatus: "authenticated",
    currentUser,
    organizations,
    environments,
    selectedOrganization,
    selectedEnvironment,
    loadError: null
  });
}

export async function loadAppContext({ apiClient, storage }) {
  try {
    const currentUser = await apiClient.getCurrentUser();
    const [organizations, environments] = await Promise.all([
      apiClient.listOrganizations(),
      apiClient.listEnvironments()
    ]);
    return createAuthenticatedState({
      currentUser,
      organizations,
      environments,
      storage
    });
  } catch (error) {
    if (error instanceof ApiClientError && error.status === 401) {
      return createUnauthenticatedState();
    }
    return createInitialAppState({
      authStatus: "error",
      currentUser: null,
      organizations: [],
      environments: [],
      selectedOrganization: null,
      selectedEnvironment: null,
      loadError: error?.message ?? "Unable to load application context."
    });
  }
}

export async function loadSystemStatus({ apiClient }) {
  try {
    const [dependencies, version] = await Promise.all([
      apiClient.listSystemDependencies(),
      apiClient.getVersion()
    ]);
    return createSystemStatus({ dependencies, version });
  } catch (error) {
    return createSystemWarning(error?.message ?? "Unable to load system status.");
  }
}

export function withSystemStatus(state, systemStatus) {
  return {
    ...state,
    systemStatus
  };
}

export function withDrawer(state, drawer) {
  return {
    ...state,
    drawer
  };
}

export function tenantHeaders(state) {
  const headers = {};
  if (state.selectedOrganization?.id) {
    headers["X-Organization-ID"] = state.selectedOrganization.id;
  }
  if (state.selectedEnvironment?.id) {
    headers["X-Environment-ID"] = state.selectedEnvironment.id;
  }
  return headers;
}

export function tenantContext(state) {
  return {
    organizationId: state.selectedOrganization?.id ?? null,
    environmentId: state.selectedEnvironment?.id ?? null
  };
}

export function updateSelectedEnvironment(state, environmentId, storage) {
  const selectedEnvironment =
    state.environments.find((environment) => environment.id === environmentId) ??
    state.selectedEnvironment;
  if (selectedEnvironment && storage) {
    storage.setItem(STORAGE_ENVIRONMENT_KEY, selectedEnvironment.id);
  }
  return {
    ...state,
    selectedEnvironment
  };
}

export function guardRoute(pathname, state) {
  const path = normalizePath(pathname);
  if (state.authStatus === "unauthenticated") {
    return { path: LOGIN_ROUTE, redirected: true, reason: "unauthenticated" };
  }
  if (state.authStatus === "authenticated" && !canAccessRoute(path, state.currentUser)) {
    return { path, redirected: false, reason: "forbidden" };
  }
  return { path, redirected: false, reason: null };
}
