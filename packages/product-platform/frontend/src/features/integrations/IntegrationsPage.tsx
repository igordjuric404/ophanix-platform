import { Cable, KeyRound, Link2, PlugZap, RefreshCw } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { useAgents, type AgentSummary } from "../../api/agents";
import {
  createFrameworkInstance,
  createProviderCredential,
  linkFrameworkAgent,
  patchFrameworkInstance,
  testProviderCredential,
  unlinkFrameworkAgent,
  useFrameworkAgentLinks,
  useFrameworkInstances,
  useIntegrationFrameworks,
  useIntegrationHealthChecks,
  useIntegrationMutation,
  useProviderCredentials,
  type FrameworkAgentLink,
  type FrameworkInstance,
  type FrameworkIntegration,
  type IntegrationHealthCheck,
  type IntegrationParams,
  type ProviderCredential
} from "../../api/integrations";
import { PageHeader } from "../../components/layout/PageHeader";
import { EmptyState } from "../../components/shared/EmptyState";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "../../components/ui/table";

const frameworkStatuses = ["", "primary_demo", "supported", "preview", "deprecated"];
const instanceStatuses = ["active", "disabled", "degraded"];
const providerTypes = ["model_provider", "mcp_server", "observability_provider", "secret_store"];
const healthStatuses = ["", "healthy", "failed", "degraded"];

export function IntegrationsPage() {
  const [frameworkFilters, setFrameworkFilters] = useState<IntegrationParams>({});
  const [healthFilters, setHealthFilters] = useState<IntegrationParams>({});
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const frameworksQuery = useIntegrationFrameworks(frameworkFilters);
  const instancesQuery = useFrameworkInstances();
  const linksQuery = useFrameworkAgentLinks();
  const credentialsQuery = useProviderCredentials();
  const healthQuery = useIntegrationHealthChecks(healthFilters);
  const agentsQuery = useAgents();
  const mutation = useIntegrationMutation();

  const frameworks = frameworksQuery.data ?? [];
  const instances = instancesQuery.data ?? [];
  const links = linksQuery.data ?? [];
  const credentials = credentialsQuery.data ?? [];
  const healthChecks = healthQuery.data ?? [];
  const agents = agentsQuery.data ?? [];
  const activeInstanceId = selectedInstanceId ?? instances[0]?.id ?? null;

  async function runTask(label: string, task: () => Promise<unknown>) {
    try {
      await mutation.mutateAsync(task);
      setMessage(label);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed");
    }
  }

  return (
    <>
      <PageHeader
        title="Integrations"
        description="Framework connectors, provider credentials, linked agents, and health checks."
      />
      <div className="space-y-6 p-6">
        {message ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            {message}
          </div>
        ) : null}
        <IntegrationsSummary
          credentials={credentials}
          frameworks={frameworks}
          healthChecks={healthChecks}
          instances={instances}
        />
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <FrameworkCatalogPanel
            filters={frameworkFilters}
            frameworks={frameworks}
            onFilter={setFrameworkFilters}
          />
          <ConnectorInstancesPanel
            frameworks={frameworks}
            instances={instances}
            onCreate={(payload) =>
              runTask("Connector instance created", () => createFrameworkInstance(payload))
            }
            onPatch={(instanceId, payload) =>
              runTask("Connector instance updated", () => patchFrameworkInstance(instanceId, payload))
            }
            onSelect={setSelectedInstanceId}
            selectedInstanceId={activeInstanceId}
          />
        </div>
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <LinkedAgentsPanel
            agents={agents}
            instances={instances}
            links={links}
            onLink={(instanceId, payload) =>
              runTask("Agent linked to connector", () => linkFrameworkAgent(instanceId, payload))
            }
            onUnlink={(linkId) =>
              runTask("Agent unlinked from connector", () => unlinkFrameworkAgent(linkId))
            }
            selectedInstanceId={activeInstanceId}
          />
          <ProviderCredentialsPanel
            credentials={credentials}
            onCreate={(payload) =>
              runTask("Provider credential created", () => createProviderCredential(payload))
            }
            onTest={(credentialId) =>
              runTask("Provider credential tested", () => testProviderCredential(credentialId))
            }
          />
        </div>
        <HealthChecksPanel
          filters={healthFilters}
          healthChecks={healthChecks}
          onFilter={setHealthFilters}
        />
      </div>
    </>
  );
}

