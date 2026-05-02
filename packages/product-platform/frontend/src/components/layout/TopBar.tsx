import { LogOut, ShieldCheck } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";

import { useLogout } from "../../api/auth";
import type { UserPrincipal } from "../../api/types";
import { Button } from "../ui/button";

export function TopBar({ user }: { user: UserPrincipal }) {
  const logout = useLogout();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout.mutateAsync();
    await navigate({ to: "/login" });
  }

  return (
    <div className="flex h-14 items-center justify-between border-b bg-background px-6">
      <div className="flex items-center gap-2 text-sm font-medium">
        <ShieldCheck className="h-4 w-4 text-primary" />
        Agent Governance Control Plane
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right text-sm">
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

