export interface ProductRoute {
  path: string;
  label: string;
  area:
    | "Command"
    | "Governance"
    | "Security"
    | "Operations"
    | "Ecosystem"
    | "Assurance"
    | "Automation"
    | "Administration";
  description: string;
}

export const defaultRoute = "/overview";
export const loginRoute = "/login";

export const routeRegistry: ProductRoute[] = [
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

export function routeGroups() {
  const groups = new Map<ProductRoute["area"], ProductRoute[]>();
  for (const route of routeRegistry) {
    groups.set(route.area, [...(groups.get(route.area) ?? []), route]);
  }
  return Array.from(groups, ([area, routes]) => ({ area, routes }));
}

