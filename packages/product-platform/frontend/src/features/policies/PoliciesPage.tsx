import {
  BookOpen,
  Download,
  FileCode2,
  Link2,
  Play,
  Radio,
  RotateCcw,
  Upload,
  X
} from "lucide-react";
import { useCallback, useMemo, useState, type FormEvent, type InputHTMLAttributes } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";

import { useAgents, type AgentSummary } from "../../api/agents";
import type { TenantContext } from "../../api/client";
import { useCurrentUserPrincipal } from "../../app/userContext";
import {
  activatePolicyVersion,
  archivePolicyVersion,
  createPolicyBinding,
  createPolicyException,
  exportPolicy,
  getPolicyEvaluation,
  importPolicy,
  lintPolicy,
  lintPolicyVersion,
  promotePolicyBinding,
  rollbackPolicyVersion,
  savePolicyDraftVersion,
  simulatePolicyEvaluation,
  usePolicies,
  usePolicyAffectedResources,
  usePolicyBindings,
  usePolicyEvaluationSummary,
  usePolicyEvaluations,
  usePolicyExceptions,
  usePolicyMutation,
  usePolicyDetail,
  type PolicyAffectedResources,
  type PolicyBinding,
  type PolicyDetail,
  type PolicyEvaluation,
  type PolicyEvaluationSummary,
  type PolicyException,
  type PolicyExport,
  type PolicyImportResult,
  type PolicyLintResult,
  type PolicyParams,
  type PolicySummary,
  type PolicyVersion
} from "../../api/policies";
import { scopedQueryKey, useTenantQueryScope } from "../../api/queryScope";
import { useEnvironments } from "../../api/system";
import type { Environment } from "../../api/types";
import { PageHeader } from "../../components/layout/PageHeader";
import { ActionFeedback, useActionFeedback } from "../../components/shared/ActionFeedback";
import { ConfirmDialog } from "../../components/shared/ConfirmDialog";
import { EmptyState } from "../../components/shared/EmptyState";
import { QueryErrorSummary } from "../../components/shared/ErrorState";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../../components/ui/dialog";
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
import { datetimeLocalToIso } from "../../lib/dates";
import { useEventStream } from "../../lib/eventSource";
import { parseJsonObjectField } from "../../lib/forms";
import { permissions, userHasPermission } from "../../lib/rbac";
import { cn } from "../../lib/utils";

const targetTypes = [
  "agent",
  "environment",
  "mcp-server",
  "mcp-tool",
  "runtime-action",
  "framework-connector",
  "discovery",
  "agent-group"
];

