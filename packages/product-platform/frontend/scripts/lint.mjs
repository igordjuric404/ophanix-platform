import { readFile } from "node:fs/promises";
import { PRODUCT_ROUTES, DEFAULT_ROUTE } from "../src/navigation.js";
import { renderShell } from "../src/render.js";

const expectedRoutes = [
  "/overview",
  "/agents",
  "/policies",
  "/trust",
  "/mcp",
  "/mesh",
  "/runtime",
  "/discovery",
  "/marketplace",
  "/compliance",
  "/observability",
  "/integrations",
  "/workflows",
  "/demo-lab",
  "/settings"
];

const failures = [];

if (DEFAULT_ROUTE !== "/overview") {
  failures.push("DEFAULT_ROUTE must be /overview.");
}

const actualRoutes = PRODUCT_ROUTES.map((route) => route.path);
if (JSON.stringify(actualRoutes) !== JSON.stringify(expectedRoutes)) {
  failures.push(`Route list mismatch: ${actualRoutes.join(", ")}`);
}

const uniqueRoutes = new Set(actualRoutes);
if (uniqueRoutes.size !== PRODUCT_ROUTES.length) {
  failures.push("Route paths must be unique.");
}

for (const route of PRODUCT_ROUTES) {
  if (!route.label || !route.area || !route.description) {
    failures.push(`Route ${route.path} is missing display metadata.`);
  }
}

const shell = renderShell({ currentPath: DEFAULT_ROUTE });
for (const route of PRODUCT_ROUTES) {
  if (!shell.includes(`data-route="${route.path}"`)) {
    failures.push(`Shell navigation is missing ${route.path}.`);
  }
}

for (const file of [
  "src/navigation.js",
  "src/agents.js",
  "src/policies.js",
  "src/auditDrawers.js",
  "src/render.js",
  "src/app.js",
  "src/apiClient.js",
  "src/mcp.js",
  "src/drawers.js",
  "src/html.js",
  "src/permissions.js",
  "src/state.js",
  "src/styles.css"
]) {
  const contents = await readFile(new URL(`../${file}`, import.meta.url), "utf8");
  if (contents.includes("\t")) {
    failures.push(`${file} contains tab characters.`);
  }
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exit(1);
}

console.log(`frontend lint ok: ${PRODUCT_ROUTES.length} routes`);
