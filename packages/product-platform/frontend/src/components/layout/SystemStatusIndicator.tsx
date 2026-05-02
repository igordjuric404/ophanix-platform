import { Activity } from "lucide-react";

import { useSystemDependencies, useVersionInfo } from "../../api/system";
import { StatusBadge } from "../shared/StatusBadge";

export function SystemStatusIndicator() {
  const dependencies = useSystemDependencies();
  const version = useVersionInfo();
  const dependencyItems = dependencies.data ?? [];
  const degraded = dependencyItems.some((dependency) => dependency.status !== "healthy");
  const status = dependencies.isError || version.isError ? "warning" : degraded ? "degraded" : "healthy";
  const label = status === "healthy" ? "Healthy" : status === "degraded" ? "Degraded" : "Warning";

  return (
    <details className="relative">
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm">
        <Activity className="h-4 w-4 text-primary" />
        <StatusBadge status={label} />
      </summary>
      <div className="absolute right-0 z-30 mt-2 w-80 rounded-lg border bg-background p-4 text-sm shadow-lg">
        <div className="font-medium">System status</div>
        <p className="mt-1 text-muted-foreground">
          {status === "healthy"
            ? "All registered dependencies are healthy."
            : status === "degraded"
              ? "One or more dependencies need attention."
              : "System status could not be fully loaded."}
        </p>
        <div className="mt-3 rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
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
    </details>
  );
}