export function PoliciesPage() {
  const [filters, setFilters] = useState<PolicyParams>({});
  const [selectedPolicyId, setSelectedPolicyId] = useState(() => readPolicyIdFromUrl());
  const [editorLint, setEditorLint] = useState<PolicyLintResult | null>(null);
  const [editorBody, setEditorBody] = useState<string | null>(null);
  const [editorFormat, setEditorFormat] = useState("yaml");
  const [editorBackend, setEditorBackend] = useState("native");
  const [exported, setExported] = useState<PolicyExport | null>(null);
  const [evaluationFilters, setEvaluationFilters] = useState<PolicyParams>({});
  const [extraEvaluationFeed, setExtraEvaluationFeed] = useState<{
    scopeKey: string;
    rows: PolicyEvaluation[];
  }>({ rows: [], scopeKey: "" });
  const [selectedEvaluation, setSelectedEvaluation] = useState<{
    id: string | null;
    scopeKey: string;
  }>({ id: null, scopeKey: "" });
  const [simulationResult, setSimulationResult] = useState<PolicyEvaluation | null>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const { feedback, runWithFeedback } = useActionFeedback();
  const scope = useTenantQueryScope();
  const currentUser = useCurrentUserPrincipal();
  const canWritePolicies = userHasPermission(currentUser, permissions.POLICY_WRITE);
  const evaluationTenantScopeKey = `${scope.key.organizationId}:${scope.key.environmentId}`;
  const extraEvaluationRows = useMemo(
    () =>
      extraEvaluationFeed.scopeKey === evaluationTenantScopeKey ? extraEvaluationFeed.rows : [],
    [evaluationTenantScopeKey, extraEvaluationFeed]
  );
  const selectedEvaluationId =
    selectedEvaluation.scopeKey === evaluationTenantScopeKey ? selectedEvaluation.id : null;
  const selectEvaluationId = useCallback(
    (evaluationId: string | null) =>
      setSelectedEvaluation({ id: evaluationId, scopeKey: evaluationTenantScopeKey }),
    [evaluationTenantScopeKey]
  );
  const upsertExtraEvaluation = useCallback(
    (evaluation: PolicyEvaluation) =>
      setExtraEvaluationFeed((feed) => ({
        rows: upsertPolicyEvaluationFeed(
          feed.scopeKey === evaluationTenantScopeKey ? feed.rows : [],
          evaluation
        ),
        scopeKey: evaluationTenantScopeKey
      })),
    [evaluationTenantScopeKey]
  );

  const policiesQuery = usePolicies(filters);
  const policies = policiesQuery.data ?? [];
  const activePolicyId = selectedPolicyId ?? policies[0]?.id ?? null;
  const detailQuery = usePolicyDetail(activePolicyId);
  const selectedPolicy =
    detailQuery.data ??
    policies.find((policy) => policy.id === activePolicyId) ??
    policies[0] ??
    null;
  const affectedQuery = usePolicyAffectedResources(activePolicyId);
  const bindingsQuery = usePolicyBindings({});
  const exceptionsQuery = usePolicyExceptions({});
  const agentsQuery = useAgents({});
  const environmentsQuery = useEnvironments();
  const evaluationsQuery = usePolicyEvaluations(evaluationFilters);
  const summaryQuery = usePolicyEvaluationSummary(evaluationFilters);
  const evaluationStreamParams = useMemo(
    () => withSelectedTenant(evaluationFilters, scope.context),
    [evaluationFilters, scope.context]
  );
  const evaluationStreamQueryKeys = useMemo(
    () => [
      scopedQueryKey(["policies", "evaluations", evaluationFilters], scope),
      scopedQueryKey(["policies", "evaluations", "summary", evaluationFilters], scope)
    ],
    [evaluationFilters, scope]
  );
  const handlePolicyEvaluationStreamMessage = useCallback(
    (event: MessageEvent) => {
      const evaluation = parsePolicyEvaluationStreamEvent(event);
      if (evaluation && policyEvaluationMatchesFilters(evaluation, evaluationStreamParams)) {
        upsertExtraEvaluation(evaluation);
      }
    },
    [evaluationStreamParams, upsertExtraEvaluation]
  );
  const selectedEvaluationQuery = useQuery({
    enabled: Boolean(selectedEvaluationId),
    queryKey: scopedQueryKey(["policies", "evaluations", selectedEvaluationId], scope),
    queryFn: () => getPolicyEvaluation(selectedEvaluationId as string, scope.context)
  });
  const mutation = usePolicyMutation();
  const evaluationRows = useMemo(() => {
    const baseRows = evaluationsQuery.data ?? [];
    const matchingExtraRows = extraEvaluationRows.filter((evaluation) =>
      policyEvaluationMatchesFilters(evaluation, evaluationStreamParams)
    );
    return [...matchingExtraRows]
      .reverse()
      .reduce((rows, evaluation) => upsertPolicyEvaluationFeed(rows, evaluation), baseRows);
  }, [evaluationStreamParams, evaluationsQuery.data, extraEvaluationRows]);

  useEventStream({
    enabled: Boolean(scope.context.environmentId && scope.context.organizationId),
    eventName: "policy_evaluation",
    onMessage: handlePolicyEvaluationStreamMessage,
    params: evaluationStreamParams,
    path: "/policy-evaluations/stream",
    queryKeysToInvalidate: evaluationStreamQueryKeys
  });

  function selectPolicy(policyId: string) {
    setSelectedPolicyId(policyId);
    setEditorLint(null);
    setEditorBody(null);
    const url = new URL(window.location.href);
    url.searchParams.set("policy_id", policyId);
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}`);
  }

  async function runTask(label: string, task: (tenantContext: TenantContext) => Promise<unknown>) {
    await runWithFeedback(() => mutation.mutateAsync(task), {
      errorMessage: `${label} failed`,
      successMessage: label
    });
  }

  return (
    <>
      <PageHeader
        title="Policies"
        description="Policy library, editor, bindings, simulator, and evaluation feed."
      />
      <div className="space-y-6 p-6">
        <ActionFeedback feedback={feedback} />
        <QueryErrorSummary
          items={[
            {
              error: policiesQuery.error,
              isError: policiesQuery.isError,
              label: "Policy library",
              onRetry: () => void policiesQuery.refetch()
            },
            {
              error: detailQuery.error,
              isError: detailQuery.isError,
              label: "Policy detail",
              onRetry: () => void detailQuery.refetch()
            },
            {
              error: affectedQuery.error,
              isError: affectedQuery.isError,
              label: "Affected resources",
              onRetry: () => void affectedQuery.refetch()
            },
            {
              error: bindingsQuery.error,
              isError: bindingsQuery.isError,
              label: "Policy bindings",
              onRetry: () => void bindingsQuery.refetch()
            },
            {
              error: exceptionsQuery.error,
              isError: exceptionsQuery.isError,
              label: "Policy exceptions",
              onRetry: () => void exceptionsQuery.refetch()
            },
            {
              error: agentsQuery.error,
              isError: agentsQuery.isError,
              label: "Agents",
              onRetry: () => void agentsQuery.refetch()
            },
            {
              error: environmentsQuery.error,
              isError: environmentsQuery.isError,
              label: "Environments",
              onRetry: () => void environmentsQuery.refetch()
            },
            {
              error: evaluationsQuery.error,
              isError: evaluationsQuery.isError,
              label: "Policy evaluations",
              onRetry: () => void evaluationsQuery.refetch()
            },
            {
              error: summaryQuery.error,
              isError: summaryQuery.isError,
              label: "Evaluation summary",
              onRetry: () => void summaryQuery.refetch()
            },
            {
              error: selectedEvaluationQuery.error,
              isError: selectedEvaluationQuery.isError,
              label: "Evaluation detail",
              onRetry: () => void selectedEvaluationQuery.refetch()
            }
          ]}
        />
        <PolicyLibrary
          canWritePolicies={canWritePolicies}
          isActionPending={mutation.isPending}
          isLoading={policiesQuery.isLoading}
          onExport={async (policyId) => {
            const result = await runWithFeedback<PolicyExport>(
              () =>
                mutation.mutateAsync((tenantContext) =>
                  exportPolicy(policyId, null, tenantContext)
                ) as Promise<PolicyExport>,
              {
                errorMessage: "Policy export failed",
                successMessage: (value) => `Exported ${value.filename ?? policyId}`
              }
            );
            if (!result) {
              return;
            }
            setExported(result);
          }}
          onFilter={(params) => setFilters(params)}
          onImport={async (payload) => {
            const imported = await runWithFeedback<PolicyImportResult>(
              () =>
                mutation.mutateAsync((tenantContext) =>
                  importPolicy(payload, tenantContext)
                ) as Promise<PolicyImportResult>,
              {
                errorMessage: "Policy import failed",
                successMessage: (value) => `Imported ${value.policy.id}`
              }
            );
            if (!imported) {
              return;
            }
            const policyId = imported.policy.id;
            if (policyId) {
              selectPolicy(policyId);
            }
          }}
          onSelect={selectPolicy}
          policies={policies}
          selectedPolicyId={activePolicyId}
        />
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(28rem,0.8fr)]">
          <PolicyVersionHistory
            canWritePolicies={canWritePolicies}
            isActionPending={mutation.isPending}
            onVersionAction={async (action, versionId) => {
              if (!selectedPolicy?.id) {
                return;
              }
              const policyId = selectedPolicy.id;
              if (action === "activate") {
                await runTask("Policy version activated", (tenantContext) =>
                  activatePolicyVersion(policyId, versionId, tenantContext)
                );
              }
              if (action === "rollback") {
                await runTask("Policy version rolled back", (tenantContext) =>
                  rollbackPolicyVersion(policyId, versionId, tenantContext)
                );
              }
              if (action === "archive") {
                await runTask("Policy version archived", (tenantContext) =>
                  archivePolicyVersion(policyId, versionId, tenantContext)
                );
              }
            }}
            policy={selectedPolicy}
            versions={selectedPolicy?.versions ?? []}
          />
          <PolicyEditorPanel
            affected={affectedQuery.data ?? null}
            body={editorBody}
            backend={editorBackend}
            bodyFormat={editorFormat}
            canWritePolicies={canWritePolicies}
            isActionPending={mutation.isPending}
            lintResult={editorLint}
            onLint={async (payload) => {
              const result = await runWithFeedback<PolicyLintResult>(
                () =>
                  mutation.mutateAsync((tenantContext) =>
                    lintPolicy(payload, tenantContext)
                  ) as Promise<PolicyLintResult>,
                {
                  errorMessage: "Policy lint failed"
                }
              );
              if (!result) {
                return;
              }
              setEditorLint(result);
              setEditorBody(String(payload.body_text ?? ""));
              setEditorFormat(String(payload.body_format ?? "yaml"));
              setEditorBackend(String(payload.backend ?? "native"));
            }}
            onSave={async (payload) => {
              if (!selectedPolicy?.id) {
                return;
              }
              const version = await runWithFeedback<PolicyVersion>(
                async () => {
                  const saved = (await mutation.mutateAsync((tenantContext) =>
                    savePolicyDraftVersion(selectedPolicy.id, payload, tenantContext)
                  )) as PolicyVersion;
                  await mutation.mutateAsync((tenantContext) =>
                    lintPolicyVersion(selectedPolicy.id, saved.id, tenantContext)
                  );
                  return saved;
                },
                {
                  errorMessage: "Policy version save failed",
                  successMessage: (value) => `Saved v${value.version_number}`
                }
              );
              if (!version) {
                return;
              }
            }}
            policy={selectedPolicy}
          />
        </div>
        <PolicyBindingsPanel
          agents={agentsQuery.data ?? []}
          bindings={bindingsQuery.data ?? []}
          canWritePolicies={canWritePolicies}
          environments={environmentsQuery.data ?? []}
          exceptions={exceptionsQuery.data ?? []}
          isActionPending={mutation.isPending}
          onCreateBinding={async (payload) => {
            await runTask("Policy binding created", (tenantContext) =>
              createPolicyBinding(payload, tenantContext)
            );
          }}
          onCreateException={async (bindingId, payload) => {
            await runTask("Policy exception created", (tenantContext) =>
              createPolicyException(bindingId, payload, tenantContext)
            );
          }}
          onPromote={async (bindingId, payload) => {
            await runTask("Policy binding promoted", (tenantContext) =>
              promotePolicyBinding(bindingId, payload, tenantContext)
            );
          }}
          policies={policies}
          selectedPolicy={selectedPolicy}
        />
        <div className="grid gap-6 xl:grid-cols-[minmax(24rem,0.75fr)_minmax(0,1fr)]">
          <PolicySimulatorPanel
            canWritePolicies={canWritePolicies}
            error={simulationError}
            isActionPending={mutation.isPending}
            onError={setSimulationError}
            onSubmit={async (payload) => {
              try {
                const result = (await mutation.mutateAsync((tenantContext) =>
                  simulatePolicyEvaluation(payload, tenantContext)
                )) as PolicyEvaluation;
                setSimulationResult(result);
                setSimulationError(null);
                upsertExtraEvaluation(result);
              } catch (error) {
                setSimulationError(error instanceof Error ? error.message : "Simulation failed");
              }
            }}
            policies={policies}
            result={simulationResult}
            selectedPolicy={selectedPolicy}
          />
          <PolicyEvaluationFeed
            evaluations={evaluationRows}
            filters={evaluationFilters}
            onFilter={setEvaluationFilters}
            onClose={() => selectEvaluationId(null)}
            onOpen={selectEvaluationId}
            selectedEvaluation={
              selectedEvaluationQuery.data ??
              evaluationRows.find((evaluation) => evaluation.id === selectedEvaluationId) ??
              null
            }
            summary={summaryQuery.data ?? null}
          />
        </div>
        {exported ? <PolicyExportPanel exported={exported} /> : null}
      </div>
    </>
  );
}

function PolicyLibrary({
  canWritePolicies,
  isActionPending,
  isLoading,
  onExport,
  onFilter,
  onImport,
  onSelect,
  policies,
  selectedPolicyId
}: {
  canWritePolicies: boolean;
  isActionPending: boolean;
  isLoading: boolean;
  onExport: (policyId: string) => void;
  onFilter: (params: PolicyParams) => void;
  onImport: (payload: Record<string, unknown>) => void;
  onSelect: (policyId: string) => void;
  policies: PolicySummary[];
  selectedPolicyId: string | null;
}) {
  function submitFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter(
      cleanParamsFromForm(event.currentTarget, [
        "scope",
        "status",
        "backend",
        "owner_user_id",
        "tag"
      ])
    );
  }

  function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onImport({
      name: formString(form, "name"),
      source_path: formString(form, "source_path"),
      body_format: formString(form, "body_format") || "yaml",
      body_text: formString(form, "body_text"),
      scope: formString(form, "scope") || "agent",
      backend: formString(form, "backend") || "native",
      tags: formString(form, "tags")
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean)
    });
  }

  return (
    <Card data-policy-workspace>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              Policy Library
            </CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              {policies.length} policies indexed for the current organization.
            </p>
          </div>
          <Badge tone={isLoading ? "warning" : "success"}>{isLoading ? "Loading" : "Ready"}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <form className="grid gap-3 md:grid-cols-6" onSubmit={submitFilter}>
          <SelectField
            label="Scope"
            name="scope"
            options={["", "agent", "mcp-tool", "runtime-action", "environment"]}
          />
          <SelectField label="Status" name="status" options={["", "draft", "active", "archived"]} />
          <SelectField label="Backend" name="backend" options={["", "native", "opa", "cedar"]} />
          <Field label="Owner" name="owner_user_id" placeholder="user id" />
          <Field label="Tag" name="tag" placeholder="safety" />
          <div className="flex items-end">
            <Button type="submit" variant="outline">
              Filter
            </Button>
          </div>
        </form>
        {policies.length ? (
          <div className="overflow-x-auto">
            <Table data-policy-table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Scope</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>Active</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {policies.map((policy) => (
                  <TableRow
                    className={cn(policy.id === selectedPolicyId && "bg-muted/60")}
                    data-policy-row={policy.id}
                    key={policy.id}
                  >
                    <TableCell>
                      <strong>{policy.name}</strong>
                      <small className="block text-muted-foreground">{policy.slug}</small>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {(policy.tags ?? []).map((tag) => (
                          <Badge key={tag} tone="muted">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>{policy.scope}</TableCell>
                    <TableCell>
                      <StatusBadge status={policy.status} />
                    </TableCell>
                    <TableCell>{policy.owner_user_id ?? "unassigned"}</TableCell>
                    <TableCell>
                      {policy.active_version_number ? `v${policy.active_version_number}` : "none"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        <Button onClick={() => onSelect(policy.id)} type="button" variant="outline">
                          Open
                        </Button>
                        <Button onClick={() => onExport(policy.id)} type="button" variant="ghost">
                          <Download className="h-4 w-4" />
                          Export
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <EmptyState description="Import a policy to populate the library." title="No policies" />
        )}
        {canWritePolicies ? (
          <form
            className="grid gap-3 rounded-md border bg-muted/20 p-4 md:grid-cols-6"
            onSubmit={submitImport}
          >
            <Field label="Name" name="name" placeholder="Inline Policy" />
            <Field
              className="md:col-span-2"
              label="Source path"
              name="source_path"
              placeholder="packages/agent-os/examples/policies/default.yaml"
            />
            <SelectField
              label="Format"
              name="body_format"
              options={["yaml", "json", "rego", "cedar"]}
            />
            <SelectField
              label="Scope"
              name="scope"
              options={["agent", "mcp-tool", "runtime-action", "environment"]}
            />
            <SelectField label="Backend" name="backend" options={["native", "opa", "cedar"]} />
            <Field
              className="md:col-span-2"
              label="Tags"
              name="tags"
              placeholder="safety, runtime"
            />
            <label className="space-y-1 md:col-span-4">
              <span className="text-sm font-medium">Body</span>
              <textarea
                className="min-h-28 w-full rounded-md border bg-background px-3 py-2 text-sm font-mono"
                name="body_text"
                spellCheck={false}
              />
            </label>
            <div className="flex items-end">
              <Button disabled={isActionPending} type="submit">
                <Upload className="h-4 w-4" />
                Import
              </Button>
            </div>
          </form>
        ) : null}
      </CardContent>
    </Card>
  );
}

function PolicyVersionHistory({
  canWritePolicies,
  isActionPending,
  onVersionAction,
  policy,
  versions
}: {
  canWritePolicies: boolean;
  isActionPending: boolean;
  onVersionAction: (action: "activate" | "rollback" | "archive", versionId: string) => void;
  policy: PolicyDetail | PolicySummary | null;
  versions: PolicyVersion[];
}) {
  return (
    <Card data-policy-version-drawer={policy?.id ?? "empty"}>
      <CardHeader>
        <CardTitle>Version History</CardTitle>
        <p className="text-sm text-muted-foreground">{policy?.name ?? "No selected policy"}</p>
      </CardHeader>
      <CardContent>
        {policy && versions.length ? (
          <div className="overflow-x-auto">
            <Table data-policy-version-table>
              <TableHeader>
                <TableRow>
                  <TableHead>Version</TableHead>
                  <TableHead>Backend</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Checksum</TableHead>
                  {canWritePolicies ? <TableHead>Actions</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {versions.map((version) => (
                  <TableRow data-policy-version-row={version.id} key={version.id}>
                    <TableCell>
                      <strong>v{version.version_number}</strong>
                      <small className="block text-muted-foreground">{version.body_format}</small>
                    </TableCell>
                    <TableCell>{version.backend}</TableCell>
                    <TableCell>
                      <StatusBadge status={version.status} />
                    </TableCell>
                    <TableCell className="max-w-44 truncate">{version.checksum ?? "n/a"}</TableCell>
                    {canWritePolicies ? (
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            disabled={isActionPending}
                            onClick={() => onVersionAction("activate", version.id)}
                            type="button"
                            variant="outline"
                          >
                            Activate
                          </Button>
                          <ConfirmDialog
                            confirmLabel="Rollback"
                            description={`Rollback ${policy.name} to version ${version.version_number}. This changes the active version for governed traffic.`}
                            isPending={isActionPending}
                            onConfirm={() => onVersionAction("rollback", version.id)}
                            title="Rollback policy version?"
                            trigger={
                              <Button disabled={isActionPending} type="button" variant="ghost">
                                <RotateCcw className="h-4 w-4" />
                                Rollback
                              </Button>
                            }
                          />
                          <ConfirmDialog
                            confirmLabel="Archive"
                            description={`Archive version ${version.version_number} of ${policy.name}. Archived versions should not be used for new policy changes.`}
                            isPending={isActionPending}
                            onConfirm={() => onVersionAction("archive", version.id)}
                            title="Archive policy version?"
                            trigger={
                              <Button disabled={isActionPending} type="button" variant="ghost">
                                Archive
                              </Button>
                            }
                          />
                        </div>
                      </TableCell>
                    ) : null}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <EmptyState description="Open a policy with version history." title="No versions" />
        )}
      </CardContent>
    </Card>
  );
}

function PolicyEditorPanel({
  affected,
  backend,
  body,
  bodyFormat,
  canWritePolicies,
  isActionPending,
  lintResult,
  onLint,
  onSave,
  policy
}: {
  affected: PolicyAffectedResources | null;
  backend: string;
  body: string | null;
  bodyFormat: string;
  canWritePolicies: boolean;
  isActionPending: boolean;
  lintResult: PolicyLintResult | null;
  onLint: (payload: Record<string, unknown>) => void;
  onSave: (payload: Record<string, unknown>) => void;
  policy: PolicyDetail | PolicySummary | null;
}) {
  const version = policy?.versions?.[0];
  const fatal = (lintResult?.issues ?? []).some(
    (issue) => issue.fatal || issue.severity === "error"
  );

  function payloadFromForm(form: HTMLFormElement) {
    const data = new FormData(form);
    return {
      body_format: formString(data, "body_format") || "yaml",
      body_text: formString(data, "body_text"),
      backend: formString(data, "backend") || "native"
    };
  }

  if (!policy) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Policy Editor</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState description="Select a policy from the library." title="No selected policy" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-policy-editor={policy.id}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileCode2 className="h-4 w-4" />
          Policy Editor
        </CardTitle>
        <p className="text-sm text-muted-foreground">{backendHint(backend)}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!canWritePolicies) {
              return;
            }
            onSave(payloadFromForm(event.currentTarget));
          }}
        >
          <div className="grid gap-3 md:grid-cols-3">
            <SelectField
              defaultValue={backend || version?.backend || "native"}
              label="Backend"
              name="backend"
              options={["native", "opa", "cedar"]}
            />
            <SelectField
              defaultValue={bodyFormat || version?.body_format || "yaml"}
              label="Format"
              name="body_format"
              options={["yaml", "json", "rego", "cedar"]}
            />
            {canWritePolicies ? (
              <div className="flex items-end">
                <Button
                  disabled={isActionPending}
                  onClick={(event) => {
                    const form = event.currentTarget.form;
                    if (form) {
                      onLint(payloadFromForm(form));
                    }
                  }}
                  type="button"
                  variant="outline"
                >
                  Lint
                </Button>
              </div>
            ) : null}
          </div>
          <label className="space-y-1">
            <span className="text-sm font-medium">Body</span>
            <textarea
              className="min-h-72 w-full rounded-md border bg-background px-3 py-2 text-sm font-mono"
              defaultValue={body ?? version?.body_text ?? ""}
              name="body_text"
              readOnly={!canWritePolicies}
              spellCheck={false}
            />
          </label>
          <PolicyLintPanel lintResult={lintResult} />
          {canWritePolicies ? (
            <Button data-policy-save-version disabled={fatal || isActionPending} type="submit">
              Save Version
            </Button>
          ) : null}
        </form>
        <AffectedResourcesPanel affected={affected} />
      </CardContent>
    </Card>
  );
}

function PolicyLintPanel({ lintResult }: { lintResult: PolicyLintResult | null }) {
  if (!lintResult) {
    return (
      <section className="rounded-md border p-3" data-policy-lint-panel>
        <h3 className="text-sm font-semibold">Lint Results</h3>
        <p className="mt-1 text-sm text-muted-foreground">Pending</p>
      </section>
    );
  }

  return (
    <section className="rounded-md border p-3" data-policy-lint-panel>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">Lint Results</h3>
        <Badge tone={(lintResult.error_count ?? 0) > 0 ? "danger" : "success"}>
          {lintResult.error_count ?? 0} errors
        </Badge>
        <Badge tone="warning">{lintResult.warning_count ?? 0} warnings</Badge>
      </div>
      {lintResult.issues?.length ? (
        <ol className="mt-3 space-y-2" data-policy-lint-issues>
          {lintResult.issues.map((issue) => (
            <li
              className="rounded-md bg-muted px-3 py-2 text-sm"
              data-policy-lint-issue={issue.code}
              key={`${issue.code}-${issue.path}`}
            >
              <div className="flex flex-wrap gap-2">
                <StatusBadge status={issue.severity} />
                <strong>{issue.code}</strong>
                <span className="text-muted-foreground">{issue.path}</span>
                {issue.line ? (
                  <span className="text-muted-foreground">line {issue.line}</span>
                ) : null}
              </div>
              <p className="mt-1">{issue.message}</p>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">Passed</p>
      )}
    </section>
  );
}

function AffectedResourcesPanel({ affected }: { affected: PolicyAffectedResources | null }) {
  const resources = affected?.resources ?? [];
  return (
    <section className="rounded-md border p-3" data-policy-affected-resources>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">Affected Resources</h3>
        {(affected?.active_binding_count ?? 0) > 0 ? (
          <Badge data-policy-active-binding-warning tone="warning">
            {affected?.active_binding_count} active bindings
          </Badge>
        ) : null}
      </div>
      {resources.length ? (
        <Table className="mt-3" data-policy-affected-table>
          <TableBody>
            {resources.map((resource) => (
              <TableRow
                data-policy-affected-resource={resource.target_id}
                key={`${resource.target_type}-${resource.target_id}`}
              >
                <TableCell>
                  <strong>{resource.label ?? resource.target_id}</strong>
                  <small className="block text-muted-foreground">{resource.target_id}</small>
                </TableCell>
                <TableCell>{resource.target_type}</TableCell>
                <TableCell>{resource.mode ?? "reference"}</TableCell>
                <TableCell>{resource.status ?? "unknown"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">Unbound</p>
      )}
    </section>
  );
}

function PolicyBindingsPanel({
  agents,
  bindings,
  canWritePolicies,
  environments,
  exceptions,
  isActionPending,
  onCreateBinding,
  onCreateException,
  onPromote,
  policies,
  selectedPolicy
}: {
  agents: AgentSummary[];
  bindings: PolicyBinding[];
  canWritePolicies: boolean;
  environments: Environment[];
  exceptions: PolicyException[];
  isActionPending: boolean;
  onCreateBinding: (payload: Record<string, unknown>) => void;
  onCreateException: (bindingId: string, payload: Record<string, unknown>) => void;
  onPromote: (bindingId: string, payload: Record<string, unknown>) => void;
  policies: PolicySummary[];
  selectedPolicy: PolicyDetail | PolicySummary | null;
}) {
  const targetOptions = useMemo(
    () => [
      ...agents.map((agent) => ({ id: agent.id, label: `${agent.name} - agent` })),
      ...environments.map((environment) => ({
        id: environment.id,
        label: `${environment.name} - environment`
      }))
    ],
    [agents, environments]
  );

  function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onCreateBinding({
      policy_id: formString(form, "policy_id"),
      policy_version_id: formString(form, "policy_version_id") || undefined,
      target_type: formString(form, "target_type") || "agent",
      target_id: formString(form, "target_id"),
      mode: formString(form, "mode") || "shadow",
      rollout_percentage: Number(formString(form, "rollout_percentage") || 100),
      priority: Number(formString(form, "priority") || 0)
    });
  }

  return (
    <Card data-policy-bindings-panel>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Link2 className="h-4 w-4" />
          Policy Bindings
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {canWritePolicies ? (
          <form className="grid gap-3 md:grid-cols-8" onSubmit={submitCreate}>
            <label className="space-y-1 md:col-span-2">
              <span className="text-sm font-medium">Policy</span>
              <select
                className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                defaultValue={selectedPolicy?.id ?? policies[0]?.id ?? ""}
                name="policy_id"
                required
              >
                {policies.map((policy) => (
                  <option key={policy.id} value={policy.id}>
                    {policy.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-sm font-medium">Version</span>
              <select
                className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                name="policy_version_id"
              >
                <option value="">Latest active</option>
                {(selectedPolicy?.versions ?? []).map((version) => (
                  <option key={version.id} value={version.id}>
                    v{version.version_number} - {version.status}
                  </option>
                ))}
              </select>
            </label>
            <SelectField label="Target Type" name="target_type" options={targetTypes} />
            <label className="space-y-1 md:col-span-2">
              <span className="text-sm font-medium">Target</span>
              <Input
                list="policy-binding-target-options"
                name="target_id"
                placeholder="agent id or resource key"
                required
              />
              <datalist id="policy-binding-target-options">
                {targetOptions.map((option) => (
                  <option key={option.id} label={option.label} value={option.id} />
                ))}
              </datalist>
            </label>
            <SelectField
              label="Mode"
              name="mode"
              options={["shadow", "audit-only", "enforce", "disabled"]}
            />
            <Field label="Rollout" name="rollout_percentage" type="number" defaultValue="100" />
            <Field label="Priority" name="priority" type="number" defaultValue="0" />
            <div className="flex items-end md:col-span-8">
              <Button disabled={isActionPending} type="submit">
                Create Binding
              </Button>
            </div>
          </form>
        ) : null}
        {bindings.length ? (
          <div className="overflow-x-auto">
            <Table className="min-w-[64rem]" data-policy-binding-matrix>
              <TableHeader>
                <TableRow>
                  <TableHead>Target</TableHead>
                  <TableHead>Policy</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Rollout</TableHead>
                  <TableHead>Exceptions</TableHead>
                  {canWritePolicies ? <TableHead>Controls</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {bindings.map((binding) => {
                  const policy = policies.find((item) => item.id === binding.policy_id);
                  const bindingExceptions = exceptions.filter(
                    (exception) => exception.binding_id === binding.id
                  );
                  return (
                    <TableRow data-policy-binding-row={binding.id} key={binding.id}>
                      <TableCell>
                        <strong>{targetLabel(binding, agents, environments)}</strong>
                        <small className="block text-muted-foreground">
                          {binding.target_type} - {binding.target_id}
                        </small>
                      </TableCell>
                      <TableCell>
                        <strong>{policy?.name ?? binding.policy_id}</strong>
                        <small className="block text-muted-foreground">
                          {binding.policy_version_id ?? "active"}
                        </small>
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={binding.mode} />
                      </TableCell>
                      <TableCell>{binding.rollout_percentage}%</TableCell>
                      <TableCell>
                        {bindingExceptions.length ? (
                          <ul className="space-y-1">
                            {bindingExceptions.map((exception) => (
                              <li key={exception.id}>
                                <span>{exception.reason}</span>
                                <small className="block text-muted-foreground">
                                  {exception.expires_at ?? "no expiry"}
                                </small>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          "none"
                        )}
                      </TableCell>
                      {canWritePolicies ? (
                        <TableCell>
                          <BindingControls
                            binding={binding}
                            isActionPending={isActionPending}
                            onCreateException={onCreateException}
                            onPromote={onPromote}
                          />
                        </TableCell>
                      ) : null}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        ) : (
          <EmptyState
            description="Create a binding to attach policy to a governed resource."
            title="No bindings"
          />
        )}
      </CardContent>
    </Card>
  );
}

function BindingControls({
  binding,
  isActionPending,
  onCreateException,
  onPromote
}: {
  binding: PolicyBinding;
  isActionPending: boolean;
  onCreateException: (bindingId: string, payload: Record<string, unknown>) => void;
  onPromote: (bindingId: string, payload: Record<string, unknown>) => void;
}) {
  return (
    <div className="space-y-3">
      <form
        className="grid min-w-72 gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          onPromote(binding.id, {
            mode: formString(form, "mode"),
            rollout_percentage: Number(
              formString(form, "rollout_percentage") || binding.rollout_percentage
            ),
            reason: formString(form, "reason")
          });
        }}
      >
        <div className="grid grid-cols-[1fr_5rem] gap-2">
          <select
            className="h-9 rounded-md border bg-background px-3 text-sm"
            defaultValue={binding.mode}
            name="mode"
          >
            {["shadow", "audit-only", "enforce", "disabled"].map((mode) => (
              <option key={mode} value={mode}>
                {mode}
              </option>
            ))}
          </select>
          <Input
            name="rollout_percentage"
            type="number"
            defaultValue={binding.rollout_percentage}
          />
        </div>
        <Input name="reason" placeholder="Promotion reason" required />
        <Button disabled={isActionPending} type="submit" variant="outline">
          Promote
        </Button>
      </form>
      <form
        className="grid min-w-72 gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          onCreateException(binding.id, {
            reason: formString(form, "reason"),
            expires_at: datetimeLocalToIso(formString(form, "expires_at")),
            target_id: formString(form, "target_id") || undefined,
            target_type: formString(form, "target_type") || undefined,
            no_expiry_approved: form.has("no_expiry_approved")
          });
        }}
      >
        <Input name="reason" placeholder="Exception reason" required />
        <Input name="expires_at" type="datetime-local" />
        <Input name="target_id" placeholder={binding.target_id} />
        <select className="h-9 rounded-md border bg-background px-3 text-sm" name="target_type">
          <option value="">Binding target</option>
          {targetTypes.map((targetType) => (
            <option key={targetType} value={targetType}>
              {targetType}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input name="no_expiry_approved" type="checkbox" />
          No expiry approved
        </label>
        <Button disabled={isActionPending} type="submit" variant="ghost">
          Exception
        </Button>
      </form>
    </div>
  );
}

function PolicySimulatorPanel({
  canWritePolicies,
  error,
  isActionPending,
  onError,
  onSubmit,
  policies,
  result,
  selectedPolicy
}: {
  canWritePolicies: boolean;
  error: string | null;
  isActionPending: boolean;
  onError: (message: string) => void;
  onSubmit: (payload: Record<string, unknown>) => void;
  policies: PolicySummary[];
  result: PolicyEvaluation | null;
  selectedPolicy: PolicyDetail | PolicySummary | null;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canWritePolicies) {
      return;
    }
    try {
      const form = new FormData(event.currentTarget);
      onSubmit({
        policy_id: formString(form, "policy_id") || undefined,
        policy_version_id: formString(form, "policy_version_id") || undefined,
        target_type: formString(form, "target_type") || undefined,
        target_id: formString(form, "target_id") || undefined,
        agent_id: formString(form, "agent_id") || undefined,
        action: formString(form, "action"),
        resource_type: formString(form, "resource_type") || undefined,
        resource_id: formString(form, "resource_id") || undefined,
        context: parseContextJson(formString(form, "context_json"))
      });
    } catch (parseError) {
      onError(parseError instanceof Error ? parseError.message : "Context JSON is invalid.");
    }
  }

  return (
    <Card data-policy-simulator>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Play className="h-4 w-4" />
          Policy Simulator
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form className="grid gap-3 md:grid-cols-2" onSubmit={submit}>
          <label className="space-y-1">
            <span className="text-sm font-medium">Policy</span>
            <select
              className="h-9 w-full rounded-md border bg-background px-3 text-sm"
              defaultValue={selectedPolicy?.id ?? ""}
              name="policy_id"
            >
              <option value="">Active binding</option>
              {policies.map((policy) => (
                <option key={policy.id} value={policy.id}>
                  {policy.name}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">Version</span>
            <select
              className="h-9 w-full rounded-md border bg-background px-3 text-sm"
              name="policy_version_id"
            >
              <option value="">Latest active</option>
              {(selectedPolicy?.versions ?? []).map((version) => (
                <option key={version.id} value={version.id}>
                  v{version.version_number} - {version.status}
                </option>
              ))}
            </select>
          </label>
          <SelectField
            label="Target Type"
            name="target_type"
            options={[
              "",
              "agent",
              "environment",
              "mcp-tool",
              "runtime-action",
              "framework-connector"
            ]}
          />
          <Field label="Target" name="target_id" placeholder="target id" />
          <Field label="Agent" name="agent_id" placeholder="agent id" />
          <Field label="Action" name="action" required defaultValue="mcp.tool_call" />
          <Field label="Resource Type" name="resource_type" placeholder="mcp-tool" />
          <Field label="Resource" name="resource_id" placeholder="demo.delete_customer" />
          <label className="space-y-1 md:col-span-2">
            <span className="text-sm font-medium">Context JSON</span>
            <textarea
              className="min-h-32 w-full rounded-md border bg-background px-3 py-2 text-sm font-mono"
              defaultValue="{}"
              name="context_json"
              spellCheck={false}
            />
          </label>
          <div className="md:col-span-2">
            <Button disabled={isActionPending || !canWritePolicies} type="submit">
              Simulate
            </Button>
          </div>
        </form>
        {error ? <p className="feedback-danger">{error}</p> : null}
        <PolicyEvaluationResult evaluation={result} />
      </CardContent>
    </Card>
  );
}

function PolicyEvaluationResult({ evaluation }: { evaluation: PolicyEvaluation | null }) {
  if (!evaluation) {
    return (
      <EmptyState description="Run a simulation to render a decision." title="No simulation" />
    );
  }
  return (
    <section
      className="rounded-md border p-3"
      data-policy-simulator-result={evaluation.id ?? "transient"}
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={evaluation.decision} />
        <strong>{evaluation.matched_rule ?? "default"}</strong>
        <span className="text-sm text-muted-foreground">{evaluation.latency_ms ?? 0}ms</span>
      </div>
      <p className="mt-2 text-sm">{evaluation.reason}</p>
    </section>
  );
}

function PolicyEvaluationFeed({
  evaluations,
  filters,
  onFilter,
  onClose,
  onOpen,
  selectedEvaluation,
  summary
}: {
  evaluations: PolicyEvaluation[];
  filters: PolicyParams;
  onFilter: (params: PolicyParams) => void;
  onClose: () => void;
  onOpen: (evaluationId: string) => void;
  selectedEvaluation: PolicyEvaluation | null;
  summary: PolicyEvaluationSummary | null;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFilter(
      cleanParamsFromForm(event.currentTarget, [
        "decision",
        "mode",
        "agent_id",
        "action",
        "policy_id",
        "correlation_id"
      ])
    );
  }

  return (
    <Card data-policy-evaluation-feed>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Radio className="h-4 w-4" />
          Policy Decisions
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <PolicyEvaluationSummaryPanel summary={summary} />
        <form className="grid gap-3 md:grid-cols-7" onSubmit={submit}>
          <SelectField
            defaultValue={String(filters.decision ?? "")}
            label="Decision"
            name="decision"
            options={["", "allow", "deny"]}
          />
          <SelectField
            defaultValue={String(filters.mode ?? "")}
            label="Mode"
            name="mode"
            options={["", "simulate", "live"]}
          />
          <Field label="Agent" name="agent_id" defaultValue={String(filters.agent_id ?? "")} />
          <Field label="Action" name="action" defaultValue={String(filters.action ?? "")} />
          <Field label="Policy" name="policy_id" defaultValue={String(filters.policy_id ?? "")} />
          <Field
            label="Correlation"
            name="correlation_id"
            defaultValue={String(filters.correlation_id ?? "")}
          />
          <div className="flex items-end">
            <Button type="submit" variant="outline">
              Filter
            </Button>
          </div>
        </form>
        {evaluations.length ? (
          <div className="overflow-x-auto">
            <Table data-policy-evaluation-table>
              <TableHeader>
                <TableRow>
                  <TableHead>Decision</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Policy</TableHead>
                  <TableHead>Rule</TableHead>
                  <TableHead>Latency</TableHead>
                  <TableHead>Correlation</TableHead>
                  <TableHead>Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {evaluations.map((evaluation) => (
                  <TableRow data-policy-evaluation-row={evaluation.id} key={evaluation.id}>
                    <TableCell>
                      <StatusBadge status={evaluation.decision} />
                      <small className="block text-muted-foreground">{evaluation.mode}</small>
                    </TableCell>
                    <TableCell>
                      <strong>{evaluation.action}</strong>
                      <small className="block text-muted-foreground">
                        {evaluation.agent_id ?? "no agent"}
                      </small>
                    </TableCell>
                    <TableCell>{evaluation.policy_id ?? evaluation.backend ?? "unbound"}</TableCell>
                    <TableCell>{evaluation.matched_rule ?? "default"}</TableCell>
                    <TableCell>{evaluation.latency_ms ?? 0}ms</TableCell>
                    <TableCell>{evaluation.correlation_id ?? "none"}</TableCell>
                    <TableCell>
                      <Button onClick={() => onOpen(evaluation.id)} type="button" variant="outline">
                        Open
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <EmptyState description="Run the simulator or adjust filters." title="No decisions" />
        )}
        <PolicyEvaluationDetailDrawer evaluation={selectedEvaluation} onClose={onClose} />
      </CardContent>
    </Card>
  );
}

function PolicyEvaluationSummaryPanel({ summary }: { summary: PolicyEvaluationSummary | null }) {
  return (
    <section className="rounded-md border p-3" data-policy-evaluation-summary>
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Total" value={String(summary?.total_count ?? 0)} />
        <Metric label="Decisions" value={inlineCountMap(summary?.decision_counts)} />
        <Metric label="Modes" value={inlineCountMap(summary?.mode_counts)} />
        <Metric label="Actions" value={inlineCountMap(summary?.action_counts)} />
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <PolicyDecisionTrendChart summary={summary} />
        <PolicyActionDistributionChart summary={summary} />
      </div>
    </section>
  );
}

function PolicyDecisionTrendChart({ summary }: { summary: PolicyEvaluationSummary | null }) {
  const rows = decisionTrendRows(summary);

  return (
    <div className="rounded-md border bg-muted/20 p-4" data-policy-evaluation-trends>
      <div className="text-sm font-medium">Decision Trend</div>
      <p className="text-xs text-muted-foreground">
        Allow and deny decisions over summary buckets.
      </p>
      {rows.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title="No decision trend"
            description="Run evaluations to populate trend buckets."
          />
        </div>
      ) : (
        <>
          <div className="mt-4 overflow-x-auto">
            <LineChart
              accessibilityLayer
              data={rows}
              height={220}
              margin={{ bottom: 8, left: 0, right: 16, top: 8 }}
              width={540}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="bucket" tickLine={false} />
              <YAxis allowDecimals={false} tickLine={false} />
              <Tooltip />
              <Line
                dataKey="allow"
                dot={{ r: 3 }}
                isAnimationActive={false}
                name="Allow"
                stroke="#16a34a"
                strokeWidth={2}
                type="monotone"
              />
              <Line
                dataKey="deny"
                dot={{ r: 3 }}
                isAnimationActive={false}
                name="Deny"
                stroke="#dc2626"
                strokeWidth={2}
                type="monotone"
              />
            </LineChart>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Bucket</TableHead>
                <TableHead>Total</TableHead>
                <TableHead>Allow</TableHead>
                <TableHead>Deny</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow data-policy-evaluation-trend={row.bucket} key={row.bucket}>
                  <TableCell>{row.bucket}</TableCell>
                  <TableCell>{row.total}</TableCell>
                  <TableCell>{row.allow}</TableCell>
                  <TableCell>{row.deny}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  );
}

function PolicyActionDistributionChart({ summary }: { summary: PolicyEvaluationSummary | null }) {
  const rows = actionDistributionRows(summary);

  return (
    <div className="rounded-md border bg-muted/20 p-4" data-policy-evaluation-action-chart>
      <div className="text-sm font-medium">Action Distribution</div>
      <p className="text-xs text-muted-foreground">Evaluation volume by governed action.</p>
      {rows.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title="No action counts"
            description="Action counts appear after evaluations run."
          />
        </div>
      ) : (
        <>
          <div className="mt-4 overflow-x-auto">
            <BarChart
              accessibilityLayer
              data={rows}
              height={220}
              margin={{ bottom: 28, left: 0, right: 16, top: 8 }}
              width={540}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                angle={-18}
                dataKey="action"
                height={56}
                interval={0}
                textAnchor="end"
                tickLine={false}
              />
              <YAxis allowDecimals={false} tickLine={false} />
              <Tooltip />
              <Bar
                dataKey="count"
                fill="#2563eb"
                isAnimationActive={false}
                name="Evaluations"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action</TableHead>
                <TableHead>Evaluations</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.action}>
                  <TableCell>{row.action}</TableCell>
                  <TableCell>{row.count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  );
}

function PolicyEvaluationDetailDrawer({
  evaluation,
  onClose
}: {
  evaluation: PolicyEvaluation | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={Boolean(evaluation)} onOpenChange={(open) => !open && onClose()}>
      {evaluation ? (
        <DialogContent
          aria-label={`Policy evaluation ${evaluation.id}`}
          className="left-auto right-0 top-0 h-dvh w-full max-w-xl translate-x-0 translate-y-0 overflow-y-auto rounded-none border-y-0 border-l border-r-0 bg-background p-6 shadow-xl"
          data-policy-evaluation-detail={evaluation.id}
          showCloseButton={false}
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <DialogTitle className="text-lg font-semibold">
                {evaluation.decision} - {evaluation.action}
              </DialogTitle>
              <DialogDescription className="mt-1 text-sm text-muted-foreground">
                {evaluation.correlation_id ?? "No correlation id"}
              </DialogDescription>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone="muted">{evaluation.backend ?? "native"}</Badge>
              <Button
                aria-label="Close policy evaluation detail"
                onClick={onClose}
                type="button"
                variant="ghost"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <dl className="mt-5 grid gap-3 text-sm md:grid-cols-2">
            <KeyValue label="Reason" value={evaluation.reason ?? "n/a"} />
            <KeyValue label="Policy" value={evaluation.policy_id ?? "unbound"} />
            <KeyValue label="Version" value={evaluation.policy_version_id ?? "n/a"} />
            <KeyValue label="Matched Rule" value={evaluation.matched_rule ?? "default"} />
            <KeyValue
              label="Resource"
              value={`${evaluation.resource_type ?? "n/a"} / ${evaluation.resource_id ?? "n/a"}`}
            />
            <KeyValue label="Latency" value={`${evaluation.latency_ms ?? 0}ms`} />
          </dl>
          <div className="mt-5">
            <div className="text-sm font-medium">Context Payload</div>
            <pre className="mt-2 max-h-72 overflow-auto rounded-md bg-muted p-3 text-xs">
              {JSON.stringify(evaluation.context ?? {}, null, 2)}
            </pre>
          </div>
        </DialogContent>
      ) : null}
    </Dialog>
  );
}

function PolicyExportPanel({ exported }: { exported: PolicyExport }) {
  return (
    <Card data-policy-export-panel>
      <CardHeader>
        <CardTitle>{exported.filename ?? "Policy export"}</CardTitle>
      </CardHeader>
      <CardContent>
        <pre className="max-h-96 overflow-auto rounded-md bg-muted p-4 text-xs">
          {exported.body_text}
        </pre>
      </CardContent>
    </Card>
  );
}

function Field({
  className,
  label,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <Label className={cn("space-y-1", className)}>
      <span>{label}</span>
      <Input {...props} />
    </Label>
  );
}

function SelectField({
  className,
  defaultValue,
  label,
  name,
  options
}: {
  className?: string;
  defaultValue?: string;
  label: string;
  name: string;
  options: string[];
}) {
  return (
    <label className={cn("space-y-1", className)}>
      <span className="text-sm font-medium">{label}</span>
      <select
        className="h-9 w-full rounded-md border bg-background px-3 text-sm"
        defaultValue={defaultValue}
        name={name}
      >
        {options.map((option) => (
          <option key={option || "any"} value={option}>
            {option || "Any"}
          </option>
        ))}
      </select>
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted p-3">
      <span className="text-xs uppercase text-muted-foreground">{label}</span>
      <strong className="mt-1 block text-sm">{value}</strong>
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

export function policyEvaluationMatchesFilters(
  evaluation: PolicyEvaluation,
  filters: PolicyParams = {}
) {
  return [
    "decision",
    "mode",
    "agent_id",
    "action",
    "policy_id",
    "correlation_id",
    "organization_id",
    "environment_id"
  ].every((key) => {
    const expected = filters[key];
    if (expected === undefined || expected === null || expected === "") {
      return true;
    }
    return String(evaluation[key as keyof PolicyEvaluation] ?? "") === String(expected);
  });
}

export function upsertPolicyEvaluationFeed(
  evaluations: PolicyEvaluation[],
  evaluation: PolicyEvaluation | null,
  limit = 50
) {
  if (!evaluation?.id) {
    return evaluations;
  }
  return [evaluation, ...evaluations.filter((row) => row.id !== evaluation.id)].slice(0, limit);
}

export function parsePolicyEvaluationStreamEvent(event: MessageEvent) {
  try {
    const payload = JSON.parse(event.data) as PolicyEvaluation;
    return payload && typeof payload === "object" ? payload : null;
  } catch {
    return null;
  }
}

function readPolicyIdFromUrl() {
  if (typeof window === "undefined") {
    return null;
  }
  return new URL(window.location.href).searchParams.get("policy_id");
}

function withSelectedTenant(params: PolicyParams, context: TenantContext) {
  return {
    ...params,
    ...(!params.organization_id && context.organizationId
      ? { organization_id: context.organizationId }
      : {}),
    ...(!params.environment_id && context.environmentId
      ? { environment_id: context.environmentId }
      : {})
  };
}

function formString(form: FormData, key: string) {
  return String(form.get(key) ?? "").trim();
}

function cleanParamsFromForm(form: HTMLFormElement, keys: string[]) {
  const data = new FormData(form);
  return Object.fromEntries(
    keys.map((key) => [key, formString(data, key)]).filter(([, value]) => value !== "")
  );
}

function parseContextJson(value: string) {
  return parseJsonObjectField(value, "Context JSON", { emptyFallback: {} });
}

function backendHint(backend: string) {
  if (backend === "opa") {
    return "OPA/Rego backend selected.";
  }
  if (backend === "cedar") {
    return "Cedar authorization backend selected.";
  }
  return "Native YAML/JSON evaluator selected.";
}

function targetLabel(binding: PolicyBinding, agents: AgentSummary[], environments: Environment[]) {
  if (binding.target_type === "agent") {
    return agents.find((agent) => agent.id === binding.target_id)?.name ?? binding.target_id;
  }
  if (binding.target_type === "environment") {
    return (
      environments.find((environment) => environment.id === binding.target_id)?.name ??
      binding.target_id
    );
  }
  return binding.target_id;
}

function decisionTrendRows(summary: PolicyEvaluationSummary | null) {
  return (summary?.time_buckets ?? []).map((bucket) => ({
    allow: bucket.decision_counts?.allow ?? 0,
    bucket: bucket.bucket,
    deny: bucket.decision_counts?.deny ?? 0,
    total: bucket.total_count ?? 0
  }));
}

function actionDistributionRows(summary: PolicyEvaluationSummary | null) {
  return Object.entries(summary?.action_counts ?? {})
    .map(([action, count]) => ({ action, count }))
    .filter((row) => row.count > 0)
    .sort((left, right) => right.count - left.count || left.action.localeCompare(right.action));
}

function inlineCountMap(counts?: Record<string, number>) {
  const entries = Object.entries(counts ?? {});
  return entries.length ? entries.map(([key, value]) => `${key}: ${value}`).join(", ") : "none";
}
