import type { TenantSelection } from "../../app/tenantContext";
import { Label } from "../ui/label";

export function EnvironmentSelector({ tenant }: { tenant: TenantSelection }) {
  const environments = tenant.selectedOrganization
    ? tenant.environments.filter(
        (environment) => environment.organization_id === tenant.selectedOrganization?.id
      )
    : tenant.environments;

  return (
    <div className="hidden min-w-48 space-y-1 md:block">
      <Label className="text-xs text-muted-foreground" htmlFor="environment-selector">
        Environment
      </Label>
      <select
        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        disabled={tenant.isLoading || environments.length === 0}
        id="environment-selector"
        onChange={(event) => tenant.setSelectedEnvironmentId(event.target.value)}
        value={tenant.selectedEnvironment?.id ?? ""}
      >
        {environments.length > 0 ? (
          environments.map((environment) => (
            <option key={environment.id} value={environment.id}>
              {environment.name}
            </option>
          ))
        ) : (
          <option value="">No environment</option>
        )}
      </select>
    </div>
  );
}

