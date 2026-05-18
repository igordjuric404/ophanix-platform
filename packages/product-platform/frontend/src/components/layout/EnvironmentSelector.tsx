import { Check, ChevronDown } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import type { TenantSelection } from "../../app/tenantContext";
import { Button } from "../ui/button";
import { announceHeaderPopoverOpen, useHeaderPopoverDismiss } from "./headerPopover";

export function EnvironmentSelector({ tenant }: { tenant: TenantSelection }) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const buttonId = useId();
  const popoverId = useId();
  const environments = tenant.selectedOrganization
    ? tenant.environments.filter(
        (environment) => environment.organization_id === tenant.selectedOrganization?.id
      )
    : tenant.environments;
  const disabled = tenant.isLoading || environments.length === 0;
  const selectedName = tenant.selectedEnvironment?.name ?? "No environment";
  const selectedIndex = Math.max(
    environments.findIndex((environment) => environment.id === tenant.selectedEnvironment?.id),
    0
  );

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
    const next = !open;
    if (next) {
      setActiveIndex(selectedIndex);
      announceHeaderPopoverOpen(popoverId);
    }
    setOpen(next);
  }

  function selectEnvironment(environmentId: string) {
    tenant.setSelectedEnvironmentId(environmentId);
    setOpen(false);
  }

  function openAndFocusSelected() {
    if (disabled) {
      return;
    }
    setActiveIndex(selectedIndex);
    setOpen(true);
    announceHeaderPopoverOpen(popoverId);
  }

  function moveActiveOption(nextIndex: number) {
    const boundedIndex = Math.max(0, Math.min(nextIndex, environments.length - 1));
    setActiveIndex(boundedIndex);
    optionRefs.current[boundedIndex]?.focus();
  }

  useEffect(() => {
    if (!open) {
      return;
    }
    const frameId = window.requestAnimationFrame(() =>
      optionRefs.current[selectedIndex]?.focus()
    );
    return () => window.cancelAnimationFrame(frameId);
  }, [open, selectedIndex]);

  return (
    <div className="relative block" ref={rootRef}>
      <Button
        aria-label={`Environment ${selectedName}`}
        aria-controls={open ? popoverId : undefined}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="h-9 w-36 justify-between gap-2 px-3 sm:w-auto sm:min-w-52"
        disabled={disabled}
        id={buttonId}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            openAndFocusSelected();
          }
        }}
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
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              moveActiveOption(activeIndex + 1);
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              moveActiveOption(activeIndex - 1);
            } else if (event.key === "Home") {
              event.preventDefault();
              moveActiveOption(0);
            } else if (event.key === "End") {
              event.preventDefault();
              moveActiveOption(environments.length - 1);
            } else if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              const environment = environments[activeIndex];
              if (environment) {
                selectEnvironment(environment.id);
              }
            } else if (event.key === "Escape") {
              event.preventDefault();
              setOpen(false);
            }
          }}
          role="listbox"
        >
          {environments.map((environment, index) => (
            <button
              aria-selected={tenant.selectedEnvironment?.id === environment.id}
              className="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:bg-accent focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/20"
              key={environment.id}
              onClick={() => selectEnvironment(environment.id)}
              onFocus={() => setActiveIndex(index)}
              ref={(element) => {
                optionRefs.current[index] = element;
              }}
              role="option"
              tabIndex={activeIndex === index ? 0 : -1}
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
