import {
  BadgeCheck,
  KeyRound,
  PackageCheck,
  PackagePlus,
  ShieldCheck,
  Sparkles
} from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import type { TenantContext } from "../../api/client";
import {
  approveMarketplaceReview,
  assessMarketplacePluginQuality,
  checkMarketplacePluginPolicy,
  createMarketplaceInstallation,
  createMarketplaceSigningKey,
  importMarketplacePlugin,
  recomputeMarketplacePluginTrust,
  rejectMarketplaceReview,
  revokeMarketplaceSigningKey,
  submitMarketplacePluginReview,
  uninstallMarketplaceInstallation,
  useMarketplaceInstallations,
  useMarketplaceMutation,
  useMarketplacePlugin,
  useMarketplacePlugins,
  useMarketplaceReviews,
  useMarketplaceSigningKeys,
  type MarketplaceParams,
  type MarketplacePlugin,
  type PluginInstallation,
  type PluginPolicyResult,
  type PluginQualityAssessment,
  type PluginReview,
  type PluginSigningKey,
  type PluginTrustEvent,
  type PluginVersion
} from "../../api/marketplace";
import { useTenantQueryScope } from "../../api/queryScope";
import { PageHeader } from "../../components/layout/PageHeader";
import {
  ActionFeedback,
  actionErrorMessage,
  useActionFeedback
} from "../../components/shared/ActionFeedback";
import { EmptyState } from "../../components/shared/EmptyState";
import { QueryErrorSummary } from "../../components/shared/ErrorState";
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
import { parseJsonObjectField } from "../../lib/forms";

const pluginTypes = ["", "policy_template", "integration", "agent", "validator"];
const pluginStatuses = ["", "available", "deprecated", "disabled"];
const reviewStatuses = ["", "pending", "approved", "rejected"];

