import { Check, ChevronDown } from "lucide-react";
import { useId, useRef, useState } from "react";

import type { TenantSelection } from "../../app/tenantContext";
import { Button } from "../ui/button";
import { announceHeaderPopoverOpen, useHeaderPopoverDismiss } from "./headerPopover";

export function EnvironmentSelector({ tenant }: { tenant: TenantSelection }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonId = useId();
  const popoverId = useId();
  const environments = tenant.selectedOrganization
    ? tenant.environments.filter(
        (environment) => environment.organization_id === tenant.selectedOrganization?.id
      )
    : tenant.environments;
  const disabled = tenant.isLoading || environments.length === 0;
  const selectedName = tenant.selectedEnvironment?.name ?? "No environment";

  useHeaderPopoverDismiss({
    id: popoverId,
    onOpenChange: setOpen,
    open,
    rootRef
  });

  function toggleOpen() {
    if (disabled) {
      return;
    }
    setOpen((current) => {
      const next = !current;
      if (next) {
        announceHeaderPopoverOpen(popoverId);
      }
      return next;
    });
  }

  function selectEnvironment(environmentId: string) {
    tenant.setSelectedEnvironmentId(environmentId);
    setOpen(false);
  }

  return (
    <div className="relative hidden md:block" ref={rootRef}>
      <Button
        aria-label={`Environment ${selectedName}`}
        aria-controls={open ? popoverId : undefined}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="h-9 min-w-52 justify-between gap-2 px-3"
        disabled={disabled}
        id={buttonId}
        onClick={toggleOpen}
        type="button"
        variant="outline"
      >
        <span className="flex min-w-0 items-center">
          <span className="truncate">{selectedName}</span>
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
      </Button>
      {open ? (
        <div
          aria-labelledby={buttonId}
          className="absolute right-0 z-30 mt-2 w-64 rounded-lg border border-border/80 bg-card p-1 text-sm shadow-[var(--shadow-popover)]"
          id={popoverId}
          role="listbox"
        >
          {environments.map((environment) => (
            <button
              aria-selected={tenant.selectedEnvironment?.id === environment.id}
              className="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:bg-accent focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/20"
              key={environment.id}
              onClick={() => selectEnvironment(environment.id)}
              role="option"
              type="button"
            >
              <span className="truncate">{environment.name}</span>
              {tenant.selectedEnvironment?.id === environment.id ? (
                <Check className="h-4 w-4 text-primary" />
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
