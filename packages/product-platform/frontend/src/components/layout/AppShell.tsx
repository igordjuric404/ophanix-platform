import type { ReactNode } from "react";

import type { UserPrincipal } from "../../api/types";
import { SidebarNav } from "./SidebarNav";
import { TopBar } from "./TopBar";

export function AppShell({ children, user }: { children: ReactNode; user: UserPrincipal }) {
  return (
    <div className="min-h-screen bg-muted/30 text-foreground">
      <aside className="fixed inset-y-0 left-0 hidden w-72 overflow-y-auto border-r bg-background px-4 py-5 lg:block">
        <div className="px-3">
          <div className="text-lg font-semibold">Ophanix</div>
          <p className="mt-1 text-xs text-muted-foreground">
            Microsoft Agent Governance Toolkit
          </p>
        </div>
        <div className="mt-7">
          <SidebarNav />
        </div>
      </aside>
      <div className="lg:pl-72">
        <TopBar user={user} />
        <main className="min-h-[calc(100vh-3.5rem)]" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