export function MarketplacePage() {
  const [pluginFilters, setPluginFilters] = useState<MarketplaceParams>({});
  const [reviewFilters, setReviewFilters] = useState<MarketplaceParams>({});
  const [selectedPluginId, setSelectedPluginId] = useState<string | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [policyResult, setPolicyResult] = useState<PluginPolicyResult | null>(null);
  const [qualityAssessment, setQualityAssessment] = useState<PluginQualityAssessment | null>(null);
  const [trustEvents, setTrustEvents] = useState<PluginTrustEvent[]>([]);
  const { feedback, runWithFeedback, setError } = useActionFeedback();

  const pluginsQuery = useMarketplacePlugins(pluginFilters);
  const installationsQuery = useMarketplaceInstallations();
  const reviewsQuery = useMarketplaceReviews(reviewFilters);
  const signingKeysQuery = useMarketplaceSigningKeys();
  const mutation = useMarketplaceMutation();
  const tenantScope = useTenantQueryScope();

  const plugins = pluginsQuery.data ?? [];
  const activePluginId = selectedPluginId ?? plugins[0]?.id ?? null;
  const pluginDetailQuery = useMarketplacePlugin(activePluginId);
  const activePlugin =
    pluginDetailQuery.data ?? plugins.find((plugin) => plugin.id === activePluginId) ?? null;
  const activeVersion =
    activePlugin?.versions.find((version) => version.id === selectedVersionId) ??
    activePlugin?.versions[0] ??
    null;
  const activeVersionId = activeVersion?.id ?? null;
  const installations = installationsQuery.data ?? [];
  const reviews = reviewsQuery.data ?? [];
  const signingKeys = signingKeysQuery.data ?? [];
  const activePolicyResult =
    policyResult?.plugin_version_id === activeVersionId ? policyResult : null;
  const activeQualityAssessment =
    qualityAssessment?.plugin_version_id === activeVersionId ? qualityAssessment : null;
  const activeTrustEvents = trustEvents.filter(
    (event) => event.plugin_version_id === activeVersionId
  );

  async function runTask(
    label: string,
    task: (tenantContext: TenantContext) => Promise<unknown>
  ) {
    await runWithFeedback(() => mutation.mutateAsync(task), {
      errorMessage: `${label} failed`,
      successMessage: label
    });
  }

  async function runResultTask<T>(
    label: string,
    task: (tenantContext: TenantContext) => Promise<T>,
    onResult: (value: T) => void
  ) {
    const result = await runWithFeedback<T>(
      () => mutation.mutateAsync(task) as Promise<T>,
      {
        errorMessage: `${label} failed`,
        successMessage: label
      }
    );
    if (result) {
      onResult(result);
    }
  }

  return (
    <>
      <PageHeader
        title="Marketplace Operations"
        description="Review, govern, install, sign, assess, and monitor trusted marketplace plugins."
      />
      <div className="space-y-6 p-6">
        <ActionFeedback feedback={feedback} />
        <QueryErrorSummary
          items={[
            { error: pluginsQuery.error, isError: pluginsQuery.isError, label: "Marketplace plugins", onRetry: () => void pluginsQuery.refetch() },
            { error: pluginDetailQuery.error, isError: pluginDetailQuery.isError, label: "Plugin detail", onRetry: () => void pluginDetailQuery.refetch() },
            { error: installationsQuery.error, isError: installationsQuery.isError, label: "Plugin installations", onRetry: () => void installationsQuery.refetch() },
            { error: reviewsQuery.error, isError: reviewsQuery.isError, label: "Plugin reviews", onRetry: () => void reviewsQuery.refetch() },
            { error: signingKeysQuery.error, isError: signingKeysQuery.isError, label: "Signing keys", onRetry: () => void signingKeysQuery.refetch() }
          ]}
        />
        <MarketplaceSummary
          installations={installations}
          plugins={plugins}
          reviews={reviews}
          signingKeys={signingKeys}
        />
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1.1fr)_minmax(24rem,0.9fr)]">
          <CatalogPanel
            filters={pluginFilters}
            isLoading={pluginsQuery.isLoading}
            onFilter={setPluginFilters}
            onInvalidInput={(error) => setError(actionErrorMessage(error, "Invalid marketplace input"))}
            onImport={(payload) =>
              runTask("Plugin manifest imported", (tenantContext) =>
                importMarketplacePlugin(payload, tenantContext)
              )
            }
            onSelect={(pluginId) => {
              setSelectedPluginId(pluginId);
              setSelectedVersionId(null);
            }}
            plugins={plugins}
            selectedPluginId={activePlugin?.id ?? null}
          />
          <PluginDetailPanel
            onAssess={(versionId) =>
              runResultTask(
                "Quality assessment completed",
                (tenantContext) => assessMarketplacePluginQuality(versionId, tenantContext),
                setQualityAssessment
              )
            }
            onSubmitReview={(versionId, payload) =>
              runTask("Plugin review submitted", (tenantContext) =>
                submitMarketplacePluginReview(versionId, payload, tenantContext)
              )
            }
            onSelectVersion={setSelectedVersionId}
            plugin={activePlugin}
            selectedVersionId={activeVersion?.id ?? null}
          />
        </div>
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <InstallPanel
            environmentId={tenantScope.context.environmentId}
            onCheck={(versionId, payload) =>
              runResultTask(
                "Policy compatibility checked",
                (tenantContext) => checkMarketplacePluginPolicy(versionId, payload, tenantContext),
                setPolicyResult
              )
            }
            onInstall={(payload) =>
              runTask("Plugin installation created", (tenantContext) =>
                createMarketplaceInstallation(payload, tenantContext)
              )
            }
            policyResult={activePolicyResult}
            version={activeVersion}
          />
          <InstalledPanel
            installations={installations}
            onUninstall={(installationId) =>
              runTask("Plugin uninstalled", (tenantContext) =>
                uninstallMarketplaceInstallation(installationId, tenantContext)
              )
            }
          />
        </div>
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.75fr)]">
          <ReviewsPanel
            filters={reviewFilters}
            onDecision={(reviewId, decision, payload) =>
              runTask(`Review ${decision}`, (tenantContext) =>
                decision === "approved"
                  ? approveMarketplaceReview(reviewId, payload, tenantContext)
                  : rejectMarketplaceReview(reviewId, payload, tenantContext)
              )
            }
            onFilter={setReviewFilters}
            reviews={reviews}
          />
          <SigningKeysPanel
            keys={signingKeys}
            onCreate={(payload) =>
              runTask("Signing key registered", (tenantContext) =>
                createMarketplaceSigningKey(payload, tenantContext)
              )
            }
            onRevoke={(keyId) =>
              runTask("Signing key revoked", (tenantContext) =>
                revokeMarketplaceSigningKey(keyId, tenantContext)
              )
            }
          />
        </div>
        <QualityTrustPanel
          assessment={activeQualityAssessment}
          events={activeTrustEvents}
          onRecompute={(versionId, payload) =>
            runResultTask(
              "Plugin trust recomputed",
              (tenantContext) =>
                recomputeMarketplacePluginTrust(versionId, payload, tenantContext),
              (event) => setTrustEvents((items) => [event, ...items])
            )
          }
          version={activeVersion}
        />
      </div>
    </>
  );
}

