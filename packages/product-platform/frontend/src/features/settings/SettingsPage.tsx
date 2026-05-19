import { KeyRound, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useId, type FormEvent, type InputHTMLAttributes } from "react";

import {
  createApiKey,
  createEnvironment,
  revokeApiKey,
  useAdminMutation,
  useApiKeys
} from "../../api/admin";
import type { TenantContext } from "../../api/client";
import { useSystemDependencies, useVersionInfo } from "../../api/system";
import { useCurrentUserPrincipal } from "../../app/userContext";
import { PageHeader } from "../../components/layout/PageHeader";
import { ActionFeedback, useActionFeedback } from "../../components/shared/ActionFeedback";
import { QueryErrorSummary } from "../../components/shared/ErrorState";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { permissions, rolePermissions, userHasPermission } from "../../lib/rbac";
import { cn } from "../../lib/utils";

export function SettingsPage() {
  const currentUser = useCurrentUserPrincipal();
  const apiKeysQuery = useApiKeys();
  const dependenciesQuery = useSystemDependencies();
  const versionQuery = useVersionInfo();
  const mutation = useAdminMutation();
  const { feedback, runWithFeedback } = useActionFeedback();
  const canManageTenants = userHasPermission(currentUser, permissions.TENANT_MANAGE);
  const canManageApiKeys = userHasPermission(currentUser, permissions.API_KEYS_MANAGE);

  async function runAdminTask(label: string, task: (tenantContext: TenantContext) => Promise<unknown>) {
    await runWithFeedback(() => mutation.mutateAsync(task), {
      errorMessage: `${label} failed`,
      successMessage: label
    });
  }

  function handleEnvironmentCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManageTenants) {
      return;
    }
    const form = new FormData(event.currentTarget);
    void runAdminTask("Environment created", (tenantContext) =>
      createEnvironment(
        {
          name: formString(form, "name"),
          slug: formString(form, "slug"),
          type: formString(form, "type") || "development"
        },
        tenantContext
      )
    );
  }

  function handleApiKeyCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManageApiKeys) {
      return;
    }
    const form = new FormData(event.currentTarget);
    const scopes = formString(form, "scopes")
      .split(",")
      .map((scope) => scope.trim())
      .filter(Boolean);
    void runAdminTask("API key created", (tenantContext) =>
      createApiKey(
        {
          name: formString(form, "name"),
          kind: formString(form, "kind") || "agent",
          scopes,
          environment_ids: tenantContext.environmentId ? [tenantContext.environmentId] : []
        },
        tenantContext
      )
    );
  }

  function handleApiKeyRevoke(keyId: string) {
    if (!canManageApiKeys) {
      return;
    }
    void runAdminTask("API key revoked", (tenantContext) => revokeApiKey(keyId, tenantContext));
  }

  return (
    <>
      <PageHeader
        title="Settings"
        description="Tenant setup, environment controls, API keys, role templates, and readiness."
      />
      <div className="space-y-6 p-6">
        <ActionFeedback feedback={feedback} />
        <QueryErrorSummary
          items={[
            {
              error: apiKeysQuery.error,
              isError: apiKeysQuery.isError,
              label: "API keys",
              onRetry: () => void apiKeysQuery.refetch()
            },
            {
              error: dependenciesQuery.error,
              isError: dependenciesQuery.isError,
              label: "Dependency status",
              onRetry: () => void dependenciesQuery.refetch()
            },
            {
              error: versionQuery.error,
              isError: versionQuery.isError,
              label: "Version",
              onRetry: () => void versionQuery.refetch()
            }
          ]}
        />
        <SetupChecklist
          apiKeyCount={apiKeysQuery.data?.length ?? 0}
          dependenciesHealthy={(dependenciesQuery.data ?? []).every(
            (dependency) => dependency.status === "healthy"
          )}
          version={versionQuery.data?.version ?? "unknown"}
        />
        <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
          <OrganizationEnvironmentPanel
            canManage={canManageTenants}
            isPending={mutation.isPending}
            onSubmit={handleEnvironmentCreate}
          />
          <ApiKeyPanel
            apiKeys={apiKeysQuery.data ?? []}
            canManage={canManageApiKeys}
            isLoading={apiKeysQuery.isLoading}
            isPending={mutation.isPending}
            onCreate={handleApiKeyCreate}
            onRevoke={handleApiKeyRevoke}
          />
        </div>
        <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
          <IdentityRolesPanel currentRoles={currentUser?.roles ?? []} />
          <OperationalSetupPanel dependencies={dependenciesQuery.data ?? []} />
        </div>
      </div>
    </>
  );
}

