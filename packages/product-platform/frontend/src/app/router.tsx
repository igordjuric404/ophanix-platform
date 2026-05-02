import {
  Navigate,
  Outlet,
  createRootRoute,
  createRoute,
  createRouter
} from "@tanstack/react-router";

import { LoginScreen } from "../components/auth/LoginScreen";
import { RequireAuth } from "../components/auth/RequireAuth";
import { AppShell } from "../components/layout/AppShell";
import { OverviewPage } from "../features/overview/OverviewPage";
import { FeaturePlaceholderPage } from "../features/shared/FeaturePlaceholderPage";
import { routeRegistry } from "../lib/routes";

function ProtectedLayout() {
  return (
    <RequireAuth>
      {(user) => (
        <AppShell user={user}>
          <Outlet />
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

const featureRoutes = routeRegistry
  .filter((route) => route.path !== "/overview")
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
  protectedRoute.addChildren([overviewRoute, ...featureRoutes])
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

