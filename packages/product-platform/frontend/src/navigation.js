export const DEFAULT_ROUTE = "/overview";
export const LOGIN_ROUTE = "/login";

export const PRODUCT_ROUTES = [
  {
    path: "/overview",
    label: "Overview",
    area: "Command",
    description: "Governed estate summary, activity, risk, and operational signals."
  },
  {
    path: "/agents",
    label: "Agents",
    area: "Governance",
    description: "Inventory, lifecycle, credentials, ownership, and capability requests."
  },
  {
    path: "/policies",
    label: "Policies",
    area: "Governance",
    description: "Policy library, editor, bindings, simulator, approvals, and packs."
  },
  {
    path: "/trust",
    label: "Trust",
    area: "Governance",
    description: "Trust score trends, dimensions, tiers, changes, and explainability."
  },
  {
    path: "/mcp",
    label: "MCP Security",
    area: "Security",
    description: "MCP servers, tools, calls, policy decisions, and blocked activity."
  },
  {
    path: "/mesh",
    label: "Mesh",
    area: "Operations",
    description: "Agent mesh topology, routes, discovery, and cross-agent coordination."
  },
  {
    path: "/runtime",
    label: "Runtime",
    area: "Operations",
    description: "Runtime sessions, sandbox controls, ring decisions, and kill-switches."
  },
  {
    path: "/discovery",
    label: "Discovery",
    area: "Operations",
    description: "Discovery scans, shadow agents, inventory drift, and ownership mapping."
  },
  {
    path: "/marketplace",
    label: "Marketplace",
    area: "Ecosystem",
    description: "Agent and integration catalog, evaluations, install flow, and attestations."
  },
  {
    path: "/compliance",
    label: "Compliance",
    area: "Assurance",
    description: "Controls, evidence, reports, violations, and governance attestations."
  },
  {
    path: "/observability",
    label: "Observability",
    area: "Operations",
    description: "Events, SLOs, incidents, telemetry, cost, and performance health."
  },
  {
    path: "/integrations",
    label: "Integrations",
    area: "Ecosystem",
    description: "Framework adapters, provider connections, webhooks, and API clients."
  },
  {
    path: "/workflows",
    label: "Workflows",
    area: "Automation",
    description: "Workflow catalog, runs, schedules, logs, artifacts, and exports."
  },
  {
    path: "/demo-lab",
    label: "Demo Lab",
    area: "Automation",
    description: "Demo scenarios, seeded environments, scripted checks, and walkthroughs."
  },
  {
    path: "/settings",
    label: "Settings",
    area: "Administration",
    description: "Tenant settings, users, keys, environments, notifications, and platform setup."
  }
];

export function normalizePath(pathname) {
  if (!pathname || pathname === "/") {
    return DEFAULT_ROUTE;
  }
  const withoutTrailingSlash = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return withoutTrailingSlash || DEFAULT_ROUTE;
}

export function findRoute(pathname) {
  const normalized = normalizePath(pathname);
  return PRODUCT_ROUTES.find((route) => route.path === normalized) ?? null;
}

export function routeGroups() {
  const groups = new Map();
  for (const route of PRODUCT_ROUTES) {
    const items = groups.get(route.area) ?? [];
    items.push(route);
    groups.set(route.area, items);
  }
  return Array.from(groups, ([area, routes]) => ({ area, routes }));
}
