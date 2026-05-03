import { Archive, FileCheck2, Play, ScrollText, XCircle } from "lucide-react";
import { useState, type ReactNode } from "react";

import {
  attestArtifact,
  cancelWorkflowRun,
  createArtifact,
  createArtifactLink,
  createWorkflowRun,
  downloadArtifact,
  useArtifact,
  useArtifacts,
  useWorkflowMutation,
  useWorkflowRun,
  useWorkflowRuns,
  useWorkflows,
  type Artifact,
  type ArtifactDownload,
  type WorkflowDefinition,
  type WorkflowRun
} from "../../api/workflows";
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

const runStatuses = ["", "queued", "running", "succeeded", "failed", "cancelled"];
const artifactTypes = ["", "workflow.output", "compliance.report", "audit.export", "sbom"];
const linkTargetTypes = ["workflow_run", "compliance_report", "audit_export", "plugin_assessment", "evidence_item"];

export function WorkflowsPage() {
  const [runFilters, setRunFilters] = useState<Record<string, string>>({});
  const [artifactFilters, setArtifactFilters] = useState<Record<string, string>>({});
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [downloadResult, setDownloadResult] = useState<ArtifactDownload | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const workflowsQuery = useWorkflows({ enabled: true });
  const runsQuery = useWorkflowRuns(runFilters);
  const artifactsQuery = useArtifacts(artifactFilters);
  const mutation = useWorkflowMutation();

  const workflows = workflowsQuery.data ?? [];
  const runs = runsQuery.data ?? [];
  const artifacts = artifactsQuery.data ?? [];
  const activeWorkflowId = selectedWorkflowId ?? workflows[0]?.id ?? null;
  const activeWorkflow = workflows.find((workflow) => workflow.id === activeWorkflowId) ?? null;
  const activeRunId = selectedRunId ?? runs[0]?.id ?? null;
  const runDetailQuery = useWorkflowRun(activeRunId);
  const activeRun = runDetailQuery.data ?? runs.find((run) => run.id === activeRunId) ?? null;
  const activeArtifactId = selectedArtifactId ?? artifacts[0]?.id ?? null;
  const artifactDetailQuery = useArtifact(activeArtifactId);
  const activeArtifact =
    artifactDetailQuery.data ?? artifacts.find((artifact) => artifact.id === activeArtifactId) ?? null;

  async function runTask(label: string, task: () => Promise<unknown>) {
    try {
      await mutation.mutateAsync(task);
      setMessage(label);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed");
    }
  }

  async function runResultTask<T>(label: string, task: () => Promise<T>, onResult: (value: T) => void) {
    try {
      const result = (await mutation.mutateAsync(task)) as T;
      onResult(result);
      setMessage(label);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed");
    }
  }

  return (
    <>
      <PageHeader
        title="Workflows"
        description="Run governed product workflows, inspect logs, and manage artifacts and attestations."
      />
      <div className="space-y-6 p-6" data-workflow-workspace>
        {message ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
            {message}
          </div>
        ) : null}
        <WorkflowSummary artifacts={artifacts} runs={runs} workflows={workflows} />
        <div className="grid gap-6 2xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <WorkflowCatalog
            onSelect={setSelectedWorkflowId}
            selectedWorkflowId={activeWorkflowId}
            workflows={workflows}
          />
          <WorkflowRunPanel
            onRun={(workflowId, payload) =>
              runResultTask(
                "Workflow run created",
                () => createWorkflowRun(workflowId, payload),
                (run) => setSelectedRunId(run.id)
              )
            }
            workflow={activeWorkflow}
          />
        </div>
        <WorkflowRunsPanel
          filters={runFilters}
          onCancel={(runId) => runTask("Workflow run cancelled", () => cancelWorkflowRun(runId))}
          onFilter={setRunFilters}
          onSelect={setSelectedRunId}
          runs={runs}
          selectedRun={activeRun}
        />
        <WorkflowArtifactsPanel
          artifact={activeArtifact}
          artifacts={artifacts}
          downloadResult={downloadResult}
          onAttest={(artifactId, payload) =>
            runTask("Artifact attested", () => attestArtifact(artifactId, payload))
          }
          onDownload={(artifactId) =>
            runResultTask("Artifact downloaded", () => downloadArtifact(artifactId), setDownloadResult)
          }
          onFilter={setArtifactFilters}
          onLink={(artifactId, payload) =>
            runTask("Artifact linked", () => createArtifactLink(artifactId, payload))
          }
          onSelect={setSelectedArtifactId}
          onUpload={(payload) =>
            runResultTask(
              "Artifact uploaded",
              () => createArtifact(payload),
              (artifact) => setSelectedArtifactId(artifact.id)
            )
          }
        />
      </div>
    </>
  );
}

