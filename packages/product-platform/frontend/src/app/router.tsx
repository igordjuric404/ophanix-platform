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
import { DemoLabPage } from "../features/demo/DemoLabPage";
import { DiscoveryPage } from "../features/discovery/DiscoveryPage";
import { IntegrationsPage } from "../features/integrations/IntegrationsPage";
import { MeshPage } from "../features/mesh/MeshPage";
import { McpPage } from "../features/mcp/McpPage";
import { MarketplacePage } from "../features/marketplace/MarketplacePage";
import { ObservabilityPage } from "../features/observability/ObservabilityPage";
import { OverviewPage } from "../features/overview/OverviewPage";
import { PoliciesPage } from "../features/policies/PoliciesPage";
import { RuntimePage } from "../features/runtime/RuntimePage";
import { AccessDeniedPage } from "../features/shared/AccessDeniedPage";
import { FeaturePlaceholderPage } from "../features/shared/FeaturePlaceholderPage";
import { TrustPage } from "../features/trust/TrustPage";
import { WorkflowsPage } from "../features/workflows/WorkflowsPage";
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

const mcpRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/mcp",
  component: McpPage
});

const runtimeRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/runtime",
  component: RuntimePage
});

const marketplaceRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/marketplace",
  component: MarketplacePage
});

const observabilityRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/observability",
  component: ObservabilityPage
});

const integrationsRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/integrations",
  component: IntegrationsPage
});

const workflowsRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/workflows",
  component: WorkflowsPage
});

const demoLabRoute = createRoute({
  getParentRoute: () => protectedRoute,
  path: "/demo-lab",
  component: DemoLabPage
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
      route.path !== "/mesh" &&
      route.path !== "/mcp" &&
      route.path !== "/runtime" &&
      route.path !== "/marketplace" &&
      route.path !== "/observability" &&
      route.path !== "/integrations" &&
      route.path !== "/workflows" &&
      route.path !== "/demo-lab"
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
    mcpRoute,
    runtimeRoute,
    marketplaceRoute,
    observabilityRoute,
    integrationsRoute,
    workflowsRoute,
    demoLabRoute,
    ...featureRoutes
  ])
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