function MarketplaceSummary({
  installations,
  plugins,
  reviews,
  signingKeys
}: {
  installations: PluginInstallation[];
  plugins: MarketplacePlugin[];
  reviews: PluginReview[];
  signingKeys: PluginSigningKey[];
}) {
  const installed = installations.filter((item) => item.status === "installed").length;
  const pendingReviews = reviews.filter((review) => review.status === "pending").length;
  const activeKeys = signingKeys.filter((key) => key.status === "active").length;
  return (
    <div className="grid gap-4 md:grid-cols-4">
      <Metric icon={<PackagePlus className="h-4 w-4" />} label="Plugins" value={plugins.length} />
      <Metric icon={<PackageCheck className="h-4 w-4" />} label="Installed" value={installed} />
      <Metric icon={<ShieldCheck className="h-4 w-4" />} label="Pending Reviews" value={pendingReviews} />
      <Metric icon={<KeyRound className="h-4 w-4" />} label="Active Keys" value={activeKeys} />
    </div>
  );
}

function CatalogPanel({
  filters,
  isLoading,
  onFilter,
  onInvalidInput,
  onImport,
  onSelect,
  plugins,
  selectedPluginId
}: {
  filters: MarketplaceParams;
  isLoading: boolean;
  onFilter: (filters: MarketplaceParams) => void;
  onInvalidInput: (error: unknown) => void;
  onImport: (payload: Record<string, unknown>) => void;
  onSelect: (pluginId: string) => void;
  plugins: MarketplacePlugin[];
  selectedPluginId: string | null;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Plugin Catalog</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="grid gap-3 md:grid-cols-4"
          onSubmit={(event) => {
            event.preventDefault();
            const form = new FormData(event.currentTarget);
            onFilter(cleanParams(form, ["plugin_type", "status"]));
          }}
        >
          <SelectField defaultValue={String(filters.plugin_type ?? "")} label="Type" name="plugin_type" options={pluginTypes} />
          <SelectField defaultValue={String(filters.status ?? "")} label="Status" name="status" options={pluginStatuses} />
          <div className="flex items-end">
            <Button type="submit" variant="outline">
              Filter
            </Button>
          </div>
        </form>
        <form
          className="grid gap-3 rounded-md border bg-muted/20 p-3"
          onSubmit={(event) => {
            event.preventDefault();
            try {
              onImport(marketplaceImportPayloadFromForm(event.currentTarget));
            } catch (error) {
              onInvalidInput(error);
              return;
            }
            event.currentTarget.reset();
          }}
        >
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_12rem_10rem]">
            <TextAreaField
              defaultValue={JSON.stringify(sampleManifest(), null, 2)}
              label="Manifest JSON"
              name="manifest_json"
              rows={5}
            />
            <Field label="Package Ref" name="package_ref" placeholder="registry://plugin" />
            <SelectField label="Status" name="status" options={["available", "deprecated", "disabled"]} />
          </div>
          <div>
            <Button type="submit">
              <PackagePlus className="h-4 w-4" />
              Import
            </Button>
          </div>
        </form>
        {isLoading ? <p className="text-sm text-muted-foreground">Loading plugins...</p> : null}
        {plugins.length === 0 ? (
          <EmptyState title="No plugins" description="Import a manifest to populate the catalog." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Latest</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {plugins.map((plugin) => (
                <TableRow data-marketplace-plugin-row={plugin.id} key={plugin.id}>
                  <TableCell>
                    <div className="font-medium">{plugin.name}</div>
                    <div className="text-xs text-muted-foreground">{plugin.publisher}</div>
                  </TableCell>
                  <TableCell>{plugin.plugin_type}</TableCell>
                  <TableCell>
                    <StatusBadge status={plugin.status} />
                  </TableCell>
                  <TableCell>{plugin.versions[0]?.version ?? "n/a"}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      aria-pressed={selectedPluginId === plugin.id}
                      onClick={() => onSelect(plugin.id)}
                      type="button"
                      variant={selectedPluginId === plugin.id ? "default" : "outline"}
                    >
                      Open
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

function PluginDetailPanel({
  onAssess,
  onSelectVersion,
  onSubmitReview,
  plugin,
  selectedVersionId
}: {
  onAssess: (versionId: string) => void;
  onSelectVersion: (versionId: string) => void;
  onSubmitReview: (versionId: string, payload: Record<string, unknown>) => void;
  plugin: MarketplacePlugin | null;
  selectedVersionId: string | null;
}) {
  const version =
    plugin?.versions.find((item) => item.id === selectedVersionId) ?? plugin?.versions[0] ?? null;
  if (!plugin || !version) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Plugin Detail</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState title="No plugin selected" description="Select a catalog row to inspect manifest and versions." />
        </CardContent>
      </Card>
    );
  }
  return (
    <Card data-marketplace-detail={plugin.id}>
      <CardHeader>
        <CardTitle>{plugin.name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3">
          <Metric label="Publisher" value={plugin.publisher} />
          <Metric label="Signature" value={version.signature_status} />
          <Metric label="Trust Tier" value={version.trust_tier} />
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="space-y-3">
            <h3 className="text-sm font-semibold">Versions</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Version</TableHead>
                  <TableHead>Quality</TableHead>
                  <TableHead>Capabilities</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {plugin.versions.map((item) => (
                  <TableRow
                    className={item.id === version.id ? "bg-accent/50" : undefined}
                    data-marketplace-version-row={item.id}
                    key={item.id}
                  >
                    <TableCell>{item.version}</TableCell>
                    <TableCell>{item.quality_score}</TableCell>
                    <TableCell>{item.required_capabilities.length}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        aria-pressed={item.id === version.id}
                        onClick={() => onSelectVersion(item.id)}
                        type="button"
                        variant={item.id === version.id ? "default" : "outline"}
                      >
                        Select
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="flex flex-wrap gap-2">
              {version.permissions.map((permission) => (
                <Badge key={permission} tone="muted">
                  {permission}
                </Badge>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {version.required_capabilities.map((capability) => (
                <Badge key={capability}>
                  {capability}
                </Badge>
              ))}
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => onAssess(version.id)} type="button" variant="outline">
                <Sparkles className="h-4 w-4" />
                Assess Quality
              </Button>
              <form
                className="flex gap-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  onSubmitReview(version.id, marketplaceReviewSubmitPayloadFromForm(event.currentTarget));
                }}
              >
                <input name="code" type="hidden" value="manual_review" />
                <input name="message" type="hidden" value="Manual review requested" />
                <Button type="submit" variant="outline">
                  Submit Review
                </Button>
              </form>
            </div>
            <pre className="max-h-80 overflow-auto rounded-md bg-muted p-3 text-xs" data-marketplace-manifest>
              {JSON.stringify(version.manifest, null, 2)}
            </pre>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function InstallPanel({
  environmentId,
  onCheck,
  onInstall,
  policyResult,
  version
}: {
  environmentId: string | null;
  onCheck: (versionId: string, payload: Record<string, unknown>) => void;
  onInstall: (payload: Record<string, unknown>) => void;
  policyResult: PluginPolicyResult | null;
  version: PluginVersion | null;
}) {
  const policyAllowsInstall =
    Boolean(version) &&
    policyResult?.plugin_version_id === version?.id &&
    policyResult?.result === "allowed";
  return (
    <Card>
      <CardHeader>
        <CardTitle>Policy And Installation</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!version ? (
          <EmptyState title="No version selected" description="Select a plugin version to check and install." />
        ) : (
          <>
            <form
              className="grid gap-3 md:grid-cols-2"
              onSubmit={(event) => {
                event.preventDefault();
                onCheck(version.id, marketplacePolicyPayloadFromForm(event.currentTarget));
              }}
            >
              <CheckboxField label="Require Signature" name="require_signature" />
              <CheckboxField label="Require Review" name="require_review_approval" />
              <Field label="Allowed Types" name="allowed_plugin_types" placeholder="integration,agent" />
              <Field label="Allowed Capabilities" name="allowed_capabilities" placeholder="claims.lookup" />
              <div className="md:col-span-2">
                <Button type="submit">
                  <ShieldCheck className="h-4 w-4" />
                  Check Policy
                </Button>
              </div>
            </form>
            <InstallGates policyResult={policyResult} version={version} />
            <form
              className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
              onSubmit={(event) => {
                event.preventDefault();
                onInstall(marketplaceInstallPayloadFromForm(event.currentTarget));
              }}
            >
              <input name="plugin_version_id" type="hidden" value={version.id} />
              <Field
                defaultValue={environmentId ?? ""}
                key={environmentId ?? "no-environment"}
                label="Environment"
                name="environment_id"
                readOnly
              />
              <Field label="Target Agent" name="target_agent_id" placeholder="agent_123" />
              <div className="flex items-end">
                <Button disabled={!environmentId || !policyAllowsInstall} type="submit">
                  Install
                </Button>
              </div>
            </form>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function InstalledPanel({
  installations,
  onUninstall
}: {
  installations: PluginInstallation[];
  onUninstall: (installationId: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Installations</CardTitle>
      </CardHeader>
      <CardContent>
        {installations.length === 0 ? (
          <EmptyState title="No installations" description="Install approved plugins into the selected environment." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Plugin</TableHead>
                <TableHead>Target</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {installations.map((installation) => (
                <TableRow data-marketplace-installation-row={installation.id} key={installation.id}>
                  <TableCell>
                    {installation.plugin_name} {installation.version}
                  </TableCell>
                  <TableCell>{installation.target_agent_name ?? installation.environment_id}</TableCell>
                  <TableCell>
                    <StatusBadge status={installation.status} />
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      disabled={installation.status !== "installed"}
                      onClick={() => onUninstall(installation.id)}
                      type="button"
                      variant="outline"
                    >
                      Uninstall
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

function ReviewsPanel({
  filters,
  onDecision,
  onFilter,
  reviews
}: {
  filters: MarketplaceParams;
  onDecision: (reviewId: string, decision: "approved" | "rejected", payload: Record<string, unknown>) => void;
  onFilter: (filters: MarketplaceParams) => void;
  reviews: PluginReview[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Review Queue</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            onFilter(cleanParams(new FormData(event.currentTarget), ["status"]));
          }}
        >
          <SelectField defaultValue={String(filters.status ?? "")} label="Status" name="status" options={reviewStatuses} />
          <Button type="submit" variant="outline">
            Filter
          </Button>
        </form>
        {reviews.length === 0 ? (
          <EmptyState title="No reviews" description="Submit plugin versions for manual governance review." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Plugin</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Findings</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {reviews.map((review) => (
                <TableRow data-marketplace-review-row={review.id} key={review.id}>
                  <TableCell>{review.plugin_name ?? review.plugin_version_id}</TableCell>
                  <TableCell>
                    <StatusBadge status={review.status} />
                  </TableCell>
                  <TableCell>{review.findings.length}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap justify-end gap-2">
                      <ReviewDecisionForm
                        action="approved"
                        disabled={review.status !== "pending"}
                        onSubmit={(payload) => onDecision(review.id, "approved", payload)}
                      />
                      <ReviewDecisionForm
                        action="rejected"
                        disabled={review.status !== "pending"}
                        onSubmit={(payload) => onDecision(review.id, "rejected", payload)}
                      />
                    </div>
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

function SigningKeysPanel({
  keys,
  onCreate,
  onRevoke
}: {
  keys: PluginSigningKey[];
  onCreate: (payload: Record<string, unknown>) => void;
  onRevoke: (keyId: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Signing Keys</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="grid gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            onCreate(marketplaceSigningKeyPayloadFromForm(event.currentTarget));
            event.currentTarget.reset();
          }}
        >
          <Field label="Key Name" name="name" />
          <Field label="Public Key" name="public_key" />
          <Button type="submit">
            <KeyRound className="h-4 w-4" />
            Add Key
          </Button>
        </form>
        {keys.length === 0 ? (
          <EmptyState title="No signing keys" description="Register public keys for signature verification." />
        ) : (
          <div className="space-y-2">
            {keys.map((key) => (
              <div
                className="flex items-center justify-between gap-3 rounded-md border p-3"
                data-marketplace-signing-key-row={key.id}
                key={key.id}
              >
                <div>
                  <div className="font-medium">{key.name}</div>
                  <div className="text-xs text-muted-foreground">{key.public_key}</div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={key.status} />
                  <Button
                    disabled={key.status !== "active"}
                    onClick={() => onRevoke(key.id)}
                    type="button"
                    variant="outline"
                  >
                    Revoke
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function QualityTrustPanel({
  assessment,
  events,
  onRecompute,
  version
}: {
  assessment: PluginQualityAssessment | null;
  events: PluginTrustEvent[];
  onRecompute: (versionId: string, payload: Record<string, unknown>) => void;
  version: PluginVersion | null;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Quality And Trust</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-6 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">Latest Assessment</h3>
          {assessment ? (
            <div className="rounded-md border p-3" data-marketplace-quality-summary={assessment.id}>
              <div className="text-2xl font-semibold">{assessment.score}</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.entries(assessment.dimensions).map(([key, value]) => (
                  <Badge key={key} tone="muted">
                    {key}: {String(value)}
                  </Badge>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState title="No quality assessment" description="Run an assessment from the plugin detail panel." />
          )}
        </div>
        <div className="space-y-4">
          <form
            className="grid gap-3 md:grid-cols-3"
            onSubmit={(event) => {
              event.preventDefault();
              if (version) {
                onRecompute(version.id, marketplaceTrustPayloadFromForm(event.currentTarget));
              }
            }}
          >
            <Field defaultValue="5" label="Daily Active Users" name="daily_active_users" type="number" />
            <Field defaultValue="100" label="Invocations" name="total_invocations" type="number" />
            <Field defaultValue="0" label="Errors" name="error_count" type="number" />
            <Field defaultValue="0" label="Incidents" name="incident_count" type="number" />
            <Field defaultValue="7" label="Days Since Update" name="days_since_update" type="number" />
            <Field defaultValue="0" label="Adoption Trend" name="adoption_trend" type="number" />
            <Field label="Source Event" name="source_event_id" />
            <div className="flex items-end">
              <Button disabled={!version} type="submit">
                <BadgeCheck className="h-4 w-4" />
                Recompute Trust
              </Button>
            </div>
          </form>
          {events.length === 0 ? (
            <EmptyState title="No trust events" description="Usage signals create trust events here." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Reason</TableHead>
                  <TableHead>Delta</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Tier</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => (
                  <TableRow data-marketplace-trust-event-row={event.id} key={event.id}>
                    <TableCell>{event.reason}</TableCell>
                    <TableCell>{event.delta}</TableCell>
                    <TableCell>
                      {event.score_before}
                      {" -> "}
                      {event.score_after}
                    </TableCell>
                    <TableCell>{event.trust_tier}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function InstallGates({
  policyResult,
  version
}: {
  policyResult: PluginPolicyResult | null;
  version: PluginVersion;
}) {
  const gates = [
    { label: "Signature", state: version.signature_status === "signed" ? "pass" : "review" },
    { label: "Policy", state: policyResult?.result === "allowed" ? "pass" : policyResult?.result ?? "unchecked" },
    { label: "Trust", state: version.trust_tier }
  ];
  return (
    <div className="grid gap-2 md:grid-cols-3" data-marketplace-install-gates>
      {gates.map((gate) => (
        <div className="rounded-md border bg-muted/20 p-3" key={gate.label}>
          <div className="text-xs uppercase text-muted-foreground">{gate.label}</div>
          <div className="mt-1 font-medium">{gate.state}</div>
        </div>
      ))}
      {policyResult?.findings.length ? (
        <ul className="md:col-span-3" data-marketplace-policy-findings>
          {policyResult.findings.map((finding, index) => (
            <li className="text-sm text-muted-foreground" key={index}>
              {String(finding.code ?? finding.message ?? "finding")}: {String(finding.message ?? "")}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground md:col-span-3">No blocking findings from the latest policy check.</p>
      )}
    </div>
  );
}

function ReviewDecisionForm({
  action,
  disabled,
  onSubmit
}: {
  action: "approved" | "rejected";
  disabled: boolean;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  return (
    <form
      className="flex gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(marketplaceReviewDecisionPayloadFromForm(event.currentTarget));
      }}
    >
      <Input aria-label={`${action} reason`} className="w-36" name="decision_reason" placeholder="Reason" />
      <Button disabled={disabled} type="submit" variant="outline">
        {action === "approved" ? "Approve" : "Reject"}
      </Button>
    </form>
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
  readOnly,
  type = "text"
}: {
  defaultValue?: string;
  label: string;
  name: string;
  placeholder?: string;
  readOnly?: boolean;
  type?: string;
}) {
  const reactId = useId();
  const id = `${reactId}-${name}`;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <Input
        defaultValue={defaultValue}
        id={id}
        name={name}
        placeholder={placeholder}
        readOnly={readOnly}
        type={type}
      />
    </div>
  );
}

function TextAreaField({
  defaultValue,
  label,
  name,
  rows = 4
}: {
  defaultValue?: string;
  label: string;
  name: string;
  rows?: number;
}) {
  const reactId = useId();
  const id = `${reactId}-${name}`;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <textarea
        className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        defaultValue={defaultValue}
        id={id}
        name={name}
        rows={rows}
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
  const reactId = useId();
  const id = `${reactId}-${name}`;
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

function CheckboxField({ label, name }: { label: string; name: string }) {
  return (
    <label className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
      <input name={name} type="checkbox" />
      {label}
    </label>
  );
}

export function marketplaceImportPayloadFromValues(values: Record<string, unknown>) {
  return {
    manifest: parseObjectJson(String(values.manifest_json ?? "{}")),
    package_ref: optionalString(values.package_ref),
    status: String(values.status ?? "available").trim() || "available"
  };
}

export function marketplaceImportPayloadFromForm(form: HTMLFormElement) {
  return marketplaceImportPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function marketplacePolicyPayloadFromValues(values: Record<string, unknown>) {
  return {
    require_signature: Boolean(values.require_signature),
    require_review_approval: Boolean(values.require_review_approval),
    allowed_plugin_types: commaList(values.allowed_plugin_types),
    allowed_capabilities: commaList(values.allowed_capabilities),
    allowed_organizations: commaList(values.allowed_organizations)
  };
}

export function marketplacePolicyPayloadFromForm(form: HTMLFormElement) {
  return marketplacePolicyPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function marketplaceInstallPayloadFromValues(values: Record<string, unknown>) {
  return {
    plugin_version_id: String(values.plugin_version_id ?? "").trim(),
    environment_id: String(values.environment_id ?? "").trim(),
    target_agent_id: optionalString(values.target_agent_id)
  };
}

export function marketplaceInstallPayloadFromForm(form: HTMLFormElement) {
  return marketplaceInstallPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function marketplaceReviewSubmitPayloadFromValues(values: Record<string, unknown>) {
  const code = optionalString(values.code) ?? "manual_review";
  const message = optionalString(values.message) ?? "Manual review requested";
  return { findings: [{ code, message }] };
}

export function marketplaceReviewSubmitPayloadFromForm(form: HTMLFormElement) {
  return marketplaceReviewSubmitPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function marketplaceReviewDecisionPayloadFromValues(values: Record<string, unknown>) {
  return { decision_reason: optionalString(values.decision_reason) };
}

export function marketplaceReviewDecisionPayloadFromForm(form: HTMLFormElement) {
  return marketplaceReviewDecisionPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function marketplaceSigningKeyPayloadFromValues(values: Record<string, unknown>) {
  return {
    name: String(values.name ?? "").trim(),
    public_key: String(values.public_key ?? "").trim()
  };
}

export function marketplaceSigningKeyPayloadFromForm(form: HTMLFormElement) {
  return marketplaceSigningKeyPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function marketplaceTrustPayloadFromValues(values: Record<string, unknown>) {
  return {
    daily_active_users: integerValue(values.daily_active_users),
    total_invocations: integerValue(values.total_invocations),
    error_count: integerValue(values.error_count),
    incident_count: integerValue(values.incident_count),
    days_since_update: integerValue(values.days_since_update),
    adoption_trend: numberValue(values.adoption_trend),
    source_event_id: optionalString(values.source_event_id)
  };
}

export function marketplaceTrustPayloadFromForm(form: HTMLFormElement) {
  return marketplaceTrustPayloadFromValues(Object.fromEntries(new FormData(form)));
}

function cleanParams(form: FormData, keys: string[]) {
  return Object.fromEntries(
    keys
      .map((key) => [key, String(form.get(key) ?? "").trim()])
      .filter(([, value]) => value !== "")
  );
}

function commaList(value: unknown) {
  const raw = String(value ?? "").trim();
  if (!raw) {
    return null;
  }
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function optionalString(value: unknown) {
  const normalized = String(value ?? "").trim();
  return normalized || null;
}

function integerValue(value: unknown) {
  const parsed = Number.parseInt(String(value ?? "0"), 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

function numberValue(value: unknown) {
  const parsed = Number.parseFloat(String(value ?? "0"));
  return Number.isFinite(parsed) ? parsed : 0;
}

function parseObjectJson(value: string) {
  return parseJsonObjectField(value, "Manifest JSON", { emptyFallback: {} });
}

function sampleManifest() {
  return {
    name: "claims-workflow-pack",
    version: "1.0.0",
    description: "Claims workflow governance pack",
    publisher: "Ophanix",
    plugin_type: "integration",
    package_ref: "registry://claims-workflow-pack",
    signature_status: "signed",
    required_capabilities: ["claims.lookup"],
    permissions: ["mcp.invoke"]
  };
}
