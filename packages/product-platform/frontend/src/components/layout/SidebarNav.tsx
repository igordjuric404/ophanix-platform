import { Link, useLocation } from "@tanstack/react-router";

import type { UserPrincipal } from "../../api/types";
import { canAccessRoute } from "../../lib/rbac";
import { routeGroups } from "../../lib/routes";
import { cn } from "../../lib/utils";

export function SidebarNav({ user }: { user: UserPrincipal }) {
  const location = useLocation();
  const groups = routeGroups();

  return (
    <nav aria-label="Product navigation" className="space-y-5">
      {groups.map((group) => (
        <section key={group.area}>
          <h2 className="px-3 text-xs font-semibold uppercase text-muted-foreground">
            {group.area}
          </h2>
          <div className="mt-2 space-y-1">
            {group.routes.map((route) => {
              const active = location.pathname === route.path;
              const allowed = canAccessRoute(route.path, user);
              if (!allowed) {
                return (
                  <span
                    aria-disabled="true"
                    className="block rounded-md px-3 py-2 text-sm text-muted-foreground opacity-45"
                    data-route-disabled={route.path}
                    key={route.path}
                  >
                    {route.label}
                  </span>
                );
              }
              return (
                <Link
                  activeOptions={{ exact: true }}
                  className={cn(
                    "block rounded-md px-3 py-2 text-sm transition-colors",
                    active
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                  data-route={route.path}
                  key={route.path}
                  to={route.path}
                >
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
