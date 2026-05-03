import {
  Navigate,
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  useLocation
} from "@tanstack/react-router";

import { LoginScreen } from "../components/auth/LoginScreen";
import { RequireAuth } from "../components/auth/RequireAuth";
import { AppShell } from "../components/layout/AppShell";
import { AgentsPage } from "../features/agents/AgentsPage";
import { CompliancePage } from "../features/compliance/CompliancePage";
import { DiscoveryPage } from "../features/discovery/DiscoveryPage";
import { MeshPage } from "../features/mesh/MeshPage";
import { OverviewPage } from "../features/overview/OverviewPage";
import { PoliciesPage } from "../features/policies/PoliciesPage";
import { AccessDeniedPage } from "../features/shared/AccessDeniedPage";
import { FeaturePlaceholderPage } from "../features/shared/FeaturePlaceholderPage";
import { TrustPage } from "../features/trust/TrustPage";
import { canAccessRoute } from "../lib/rbac";
import { routeRegistry } from "../lib/routes";

function ProtectedLayout() {
  const location = useLocation();

  return (
    <RequireAuth>
      {(user) => (
        <AppShell user={user}>
          {canAccessRoute(location.pathname, user) ? (
            <Outlet />
          ) : (
            <AccessDeniedPage path={location.pathname} />
          )}
        </AppShell>
      )}
    </RequireAuth>
  );
}

const rootRoute = createRootRoute({
  component: Outlet,
  notFoundComponent: () => (
    <RequireAuth>
      {(user) => (
        <AppShell user={user}>
          <FeaturePlaceholderPage
            title="Page not found"
            description="The requested governance workspace is not registered."
            status="Unavailable"
          />
        </AppShell>
      )}
    </RequireAuth>
  )
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <Navigate to="/overview" />
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginScreen
});

const protectedRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "protected",
  component: ProtectedLayout
});

const overviewRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/overview",
  component: OverviewPage
});

const agentsRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/agents",
  component: AgentsPage
});

const discoveryRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/discovery",
  component: DiscoveryPage
});

const policiesRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/policies",
  component: PoliciesPage
});

const complianceRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/compliance",
  component: CompliancePage
});

const trustRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/trust",
  component: TrustPage
});

const meshRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/mesh",
  component: MeshPage
});

const featureRoutes = routeRegistry
  .filter(
    (route) =>
      route.path !== "/overview" &&
      route.path !== "/agents" &&
      route.path !== "/discovery" &&
      route.path !== "/policies" &&
      route.path !== "/compliance" &&
      route.path !== "/trust" &&
      route.path !== "/mesh"
  )
  .map((route) =>
    createRoute({
      getParentRoute: () => protectedRoute,
      path: route.path,
      component: () => (
        <FeaturePlaceholderPage
          title={route.label}
          description={route.description}
          status="Ready for feature migration"
        />
      )
    })
  );

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  protectedRoute.addChildren([
    overviewRoute,
    agentsRoute,
    discoveryRoute,
    policiesRoute,
    complianceRoute,
    trustRoute,
    meshRoute,
    ...featureRoutes
  ])
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
