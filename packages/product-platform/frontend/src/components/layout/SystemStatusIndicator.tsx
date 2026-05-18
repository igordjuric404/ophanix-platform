import { Activity } from "lucide-react";
import { useId, useRef, useState } from "react";

import { useSystemDependencies, useVersionInfo } from "../../api/system";
import { StatusBadge } from "../shared/StatusBadge";
import { Button } from "../ui/button";
import { announceHeaderPopoverOpen, useHeaderPopoverDismiss } from "./headerPopover";

export function SystemStatusIndicator() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const popoverId = useId();
  const dependencies = useSystemDependencies();
  const version = useVersionInfo();
  const dependencyItems = dependencies.data ?? [];
  const requiredIssue = dependencyItems.some(
    (dependency) => dependency.required && isAttentionStatus(dependency.status)
  );
  const optionalIssue = dependencyItems.some(
    (dependency) => !dependency.required && isAttentionStatus(dependency.status)
  );
  const status =
    dependencies.isError || version.isError
      ? "warning"
      : requiredIssue
        ? "degraded"
        : optionalIssue
          ? "warning"
          : "healthy";
  const label = status === "healthy" ? "Healthy" : status === "degraded" ? "Degraded" : "Warning";

  useHeaderPopoverDismiss({
    id: popoverId,
    onOpenChange: setOpen,
    open,
    rootRef
  });

  function toggleOpen() {
    setOpen((current) => {
      const next = !current;
      if (next) {
        announceHeaderPopoverOpen(popoverId);
      }
      return next;
    });
  }

  return (
    <div className="relative" ref={rootRef}>
      <Button
        aria-controls={open ? popoverId : undefined}
        aria-expanded={open}
        aria-label="System status"
        className="h-9 gap-2 px-3"
        onClick={toggleOpen}
        type="button"
        variant="outline"
      >
        <Activity className="h-4 w-4 text-primary" />
        <StatusBadge status={label} />
      </Button>
      {open ? (
        <div
          className="absolute right-0 z-30 mt-2 w-80 rounded-lg border border-border/80 bg-card p-4 text-sm shadow-[var(--shadow-popover)]"
          id={popoverId}
          role="dialog"
        >
          <div className="font-display font-semibold">System status</div>
          <p className="mt-1 text-muted-foreground">
            {status === "healthy"
              ? "Required dependencies are healthy."
              : status === "degraded"
                ? "One or more dependencies need attention."
                : dependencies.isError || version.isError
                  ? "System status could not be fully loaded."
                  : "Optional dependencies need attention."}
          </p>
          <div className="mt-3 rounded-md border border-border/80 bg-muted/60 p-3 text-xs text-muted-foreground">
            API build: {version.data?.build_sha ?? version.data?.version ?? "unknown"}
          </div>
          <ul className="mt-3 space-y-2">
            {dependencyItems.length > 0 ? (
              dependencyItems.map((dependency) => (
                <li className="flex items-center justify-between gap-2" key={dependency.name}>
                  <span>{dependency.name}</span>
                  <StatusBadge status={dependency.status} />
                </li>
              ))
            ) : (
              <li className="text-muted-foreground">No dependencies reported</li>
            )}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function isAttentionStatus(status: string) {
  return ["degraded", "failed", "unhealthy", "warning"].includes(status.toLowerCase());
}