function IntegrationsSummary({
  credentials,
  frameworks,
  healthChecks,
  instances
}: {
  credentials: ProviderCredential[];
  frameworks: FrameworkIntegration[];
  healthChecks: IntegrationHealthCheck[];
  instances: FrameworkInstance[];
}) {
  return (
    <div className="grid gap-4 md:grid-cols-4">
      <Metric icon={<PlugZap className="h-4 w-4" />} label="Frameworks" value={frameworks.length} />
      <Metric icon={<Cable className="h-4 w-4" />} label="Connectors" value={instances.length} />
      <Metric icon={<KeyRound className="h-4 w-4" />} label="Credentials" value={credentials.length} />
      <Metric icon={<RefreshCw className="h-4 w-4" />} label="Failed Health" value={healthChecks.filter((check) => check.status === "failed").length} />
    </div>
  );
}

function FrameworkCatalogPanel({
  filters,
  frameworks,
  onFilter
}: {
  filters: IntegrationParams;
  frameworks: FrameworkIntegration[];
  onFilter: (filters: IntegrationParams) => void;
}) {
  return (
    <Card data-integration-framework-catalog>
      <CardHeader>
        <CardTitle>Framework Catalog</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            onFilter(cleanParams(new FormData(event.currentTarget), ["status"]));
          }}
        >
          <SelectField defaultValue={String(filters.status ?? "")} label="Framework Status" name="status" options={frameworkStatuses} />
          <Button type="submit" variant="outline">
            Filter
          </Button>
        </form>
        {frameworks.length === 0 ? (
          <EmptyState title="No frameworks" description="Seed the framework catalog to configure connectors." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Framework</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Versions</TableHead>
                <TableHead>Setup</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {frameworks.map((framework) => (
                <TableRow data-integration-framework-row={framework.id} key={framework.id}>
                  <TableCell>
                    <div className="font-medium">{framework.name}</div>
                    <div className="text-xs text-muted-foreground">{framework.description}</div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={framework.status} />
                  </TableCell>
                  <TableCell>{framework.supported_versions.join(", ") || "n/a"}</TableCell>
                  <TableCell>
                    <code data-integration-setup-snippet={framework.id}>
                      {framework.setup_snippet ?? framework.example_path ?? "none"}
                    </code>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function ConnectorInstancesPanel({
  frameworks,
  instances,
  onCreate,
  onPatch,
  onSelect,
  selectedInstanceId
}: {
  frameworks: FrameworkIntegration[];
  instances: FrameworkInstance[];
  onCreate: (payload: Record<string, unknown>) => void;
  onPatch: (instanceId: string, payload: Record<string, unknown>) => void;
  onSelect: (instanceId: string) => void;
  selectedInstanceId: string | null;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Connector Instances</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="grid gap-3 md:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            onCreate(integrationInstancePayloadFromForm(event.currentTarget));
            event.currentTarget.reset();
          }}
        >
          <SelectField
            label="Framework"
            name="integration_id"
            options={frameworks.map((framework) => framework.id)}
          />
          <Field label="Connector Name" name="name" />
          <SelectField label="Connector Status" name="status" options={instanceStatuses} />
          <TextAreaField defaultValue='{"project":"demo-project"}' label="Config JSON" name="config_json" />
          <div>
            <Button type="submit">Create Connector</Button>
          </div>
        </form>
        {instances.length === 0 ? (
          <EmptyState title="No connector instances" description="Create a configured connector for an environment." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Config</TableHead>
                <TableHead>Patch</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {instances.map((instance) => (
                <TableRow data-integration-instance-row={instance.id} key={instance.id}>
                  <TableCell>
                    <button
                      className="font-medium text-primary"
                      onClick={() => onSelect(instance.id)}
                      type="button"
                    >
                      {instance.name}
                    </button>
                    <div className="text-xs text-muted-foreground">{instance.integration_name}</div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={instance.status} />
                  </TableCell>
                  <TableCell>
                    <code>{JSON.stringify(maskConfig(instance.config))}</code>
                  </TableCell>
                  <TableCell>
                    <form
                      className="flex flex-wrap gap-2"
                      onSubmit={(event) => {
                        event.preventDefault();
                        const form = new FormData(event.currentTarget);
                        onPatch(instance.id, {
                          name: optionalString(form.get("name")),
                          status: optionalString(form.get("status"))
                        });
                      }}
                    >
                      <Input aria-label={`${instance.name} name`} className="w-36" name="name" placeholder="Name" />
                      <select className="h-9 rounded-md border border-input bg-background px-2 text-sm" name="status">
                        {instanceStatuses.map((status) => (
                          <option key={status} value={status}>
                            {status}
                          </option>
                        ))}
                      </select>
                      <Button type="submit" variant="outline">
                        Patch
                      </Button>
                    </form>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {selectedInstanceId ? <Badge tone="muted">Selected {selectedInstanceId}</Badge> : null}
      </CardContent>
    </Card>
  );
}

function LinkedAgentsPanel({
  agents,
  instances,
  links,
  onLink,
  onUnlink,
  selectedInstanceId
}: {
  agents: AgentSummary[];
  instances: FrameworkInstance[];
  links: FrameworkAgentLink[];
  onLink: (instanceId: string, payload: Record<string, unknown>) => void;
  onUnlink: (linkId: string) => void;
  selectedInstanceId: string | null;
}) {
  const activeInstanceId = selectedInstanceId ?? instances[0]?.id ?? "";
  const activeLinks = useMemo(
    () =>
      activeInstanceId
        ? links.filter((link) => link.integration_instance_id === activeInstanceId)
        : links,
    [activeInstanceId, links]
  );
  return (
    <Card>
      <CardHeader>
        <CardTitle>Linked Agents</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="grid gap-3 md:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (activeInstanceId) {
              onLink(activeInstanceId, integrationAgentLinkPayloadFromForm(event.currentTarget));
            }
          }}
        >
          <SelectField label="Agent" name="agent_id" options={agents.map((agent) => agent.id)} />
          <Field label="Framework Agent Ref" name="framework_agent_ref" placeholder="assistant:demo" />
          <Field defaultValue="0.3.0" label="SDK Version" name="sdk_version" />
          <div className="flex items-end">
            <Button disabled={!activeInstanceId} type="submit">
              <Link2 className="h-4 w-4" />
              Link Agent
            </Button>
          </div>
        </form>
        {activeLinks.length === 0 ? (
          <EmptyState title="No linked agents" description="Link connector coverage to governed agents." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Agent</TableHead>
                <TableHead>Reference</TableHead>
                <TableHead>Telemetry</TableHead>
                <TableHead>Policy</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {activeLinks.map((link) => (
                <TableRow data-integration-linked-agent-row={link.id} key={link.id}>
                  <TableCell>{link.agent_name}</TableCell>
                  <TableCell>{link.framework_agent_ref}</TableCell>
                  <TableCell>
                    <StatusBadge status={link.telemetry_status} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={link.policy_coverage_status} />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button onClick={() => onUnlink(link.id)} type="button" variant="outline">
                      Unlink
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function ProviderCredentialsPanel({
  credentials,
  onCreate,
  onTest
}: {
  credentials: ProviderCredential[];
  onCreate: (payload: Record<string, unknown>) => void;
  onTest: (credentialId: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Provider Credentials</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="grid gap-3 md:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            onCreate(providerCredentialPayloadFromForm(event.currentTarget));
            event.currentTarget.reset();
          }}
        >
          <Field label="Credential Name" name="name" />
          <SelectField label="Provider Type" name="provider_type" options={providerTypes} />
          <Field label="Secret Value" name="secret_value" type="password" />
          <div className="flex items-end">
            <Button type="submit">
              <KeyRound className="h-4 w-4" />
              Add Credential
            </Button>
          </div>
        </form>
        {credentials.length === 0 ? (
          <EmptyState title="No provider credentials" description="Add provider secrets by reference." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Masked</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {credentials.map((credential) => (
                <TableRow data-provider-credential-row={credential.id} key={credential.id}>
                  <TableCell>{credential.name}</TableCell>
                  <TableCell>{credential.provider_type}</TableCell>
                  <TableCell>{credential.masked_secret}</TableCell>
                  <TableCell>
                    <StatusBadge status={credential.status} />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button onClick={() => onTest(credential.id)} type="button" variant="outline">
                      Test
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function HealthChecksPanel({
  filters,
  healthChecks,
  onFilter
}: {
  filters: IntegrationParams;
  healthChecks: IntegrationHealthCheck[];
  onFilter: (filters: IntegrationParams) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Health Checks</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            onFilter(cleanParams(new FormData(event.currentTarget), ["status", "target_type"]));
          }}
        >
          <SelectField defaultValue={String(filters.status ?? "")} label="Health Status" name="status" options={healthStatuses} />
          <SelectField defaultValue={String(filters.target_type ?? "")} label="Health Target Type" name="target_type" options={["", "provider_credential", "framework_instance"]} />
          <Button type="submit" variant="outline">
            Filter
          </Button>
        </form>
        {healthChecks.length === 0 ? (
          <EmptyState title="No health checks" description="Run provider or connector checks to populate this feed." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Target</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Latency</TableHead>
                <TableHead>Message</TableHead>
                <TableHead>Remediation</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {healthChecks.map((check) => (
                <TableRow data-integration-health-row={check.id} key={check.id}>
                  <TableCell>
                    {check.target_type}:{check.target_id}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={check.status} />
                  </TableCell>
                  <TableCell>{check.latency_ms} ms</TableCell>
                  <TableCell>{check.message}</TableCell>
                  <TableCell data-health-remediation>{remediationFor(check)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ icon, label, value }: { icon?: ReactNode; label: string; value: ReactNode }) {
  return (
    <div className="rounded-md border bg-card p-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function Field({
  defaultValue,
  label,
  name,
  placeholder,
  type = "text"
}: {
  defaultValue?: string;
  label: string;
  name: string;
  placeholder?: string;
  type?: string;
}) {
  const id = `${name}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <Input defaultValue={defaultValue} id={id} name={name} placeholder={placeholder} type={type} />
    </div>
  );
}

function TextAreaField({
  defaultValue,
  label,
  name
}: {
  defaultValue?: string;
  label: string;
  name: string;
}) {
  const id = `${name}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <textarea
        className="min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        defaultValue={defaultValue}
        id={id}
        name={name}
      />
    </div>
  );
}

function SelectField({
  defaultValue,
  label,
  name,
  options
}: {
  defaultValue?: string;
  label: string;
  name: string;
  options: string[];
}) {
  const id = `${name}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <select
        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
        defaultValue={defaultValue}
        id={id}
        name={name}
      >
        {options.map((option) => (
          <option key={option || "all"} value={option}>
            {option || "all"}
          </option>
        ))}
      </select>
    </div>
  );
}

export function integrationInstancePayloadFromValues(values: Record<string, unknown> = {}) {
  return {
    integration_id: requiredString(values.integration_id, "integration_id"),
    name: requiredString(values.name, "name"),
    status: optionalString(values.status) || "active",
    config: parseJsonObject(values.config_json, "config_json")
  };
}

export function integrationInstancePayloadFromForm(form: HTMLFormElement) {
  return integrationInstancePayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function integrationAgentLinkPayloadFromValues(values: Record<string, unknown> = {}) {
  return {
    agent_id: requiredString(values.agent_id, "agent_id"),
    framework_agent_ref: requiredString(values.framework_agent_ref, "framework_agent_ref"),
    sdk_version: optionalString(values.sdk_version) || "unknown"
  };
}

export function integrationAgentLinkPayloadFromForm(form: HTMLFormElement) {
  return integrationAgentLinkPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function providerCredentialPayloadFromValues(values: Record<string, unknown> = {}) {
  return {
    name: requiredString(values.name, "name"),
    provider_type: requiredString(values.provider_type, "provider_type"),
    secret_value: requiredString(values.secret_value, "secret_value")
  };
}

export function providerCredentialPayloadFromForm(form: HTMLFormElement) {
  return providerCredentialPayloadFromValues(Object.fromEntries(new FormData(form)));
}

function cleanParams(form: FormData, keys: string[]) {
  return Object.fromEntries(
    keys
      .map((key) => [key, String(form.get(key) ?? "").trim()])
      .filter(([, value]) => value !== "")
  );
}

function requiredString(value: unknown, fieldName: string) {
  const trimmed = optionalString(value);
  if (!trimmed) {
    throw new Error(`${fieldName} is required.`);
  }
  return trimmed;
}

function optionalString(value: unknown) {
  return String(value ?? "").trim();
}

function parseJsonObject(value: unknown, fieldName: string) {
  try {
    const parsed = JSON.parse(String(value ?? "{}")) as unknown;
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      throw new Error("not object");
    }
    return parsed as Record<string, unknown>;
  } catch {
    throw new Error(`${fieldName} must be a JSON object.`);
  }
}

function maskConfig(config: Record<string, unknown>) {
  const masked: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(config)) {
    masked[key] =
      key.toLowerCase().includes("secret") || key.toLowerCase().includes("token")
        ? "********"
        : value;
  }
  return masked;
}

function remediationFor(check: IntegrationHealthCheck) {
  if (check.status === "healthy") {
    return "No action needed";
  }
  if (check.target_type === "provider_credential") {
    return "Check secret reference and provider configuration";
  }
  return "Review connector configuration and retry";
}