function WorkflowSummary({
  artifacts,
  runs,
  workflows
}: {
  artifacts: Artifact[];
  runs: WorkflowRun[];
  workflows: WorkflowDefinition[];
}) {
  return (
    <div className="grid gap-4 md:grid-cols-4">
      <Metric icon={<ScrollText className="h-4 w-4" />} label="Workflows" value={workflows.length} />
      <Metric icon={<Play className="h-4 w-4" />} label="Runs" value={runs.length} />
      <Metric icon={<Archive className="h-4 w-4" />} label="Artifacts" value={artifacts.length} />
      <Metric icon={<FileCheck2 className="h-4 w-4" />} label="Attestations" value={artifacts.reduce((count, artifact) => count + artifact.attestations.length, 0)} />
    </div>
  );
}

function WorkflowCatalog({
  onSelect,
  selectedWorkflowId,
  workflows
}: {
  onSelect: (workflowId: string) => void;
  selectedWorkflowId: string | null;
  workflows: WorkflowDefinition[];
}) {
  return (
    <Card data-workflow-catalog>
      <CardHeader>
        <CardTitle>Workflow Catalog</CardTitle>
      </CardHeader>
      <CardContent>
        {workflows.length === 0 ? (
          <EmptyState title="No workflows" description="Workflow definitions are seeded by the backend." />
        ) : (
          <Table data-workflow-catalog-table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Command</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {workflows.map((workflow) => (
                <TableRow data-workflow-row={workflow.id} key={workflow.id}>
                  <TableCell>
                    <div className="font-medium">{workflow.name}</div>
                    <div className="text-xs text-muted-foreground">{workflow.id}</div>
                  </TableCell>
                  <TableCell>{workflow.workflow_type}</TableCell>
                  <TableCell>{workflow.command_ref}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      aria-pressed={workflow.id === selectedWorkflowId}
                      onClick={() => onSelect(workflow.id)}
                      type="button"
                      variant={workflow.id === selectedWorkflowId ? "default" : "outline"}
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

function WorkflowRunPanel({
  onRun,
  workflow
}: {
  onRun: (workflowId: string, payload: Record<string, unknown>) => void;
  workflow: WorkflowDefinition | null;
}) {
  const fields = workflowFields(workflow);
  return (
    <Card data-workflow-runner>
      <CardHeader>
        <CardTitle>Run Workflow</CardTitle>
      </CardHeader>
      <CardContent>
        {!workflow ? (
          <EmptyState title="No workflow selected" description="Select a workflow before creating a run." />
        ) : (
          <form
            className="grid gap-3"
            data-workflow-run-form
            onSubmit={(event) => {
              event.preventDefault();
              onRun(workflow.id, workflowRunPayloadFromForm(event.currentTarget, workflow));
            }}
          >
            {fields.map((field) => (
              <Field
                defaultValue={String(field.schema.default ?? "")}
                key={field.name}
                label={field.label}
                name={field.name}
                required={field.required}
              />
            ))}
            <label className="flex items-center gap-2 text-sm">
              <input defaultChecked name="run_immediately" type="checkbox" value="true" />
              Run immediately
            </label>
            <Button type="submit">
              <Play className="h-4 w-4" />
              Run Workflow
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

function WorkflowRunsPanel({
  filters,
  onCancel,
  onFilter,
  onSelect,
  runs,
  selectedRun
}: {
  filters: Record<string, string>;
  onCancel: (runId: string) => void;
  onFilter: (filters: Record<string, string>) => void;
  onSelect: (runId: string) => void;
  runs: WorkflowRun[];
  selectedRun: WorkflowRun | null;
}) {
  return (
    <Card data-workflow-runs>
      <CardHeader>
        <CardTitle>Workflow Runs</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            onFilter(cleanParams(new FormData(event.currentTarget), ["status"]));
          }}
        >
          <SelectField defaultValue={filters.status ?? ""} label="Run Status" name="status" options={runStatuses} />
          <Button type="submit" variant="outline">
            Filter
          </Button>
        </form>
        {runs.length === 0 ? (
          <EmptyState title="No runs" description="Run a workflow to populate logs." />
        ) : (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <Table data-workflow-run-table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Exit</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => (
                  <TableRow data-workflow-run-row={run.id} key={run.id}>
                    <TableCell>{run.id}</TableCell>
                    <TableCell>
                      <StatusBadge status={run.status} />
                    </TableCell>
                    <TableCell>{run.exit_code ?? "n/a"}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button onClick={() => onSelect(run.id)} type="button" variant="outline">
                          Open
                        </Button>
                        <Button
                          disabled={!["queued", "running"].includes(run.status)}
                          onClick={() => onCancel(run.id)}
                          type="button"
                          variant="outline"
                        >
                          <XCircle className="h-4 w-4" />
                          Cancel
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {selectedRun ? <WorkflowRunDetail run={selectedRun} /> : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function WorkflowRunDetail({ run }: { run: WorkflowRun }) {
  return (
    <section className="rounded-md border p-4" data-workflow-run-detail={run.id}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">{run.id}</h3>
          <p className="text-sm text-muted-foreground">{run.command_ref ?? run.workflow_type}</p>
        </div>
        <StatusBadge status={run.status} />
      </div>
      <pre className="mt-3 max-h-40 overflow-auto rounded-md bg-muted p-3 text-xs" data-workflow-run-summary={run.id}>
        {JSON.stringify(run.summary, null, 2)}
      </pre>
      {run.logs.length === 0 ? (
        <EmptyState title="No logs" description="Run has not emitted logs." />
      ) : (
        <Table data-workflow-run-logs={run.id}>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>Stream</TableHead>
              <TableHead>Message</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {run.logs.map((log) => (
              <TableRow data-workflow-log-row={log.id} key={log.id}>
                <TableCell>{log.line_number}</TableCell>
                <TableCell>{log.stream}</TableCell>
                <TableCell>{log.message}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}

function WorkflowArtifactsPanel({
  artifact,
  artifacts,
  downloadResult,
  onAttest,
  onDownload,
  onFilter,
  onLink,
  onSelect,
  onUpload
}: {
  artifact: Artifact | null;
  artifacts: Artifact[];
  downloadResult: ArtifactDownload | null;
  onAttest: (artifactId: string, payload: Record<string, unknown>) => void;
  onDownload: (artifactId: string) => void;
  onFilter: (filters: Record<string, string>) => void;
  onLink: (artifactId: string, payload: Record<string, unknown>) => void;
  onSelect: (artifactId: string) => void;
  onUpload: (payload: Record<string, unknown>) => void;
}) {
  return (
    <Card data-workflow-artifacts>
      <CardHeader>
        <CardTitle>Artifacts And Attestations</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,0.35fr)_minmax(0,0.65fr)]">
          <div className="space-y-4">
            <form
              className="grid gap-3"
              data-artifact-upload-form
              onSubmit={(event) => {
                event.preventDefault();
                onUpload(artifactUploadPayloadFromForm(event.currentTarget));
                event.currentTarget.reset();
              }}
            >
              <Field label="Artifact Name" name="name" placeholder="out.json" />
              <SelectField label="Artifact Type" name="artifact_type" options={artifactTypes.filter(Boolean)} />
              <Field defaultValue="application/json" label="Content Type" name="content_type" />
              <TextAreaField defaultValue="{}" label="Content" name="content" />
              <Button type="submit">Upload Artifact</Button>
            </form>
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                onFilter(cleanParams(new FormData(event.currentTarget), ["artifact_type"]));
              }}
            >
              <SelectField label="Filter Artifact Type" name="artifact_type" options={artifactTypes} />
              <Button type="submit" variant="outline">
                Filter
              </Button>
            </form>
          </div>
          <div className="space-y-4">
            {artifacts.length === 0 ? (
              <EmptyState title="No artifacts" description="Workflow outputs and report evidence appear here." />
            ) : (
              <Table data-workflow-artifact-table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Checksum</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {artifacts.map((item) => (
                    <TableRow data-workflow-artifact-row={item.id} key={item.id}>
                      <TableCell>{item.name}</TableCell>
                      <TableCell>{item.artifact_type}</TableCell>
                      <TableCell>{item.checksum.slice(0, 12)}</TableCell>
                      <TableCell className="text-right">
                        <Button onClick={() => onSelect(item.id)} type="button" variant="outline">
                          Open
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            {artifact ? (
              <WorkflowArtifactDetail
                artifact={artifact}
                downloadResult={downloadResult}
                onAttest={onAttest}
                onDownload={onDownload}
                onLink={onLink}
              />
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function WorkflowArtifactDetail({
  artifact,
  downloadResult,
  onAttest,
  onDownload,
  onLink
}: {
  artifact: Artifact;
  downloadResult: ArtifactDownload | null;
  onAttest: (artifactId: string, payload: Record<string, unknown>) => void;
  onDownload: (artifactId: string) => void;
  onLink: (artifactId: string, payload: Record<string, unknown>) => void;
}) {
  const activeDownload = downloadResult?.artifact.id === artifact.id ? downloadResult : null;
  return (
    <section className="rounded-md border p-4" data-workflow-artifact-detail={artifact.id}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">{artifact.name}</h3>
          <p className="text-sm text-muted-foreground">{artifact.storage_uri}</p>
        </div>
        <Button onClick={() => onDownload(artifact.id)} type="button" variant="outline">
          Download
        </Button>
      </div>
      {activeDownload ? (
        <output className="mt-3 block rounded-md bg-muted p-2 text-sm" data-workflow-artifact-download-result={artifact.id}>
          {activeDownload.metadata.checksum_verified ? "checksum verified" : "downloaded"} {activeDownload.content_base64}
        </output>
      ) : null}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <h4 className="text-sm font-semibold">Links</h4>
          {artifact.links.length === 0 ? (
            <EmptyState title="No links" description="Attach artifacts to product evidence." />
          ) : (
            <ul className="space-y-2" data-workflow-artifact-links={artifact.id}>
              {artifact.links.map((link) => (
                <li className="rounded-md bg-muted p-2 text-sm" key={link.id}>
                  {link.target_type}:{link.target_id} <Badge tone="muted">{link.link_type}</Badge>
                </li>
              ))}
            </ul>
          )}
          <form
            className="mt-3 grid gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              onLink(artifact.id, artifactLinkPayloadFromForm(event.currentTarget));
            }}
          >
            <SelectField label="Link Target Type" name="target_type" options={linkTargetTypes} />
            <Field label="Link Target ID" name="target_id" />
            <Field defaultValue="evidence" label="Link Type" name="link_type" />
            <Button type="submit" variant="outline">
              Link Artifact
            </Button>
          </form>
        </div>
        <div>
          <h4 className="text-sm font-semibold">Attestations</h4>
          {artifact.attestations.length === 0 ? (
            <EmptyState title="No attestations" description="Reviewer attestations appear here." />
          ) : (
            <ul className="space-y-2" data-workflow-artifact-attestations={artifact.id}>
              {artifact.attestations.map((attestation) => (
                <li
                  className="rounded-md bg-muted p-2 text-sm"
                  data-workflow-artifact-attestation-row={attestation.id}
                  key={attestation.id}
                >
                  {attestation.statement}
                </li>
              ))}
            </ul>
          )}
          <form
            className="mt-3 grid gap-2"
            data-artifact-attest-form
            onSubmit={(event) => {
              event.preventDefault();
              onAttest(artifact.id, artifactAttestationPayloadFromForm(event.currentTarget));
            }}
          >
            <TextAreaField label="Statement" name="statement" />
            <Field label="Signature Ref" name="signature_ref" />
            <Button type="submit" variant="outline">
              Attest
            </Button>
          </form>
        </div>
      </div>
    </section>
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
  required = false,
  type = "text"
}: {
  defaultValue?: string;
  label: string;
  name: string;
  placeholder?: string;
  required?: boolean;
  type?: string;
}) {
  const id = `${name}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <Input
        defaultValue={defaultValue}
        id={id}
        name={name}
        placeholder={placeholder}
        required={required}
        type={type}
      />
    </div>
  );
}

function TextAreaField({
  defaultValue,
  label,
  name,
  required = false
}: {
  defaultValue?: string;
  label: string;
  name: string;
  required?: boolean;
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
        required={required}
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

export function workflowRunPayloadFromValues(
  workflow: WorkflowDefinition | null,
  values: Record<string, unknown> = {}
) {
  const schema = workflow?.input_schema ?? {};
  const properties = (schema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const required = new Set((schema.required as string[] | undefined) ?? []);
  const missing: string[] = [];
  const inputs: Record<string, string> = {};

  for (const [name, propertySchema] of Object.entries(properties)) {
    const submittedValue = values[name];
    const rawValue =
      submittedValue === undefined || submittedValue === null || String(submittedValue).trim() === ""
        ? propertySchema.default ?? ""
        : submittedValue;
    const value = String(rawValue).trim();
    if (value || required.has(name)) {
      inputs[name] = value;
    }
    if (required.has(name) && !value) {
      missing.push(name);
    }
  }

  if (missing.length > 0) {
    throw new Error(`Missing required workflow input: ${missing.join(", ")}`);
  }

  return {
    inputs,
    run_immediately: values.run_immediately !== "false" && values.run_immediately !== false
  };
}

export function workflowRunPayloadFromForm(form: HTMLFormElement, workflow: WorkflowDefinition | null) {
  return workflowRunPayloadFromValues(workflow, Object.fromEntries(new FormData(form)));
}

export function artifactUploadPayloadFromValues(values: Record<string, unknown> = {}) {
  const content = String(values.content ?? "").trim();
  if (!content) {
    throw new Error("Artifact content is required.");
  }
  return {
    name: String(values.name ?? "").trim(),
    artifact_type: String(values.artifact_type ?? "workflow.output").trim(),
    content_type: String(values.content_type ?? "application/octet-stream").trim(),
    content_base64: encodeUtf8Base64(content)
  };
}

export function artifactUploadPayloadFromForm(form: HTMLFormElement) {
  return artifactUploadPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function artifactLinkPayloadFromValues(values: Record<string, unknown> = {}) {
  return {
    target_type: String(values.target_type ?? "").trim(),
    target_id: String(values.target_id ?? "").trim(),
    link_type: String(values.link_type ?? "evidence").trim()
  };
}

export function artifactLinkPayloadFromForm(form: HTMLFormElement) {
  return artifactLinkPayloadFromValues(Object.fromEntries(new FormData(form)));
}

export function artifactAttestationPayloadFromValues(values: Record<string, unknown> = {}) {
  const statement = String(values.statement ?? "").trim();
  if (!statement) {
    throw new Error("Attestation statement is required.");
  }
  const signatureRef = String(values.signature_ref ?? "").trim();
  return {
    statement,
    signature_ref: signatureRef || null
  };
}

export function artifactAttestationPayloadFromForm(form: HTMLFormElement) {
  return artifactAttestationPayloadFromValues(Object.fromEntries(new FormData(form)));
}

function workflowFields(workflow: WorkflowDefinition | null) {
  const schema = workflow?.input_schema ?? {};
  const properties = (schema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const required = new Set((schema.required as string[] | undefined) ?? []);
  return Object.entries(properties).map(([name, propertySchema]) => ({
    name,
    schema: propertySchema,
    required: required.has(name),
    label: String(propertySchema.title ?? name)
  }));
}

function cleanParams(form: FormData, keys: string[]) {
  return Object.fromEntries(
    keys
      .map((key) => [key, String(form.get(key) ?? "").trim()])
      .filter(([, value]) => value !== "")
  );
}

function encodeUtf8Base64(value: string) {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return globalThis.btoa(binary);
}
