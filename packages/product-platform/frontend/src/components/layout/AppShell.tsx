import type { ReactNode } from "react";

import { useTenantSelection } from "../../app/tenantContext";
import { DetailDrawerProvider } from "../../app/drawerContext";
import type { UserPrincipal } from "../../api/types";
import { SidebarNav } from "./SidebarNav";
import { TopBar } from "./TopBar";

export function AppShell({ children, user }: { children: ReactNode; user: UserPrincipal }) {
  const tenant = useTenantSelection(user);

  return (
    <div className="min-h-screen bg-canvas text-foreground">
      <div className="fixed inset-x-0 top-0 z-50 h-0.5 bg-gradient-to-r from-brand-warm via-brand-cream to-brand-teal" />
      <aside className="fixed inset-y-0 left-0 hidden w-72 overflow-y-auto border-r border-sidebar-foreground/10 bg-sidebar px-4 py-5 text-sidebar-foreground lg:block">
        <div className="px-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-sidebar-foreground/20 bg-sidebar-foreground text-sidebar">
              <span className="font-display text-lg font-semibold">O</span>
            </div>
            <div>
              <div className="font-display text-lg font-semibold tracking-normal">Ophanix</div>
              <p className="mt-0.5 text-xs leading-4 text-sidebar-muted">
                Agent governance
              </p>
            </div>
          </div>
          <p className="mt-4 text-xs leading-5 text-sidebar-muted">
            Microsoft Agent Governance Toolkit
          </p>
        </div>
        <div className="mt-7">
          <SidebarNav user={user} />
        </div>
      </aside>
      <div className="lg:pl-72">
        <TopBar tenant={tenant} user={user} />
        <div className="border-b border-border/80 bg-background/90 px-4 py-3 backdrop-blur lg:hidden">
          <SidebarNav user={user} variant="mobile" />
        </div>
        <DetailDrawerProvider>
          <main className="min-h-[calc(100vh-4rem)]" tabIndex={-1}>
            {children}
          </main>
        </DetailDrawerProvider>
      </div>
    </div>
  );
}
