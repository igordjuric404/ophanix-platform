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
import { DiscoveryPage } from "../features/discovery/DiscoveryPage";
import { OverviewPage } from "../features/overview/OverviewPage";
import { AccessDeniedPage } from "../features/shared/AccessDeniedPage";
import { FeaturePlaceholderPage } from "../features/shared/FeaturePlaceholderPage";
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

const featureRoutes = routeRegistry
  .filter(
    (route) => route.path !== "/overview" && route.path !== "/agents" && route.path !== "/discovery"
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
  protectedRoute.addChildren([overviewRoute, agentsRoute, discoveryRoute, ...featureRoutes])
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
