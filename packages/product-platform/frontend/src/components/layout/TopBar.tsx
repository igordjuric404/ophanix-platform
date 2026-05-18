import { LogOut, ShieldCheck } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";

import type { TenantSelection } from "../../app/tenantContext";
import { useLogout } from "../../api/auth";
import type { UserPrincipal } from "../../api/types";
import { Button } from "../ui/button";
import { EnvironmentSelector } from "./EnvironmentSelector";
import { NotificationCenter } from "./NotificationCenter";
import { SystemStatusIndicator } from "./SystemStatusIndicator";
import { ThemeToggle } from "./ThemeToggle";

export function TopBar({ tenant, user }: { tenant: TenantSelection; user: UserPrincipal }) {
  const logout = useLogout();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout.mutateAsync();
    await navigate({ to: "/login" });
  }

  return (
    <div className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border/80 bg-background/90 px-4 backdrop-blur-xl lg:px-6">
      <div className="flex min-w-0 items-center gap-2 text-sm font-medium">
        <ShieldCheck className="h-4 w-4 text-primary" />
        <span className="hidden truncate sm:inline">Agent Governance Control Plane</span>
        <span className="sm:hidden">Ophanix</span>
      </div>
      <div className="flex items-center gap-2 sm:gap-3">
        <EnvironmentSelector tenant={tenant} />
        <SystemStatusIndicator />
        <NotificationCenter />
        <ThemeToggle />
        <div className="hidden text-right text-sm sm:block">
          <div className="font-medium">{user.display_name}</div>
          <div className="text-xs text-muted-foreground">{user.roles.join(", ")}</div>
        </div>
        <Button
          aria-label="Sign out"
          className="h-9 w-9 p-0"
          disabled={logout.isPending}
          onClick={handleLogout}
          type="button"
          variant="outline"
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