function SetupChecklist({
  apiKeyCount,
  dependenciesHealthy,
  version
}: {
  apiKeyCount: number;
  dependenciesHealthy: boolean;
  version: string;
}) {
  const items = [
    { label: "Application version", status: version !== "unknown" ? "ready" : "unknown" },
    { label: "Dependency health", status: dependenciesHealthy ? "ready" : "attention" },
    { label: "API key bootstrap", status: apiKeyCount > 0 ? "ready" : "attention" }
  ];

  return (
    <section className="rounded-lg border bg-card p-5" data-settings-checklist>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Setup Checklist</h2>
          <p className="text-sm text-muted-foreground">Current control-plane readiness signals.</p>
        </div>
        <Badge tone={dependenciesHealthy && apiKeyCount > 0 ? "success" : "warning"}>
          {dependenciesHealthy && apiKeyCount > 0 ? "Ready" : "Needs setup"}
        </Badge>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {items.map((item) => (
          <div className="rounded-lg border p-4" key={item.label}>
            <div className="text-sm font-medium">{item.label}</div>
            <div className="mt-2">
              <StatusBadge status={item.status} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function OrganizationEnvironmentPanel({
  canManage,
  isPending,
  onSubmit
}: {
  canManage: boolean;
  isPending: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="rounded-lg border bg-card p-5" data-environment-settings>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Organization And Environments</h2>
          <p className="text-sm text-muted-foreground">
            Create deployment environments inside the selected organization.
          </p>
        </div>
        <ShieldCheck className="h-5 w-5 text-primary" />
      </div>
      <form className="mt-5 grid gap-4 md:grid-cols-3" onSubmit={onSubmit}>
        <Field disabled={!canManage} label="Name" name="name" required defaultValue="Staging" />
        <Field disabled={!canManage} label="Slug" name="slug" required defaultValue="staging" />
        <SelectField
          disabled={!canManage}
          label="Type"
          name="type"
          options={["development", "staging", "production", "sandbox"]}
        />
        <div className="flex items-end">
          <Button disabled={!canManage || isPending} type="submit">
            <Plus className="h-4 w-4" />
            Create environment
          </Button>
        </div>
      </form>
    </section>
  );
}

function ApiKeyPanel({
  apiKeys,
  canManage,
  isLoading,
  isPending,
  onCreate,
  onRevoke
}: {
  apiKeys: Array<{
    id: string;
    name: string;
    kind: string;
    scopes: string[];
    environment_ids: string[];
    revoked_at: number | null;
  }>;
  canManage: boolean;
  isLoading: boolean;
  isPending: boolean;
  onCreate: (event: FormEvent<HTMLFormElement>) => void;
  onRevoke: (keyId: string) => void;
}) {
  return (
    <section className="rounded-lg border bg-card p-5" data-api-key-settings>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">API Keys</h2>
          <p className="text-sm text-muted-foreground">
            Create scoped automation keys and revoke stale credentials.
          </p>
        </div>
        <KeyRound className="h-5 w-5 text-primary" />
      </div>
      <form className="mt-5 grid gap-4 md:grid-cols-4" onSubmit={onCreate}>
        <Field disabled={!canManage} label="Name" name="name" required defaultValue="Workflow key" />
        <SelectField
          disabled={!canManage}
          label="Kind"
          name="kind"
          options={["agent", "ci", "integration"]}
        />
        <Field
          className="md:col-span-2"
          disabled={!canManage}
          label="Scopes"
          name="scopes"
          required
          defaultValue="job:run"
        />
        <div className="flex items-end">
          <Button disabled={!canManage || isPending} type="submit">
            <Plus className="h-4 w-4" />
            Create API key
          </Button>
        </div>
      </form>
      <div className="mt-5 overflow-x-auto">
        {isLoading ? (
          <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
            Loading API keys
          </div>
        ) : apiKeys.length === 0 ? (
          <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
            No API keys created
          </div>
        ) : (
          <table className="w-full min-w-[42rem] text-sm">
            <thead className="border-b text-left text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">Name</th>
                <th className="py-2 pr-3 font-medium">Kind</th>
                <th className="py-2 pr-3 font-medium">Scopes</th>
                <th className="py-2 pr-3 font-medium">Environments</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {apiKeys.map((key) => (
                <tr className="border-b last:border-b-0" key={key.id}>
                  <td className="py-3 pr-3 font-medium">{key.name}</td>
                  <td className="py-3 pr-3">{key.kind}</td>
                  <td className="py-3 pr-3">{key.scopes.join(", ") || "n/a"}</td>
                  <td className="py-3 pr-3">{key.environment_ids.join(", ") || "selected"}</td>
                  <td className="py-3 pr-3">
                    <StatusBadge status={key.revoked_at ? "revoked" : "active"} />
                  </td>
                  <td className="py-3 pr-3">
                    <Button
                      disabled={!canManage || isPending || Boolean(key.revoked_at)}
                      onClick={() => onRevoke(key.id)}
                      type="button"
                      variant="outline"
                    >
                      <Trash2 className="h-4 w-4" />
                      Revoke
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

function IdentityRolesPanel({ currentRoles }: { currentRoles: string[] }) {
  return (
    <section className="rounded-lg border bg-card p-5" data-role-settings>
      <h2 className="text-lg font-semibold">Identity And Roles</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Backend-aligned role templates for the current control-plane contract.
      </p>
      <div className="mt-4 space-y-3">
        {Object.entries(rolePermissions).map(([role, grantedPermissions]) => (
          <div
            className={cn(
              "rounded-lg border p-4",
              currentRoles.includes(role) ? "border-primary/50 bg-primary/5" : ""
            )}
            key={role}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-medium">{role}</h3>
              {currentRoles.includes(role) ? <Badge tone="success">Current</Badge> : null}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {Array.from(grantedPermissions).sort().join(", ")}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function OperationalSetupPanel({
  dependencies
}: {
  dependencies: Array<{ name: string; status: string; required: boolean; message?: string | null }>;
}) {
  return (
    <section className="rounded-lg border bg-card p-5" data-operational-settings>
      <h2 className="text-lg font-semibold">Operational Setup</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Runtime dependencies that affect first-run and admin workflows.
      </p>
      <div className="mt-4 space-y-3">
        {dependencies.length === 0 ? (
          <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
            No dependency status returned
          </div>
        ) : (
          dependencies.map((dependency) => (
            <div className="flex items-center justify-between gap-3 rounded-lg border p-4" key={dependency.name}>
              <div>
                <div className="font-medium">{dependency.name}</div>
                <div className="text-xs text-muted-foreground">
                  {dependency.required ? "Required" : "Optional"}
                  {dependency.message ? ` - ${dependency.message}` : ""}
                </div>
              </div>
              <StatusBadge status={dependency.status} />
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function Field({
  className,
  label,
  name,
  ...props
}: {
  className?: string;
  label: string;
  name: string;
} & InputHTMLAttributes<HTMLInputElement>) {
  const reactId = useId();
  const id = `${reactId}-${name}`;
  return (
    <div className={cn("space-y-1", className)}>
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} name={name} {...props} />
    </div>
  );
}

function SelectField({
  disabled,
  label,
  name,
  options
}: {
  disabled?: boolean;
  label: string;
  name: string;
  options: string[];
}) {
  const reactId = useId();
  const id = `${reactId}-${name}`;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <select
        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
        disabled={disabled}
        id={id}
        name={name}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}

function formString(form: FormData, key: string) {
  return String(form.get(key) ?? "").trim();
}
