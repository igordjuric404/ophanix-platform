import { Link, useLocation } from "@tanstack/react-router";
import {
  Activity,
  Bot,
  Boxes,
  Compass,
  FileCheck,
  Gauge,
  GitBranch,
  Network,
  Plug,
  ScrollText,
  Settings,
  Shield,
  ShieldCheck,
  Store,
  Workflow,
  type LucideIcon
} from "lucide-react";

import type { UserPrincipal } from "../../api/types";
import { canAccessRoute } from "../../lib/rbac";
import { routeGroups, routeRegistry } from "../../lib/routes";
import { cn } from "../../lib/utils";

const routeIcons: Record<string, LucideIcon> = {
  "/overview": Gauge,
  "/agents": Bot,
  "/discovery": Compass,
  "/policies": ScrollText,
  "/compliance": FileCheck,
  "/trust": ShieldCheck,
  "/mesh": Network,
  "/mcp": Shield,
  "/runtime": Activity,
  "/tool-gateway/decisions": GitBranch,
  "/marketplace": Store,
  "/observability": Boxes,
  "/integrations": Plug,
  "/workflows": Workflow,
  "/demo-lab": Activity,
  "/settings": Settings
};

export function SidebarNav({
  user,
  variant = "sidebar"
}: {
  user: UserPrincipal;
  variant?: "sidebar" | "mobile";
}) {
  const location = useLocation();
  const groups = routeGroups();

  if (variant === "mobile") {
    return (
      <nav aria-label="Product navigation" className="flex gap-2 overflow-x-auto pb-1">
        {routeRegistry.map((route) => {
          const active = location.pathname === route.path;
          const allowed = canAccessRoute(route.path, user);
          const Icon = routeIcons[route.path] ?? Activity;
          if (!allowed) {
            return null;
          }
          return (
            <Link
              activeOptions={{ exact: true }}
              className={cn(
                "inline-flex h-9 shrink-0 items-center gap-2 rounded-md border px-3 text-sm font-medium transition-colors",
                active
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
              data-route={route.path}
              key={route.path}
              to={route.path}
            >
              <Icon className="h-4 w-4" />
              {route.label}
            </Link>
          );
        })}
      </nav>
    );
  }

  return (
    <nav aria-label="Product navigation" className="space-y-5">
      {groups.map((group) => (
        <section key={group.area}>
          <h2 className="px-3 text-xs font-semibold uppercase tracking-[0.12em] text-sidebar-muted/80">
            {group.area}
          </h2>
          <div className="mt-2 space-y-1">
            {group.routes.map((route) => {
              const active = location.pathname === route.path;
              const allowed = canAccessRoute(route.path, user);
              const Icon = routeIcons[route.path] ?? Activity;
              if (!allowed) {
                return (
                  <span
                    aria-disabled="true"
                    className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-sidebar-muted opacity-45"
                    data-route-disabled={route.path}
                    key={route.path}
                  >
                    <Icon className="h-4 w-4" />
                    {route.label}
                  </span>
                );
              }
              return (
                <Link
                  activeOptions={{ exact: true }}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-sidebar-foreground text-sidebar shadow-sm"
                      : "text-sidebar-muted hover:bg-sidebar-foreground/10 hover:text-sidebar-foreground"
                  )}
                  data-route={route.path}
                  key={route.path}
                  to={route.path}
                >
                  <Icon className="h-4 w-4" />
                  {route.label}
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </nav>
  );
}
