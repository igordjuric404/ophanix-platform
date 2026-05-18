import { ChevronLeft, ChevronRight, RefreshCw, X } from "lucide-react";
import { useState, type FormEvent } from "react";

import {
  useToolRuntimeActionDetail,
  useToolRuntimeActions,
  type ToolRuntimeAction,
  type ToolRuntimeActionDetail
} from "../../api/toolRuntime";
import { PageHeader } from "../../components/layout/PageHeader";
import { EmptyState } from "../../components/shared/EmptyState";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
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

const pageSize = 25;
const filterKeys = [
  "action_status",
  "decision_id",
  "correlation_id",
  "agent_id",
  "tool_id",
  "created_from",
  "created_to"
] as const;
type FilterKey = (typeof filterKeys)[number];
type FilterState = Record<FilterKey, string>;

export function ToolDecisionsPage() {
  const [filters, setFilters] = useState<FilterState>(() => readFiltersFromUrl());
  const [draftFilters, setDraftFilters] = useState<FilterState>(() => readFiltersFromUrl());
  const [offset, setOffset] = useState(() => readOffsetFromUrl());
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const actionsQuery = useToolRuntimeActions({ limit: pageSize, offset, ...cleanFilters(filters) });
  const detailQuery = useToolRuntimeActionDetail(selectedActionId);
  const actions = actionsQuery.data ?? [];

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleaned = cleanFilters(draftFilters);
    setFilters({ ...emptyFilters(), ...cleaned });
    setOffset(0);
    writeUrl(cleaned, 0);
  }

  function resetFilters() {
    const empty = emptyFilters();
    setDraftFilters(empty);
    setFilters(empty);
    setOffset(0);
    writeUrl({}, 0);
  }

  function updateDraft(key: FilterKey, value: string) {
    setDraftFilters((current) => ({ ...current, [key]: value }));
  }

  function goToOffset(nextOffset: number) {
    setOffset(nextOffset);
    writeUrl(cleanFilters(filters), nextOffset);
  }

  return (
    <>
      <PageHeader
        title="Tool Gateway Decisions"
        description="Runtime actions, policy outcomes, upstream metadata, and safe response summaries."
      />
      <div className="space-y-4 p-6">
        <section className="rounded-md border bg-card" data-tool-runtime-feed>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            <div>
              <h2 className="text-base font-semibold">Decision Feed</h2>
              <p className="text-sm text-muted-foreground">
                Allowed, denied, failed, and redacted calls across the active environment.
              </p>
            </div>
            <Badge tone="muted">{actions.length} rows</Badge>
          </div>
          <ToolRuntimeFilters
            filters={draftFilters}
            onApply={applyFilters}
            onReset={resetFilters}
            onUpdate={updateDraft}
          />
          {actionsQuery.isLoading ? (
            <LoadingState />
          ) : actionsQuery.isError ? (
            <ErrorState
              message={
                actionsQuery.error instanceof Error
                  ? actionsQuery.error.message
                  : "Unable to load tool decisions."
              }
              onRetry={() => void actionsQuery.refetch()}
            />
          ) : actions.length === 0 ? (
            <div className="p-4">
              <EmptyState
                title="No tool decisions"
                description="Gateway calls will appear after agents invoke registered tools."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table data-tool-runtime-table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Decision</TableHead>
                    <TableHead>Request</TableHead>
                    <TableHead>Agent</TableHead>
                    <TableHead>Tool</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead>Upstream</TableHead>
                    <TableHead>Latency</TableHead>
                    <TableHead>Correlation</TableHead>
                    <TableHead>Detail</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {actions.map((action) => (
                    <TableRow data-testid="tool-runtime-action-row" key={action.id}>
                      <TableCell className="whitespace-nowrap">
                        {formatTimestamp(action.created_at)}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <StatusBadge status={decisionForAction(action)} />
                          <small className="text-muted-foreground">
                            {humanize(action.action_status)}
                          </small>
                        </div>
                      </TableCell>
                      <TableCell>
                        <strong>{action.request_id}</strong>
                        <small className="block text-muted-foreground">
                          {action.decision_id ?? "no decision"}
                        </small>
                      </TableCell>
                      <TableCell>{action.agent_id ?? "unknown"}</TableCell>
                      <TableCell>{action.tool_id ?? "unknown"}</TableCell>
                      <TableCell>
                        {humanize(action.reason_code ?? action.error_code ?? "n/a")}
                      </TableCell>
                      <TableCell>{action.upstream_status_code ?? "n/a"}</TableCell>
                      <TableCell>{formatLatency(action.latency_ms)}</TableCell>
                      <TableCell>{action.correlation_id ?? "none"}</TableCell>
                      <TableCell>
                        <Button
                          onClick={() => setSelectedActionId(action.id)}
                          type="button"
                          variant="outline"
                        >
                          Open
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          <Pagination
            canGoNext={actions.length >= pageSize}
            canGoPrevious={offset > 0}
            isFetching={actionsQuery.isFetching}
            offset={offset}
            onNext={() => goToOffset(offset + pageSize)}
            onPrevious={() => goToOffset(Math.max(0, offset - pageSize))}
          />
        </section>
        {selectedActionId ? (
          <ToolRuntimeDetailDrawer
            detail={detailQuery.data ?? null}
            error={detailQuery.error}
            isError={detailQuery.isError}
            isLoading={detailQuery.isLoading}
            onClose={() => setSelectedActionId(null)}
          />
        ) : null}
      </div>
    </>
  );
}

function ToolRuntimeFilters({
  filters,
  onApply,
  onReset,
  onUpdate
}: {
  filters: FilterState;
  onApply: (event: FormEvent<HTMLFormElement>) => void;
  onReset: () => void;
  onUpdate: (key: FilterKey, value: string) => void;
}) {
  return (
    <form
      className="grid gap-3 border-b px-4 py-3 md:grid-cols-[minmax(8rem,0.8fr)_repeat(6,minmax(8rem,1fr))_auto_auto]"
      onSubmit={onApply}
    >
      <SelectField
        label="Status"
        name="action_status"
        onChange={(value) => onUpdate("action_status", value)}
        options={[
          "",
          "completed",
          "denied",
          "upstream_failed",
          "response_blocked",
          "authentication_failed"
        ]}
        value={filters.action_status}
      />
      <Field
        label="Decision ID"
        name="decision_id"
        onChange={(value) => onUpdate("decision_id", value)}
        value={filters.decision_id}
      />
      <Field
        label="Correlation"
        name="correlation_id"
        onChange={(value) => onUpdate("correlation_id", value)}
        value={filters.correlation_id}
      />
      <Field
        label="Agent ID"
        name="agent_id"
        onChange={(value) => onUpdate("agent_id", value)}
        value={filters.agent_id}
      />
      <Field
        label="Tool ID"
        name="tool_id"
        onChange={(value) => onUpdate("tool_id", value)}
        value={filters.tool_id}
      />
      <Field
        label="Created From"
        name="created_from"
        onChange={(value) => onUpdate("created_from", value)}
        value={filters.created_from}
      />
      <Field
        label="Created To"
        name="created_to"
        onChange={(value) => onUpdate("created_to", value)}
        value={filters.created_to}
      />
      <Button className="self-end" type="submit" variant="outline">
        Apply filters
      </Button>
      <Button className="self-end" onClick={onReset} type="button" variant="ghost">
        Reset
      </Button>
    </form>
  );
}

function Field({
  label,
  name,
  onChange,
  value
}: {
  label: string;
  name: FilterKey;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={`tool-runtime-${name}`}>{label}</Label>
      <Input
        id={`tool-runtime-${name}`}
        name={name}
        onChange={(event) => onChange(event.currentTarget.value)}
        value={value}
      />
    </div>
  );
}

function SelectField({
  label,
  name,
  onChange,
  options,
  value
}: {
  label: string;
  name: FilterKey;
  onChange: (value: string) => void;
  options: string[];
  value: string;
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={`tool-runtime-${name}`}>{label}</Label>
      <select
        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring"
        id={`tool-runtime-${name}`}
        name={name}
        onChange={(event) => onChange(event.currentTarget.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option ? humanize(option) : "All"}
          </option>
        ))}
      </select>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-3 p-4" data-testid="tool-runtime-loading">
      <div className="text-sm font-medium">Loading decisions</div>
      <div className="grid gap-2">
        {Array.from({ length: 4 }, (_, index) => (
          <div className="h-10 rounded-md bg-muted" key={index} />
        ))}
      </div>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="space-y-3 p-4" role="alert">
      <div>
        <strong>Unable to load tool decisions</strong>
        <p className="mt-1 text-sm text-muted-foreground">{message}</p>
      </div>
      <Button onClick={onRetry} type="button" variant="outline">
        <RefreshCw className="h-4 w-4" />
        Retry
      </Button>
    </div>
  );
}

function Pagination({
  canGoNext,
  canGoPrevious,
  isFetching,
  offset,
  onNext,
  onPrevious
}: {
  canGoNext: boolean;
  canGoPrevious: boolean;
  isFetching: boolean;
  offset: number;
  onNext: () => void;
  onPrevious: () => void;
}) {
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3"
      data-testid="tool-runtime-pagination"
    >
      <span className="text-sm text-muted-foreground">Offset {offset}</span>
      <div className="flex gap-2">
        <Button
          disabled={!canGoPrevious || isFetching}
          onClick={onPrevious}
          type="button"
          variant="outline"
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>
        <Button
          disabled={!canGoNext || isFetching}
          onClick={onNext}
          type="button"
          variant="outline"
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function ToolRuntimeDetailDrawer({
  detail,
  error,
  isError,
  isLoading,
  onClose
}: {
  detail: ToolRuntimeActionDetail | null;
  error: unknown;
  isError: boolean;
  isLoading: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <DialogContent
        className="left-auto right-0 top-0 ml-auto flex h-dvh w-full max-w-3xl translate-x-0 translate-y-0 flex-col rounded-none border-y-0 border-l border-r-0 bg-background p-0 shadow-xl"
        showCloseButton={false}
      >
        <div className="flex items-start justify-between gap-4 border-b px-5 py-4">
          <div>
            <DialogTitle className="text-lg font-semibold">Runtime Action Detail</DialogTitle>
            <DialogDescription className="text-sm text-muted-foreground">
              {detail?.request_id ?? "Loading action"}
            </DialogDescription>
          </div>
          <Button aria-label="Close" onClick={onClose} type="button" variant="ghost">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          {isLoading ? (
            <div className="space-y-2">
              <div className="h-5 w-40 rounded-md bg-muted" />
              <div className="h-24 rounded-md bg-muted" />
            </div>
          ) : isError ? (
            <div className="rounded-md border border-destructive/30 p-4 text-sm">
              {error instanceof Error ? error.message : "Unable to load runtime action."}
            </div>
          ) : detail ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={decisionForAction(detail)} />
                <StatusBadge status={detail.action_status} />
                {detail.redaction_applied || summaryHasRedaction(detail.response_summary) ? (
                  <Badge tone="warning">Redacted</Badge>
                ) : null}
                {isResponseHidden(detail.response_summary) ? (
                  <Badge tone="muted">Hidden response</Badge>
                ) : null}
              </div>
              <MetadataGrid detail={detail} />
              <SummaryBlock title="Payload Summary" value={detail.payload_summary} />
              <SummaryBlock title="Response Summary" value={detail.response_summary} />
              <Timeline events={detail.events} />
            </>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function MetadataGrid({ detail }: { detail: ToolRuntimeActionDetail }) {
  const fields = [
    ["Reason", humanize(detail.reason_code ?? detail.error_code ?? "n/a")],
    ["Decision ID", detail.decision_id ?? "n/a"],
    ["Permission", detail.permission_id ?? "n/a"],
    ["Credential", detail.credential_id ?? "n/a"],
    ["Correlation", detail.correlation_id ?? "none"],
    ["Upstream", detail.upstream_status_code ?? "n/a"],
    ["Latency", formatLatency(detail.latency_ms)],
    ["Created", formatTimestamp(detail.created_at)]
  ];

  return (
    <section className="grid gap-3 md:grid-cols-2">
      <div className="rounded-md border p-3">
        <div className="text-xs font-medium text-muted-foreground">Agent</div>
        {detail.agent_id ? (
          <a
            className="text-sm font-medium text-primary underline-offset-2 hover:underline"
            href={`/agents?agent_id=${encodeURIComponent(detail.agent_id)}`}
          >
            {detail.agent_id}
          </a>
        ) : (
          <div className="text-sm">unknown</div>
        )}
      </div>
      <div className="rounded-md border p-3">
        <div className="text-xs font-medium text-muted-foreground">Tool</div>
        {detail.tool_id ? (
          <a
            className="text-sm font-medium text-primary underline-offset-2 hover:underline"
            href={`/tool-gateway/decisions?tool_id=${encodeURIComponent(detail.tool_id)}`}
          >
            {detail.tool_id}
          </a>
        ) : (
          <div className="text-sm">unknown</div>
        )}
      </div>
      {fields.map(([label, value]) => (
        <div className="rounded-md border p-3" key={label}>
          <div className="text-xs font-medium text-muted-foreground">{label}</div>
          <div className="break-all text-sm">{String(value)}</div>
        </div>
      ))}
    </section>
  );
}

function SummaryBlock({
  title,
  value
}: {
  title: string;
  value: Record<string, unknown> | null | undefined;
}) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {value ? (
        <pre className="max-h-64 overflow-auto rounded-md border bg-muted p-3 text-xs">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : (
        <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
          No summary
        </div>
      )}
    </section>
  );
}

function Timeline({ events }: { events: ToolRuntimeActionDetail["events"] }) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold">Event Timeline</h3>
      {events.length === 0 ? (
        <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
          No events
        </div>
      ) : (
        <ol className="space-y-2">
          {events.map((event) => (
            <li className="rounded-md border p-3" key={event.id}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <strong className="text-sm">{event.event_type}</strong>
                <span className="text-xs text-muted-foreground">
                  {formatTimestamp(event.created_at)}
                </span>
              </div>
              <pre className="mt-2 overflow-auto rounded-md bg-muted p-2 text-xs">
                {JSON.stringify(event.event_summary, null, 2)}
              </pre>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function decisionForAction(action: ToolRuntimeAction) {
  if (["allowed", "forwarded", "completed"].includes(action.action_status)) {
    return "allow";
  }
  if (
    ["authentication_failed", "denied", "response_blocked", "upstream_failed"].includes(
      action.action_status
    )
  ) {
    return "deny";
  }
  return action.action_status;
}

function humanize(value: string) {
  return value.replaceAll("_", " ");
}

function formatLatency(value?: number | null) {
  return value === null || value === undefined ? "n/a" : `${value}ms`;
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("en-US", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short"
  });
}

function summaryHasRedaction(value: Record<string, unknown> | null | undefined): boolean {
  return value ? JSON.stringify(value).includes("[redacted]") : false;
}

function isResponseHidden(value: Record<string, unknown> | null | undefined): boolean {
  return value ? value.exposed_to_agent === false : false;
}

function emptyFilters(): FilterState {
  return {
    action_status: "",
    decision_id: "",
    correlation_id: "",
    agent_id: "",
    tool_id: "",
    created_from: "",
    created_to: ""
  };
}

function readFiltersFromUrl(): FilterState {
  if (typeof window === "undefined") {
    return emptyFilters();
  }
  const params = new URLSearchParams(window.location.search);
  return {
    ...emptyFilters(),
    ...Object.fromEntries(filterKeys.map((key) => [key, params.get(key) ?? ""]))
  };
}

function readOffsetFromUrl() {
  if (typeof window === "undefined") {
    return 0;
  }
  const parsed = Number.parseInt(
    new URLSearchParams(window.location.search).get("offset") ?? "0",
    10
  );
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function cleanFilters(filters: Partial<FilterState>) {
  return Object.fromEntries(
    filterKeys
      .map((key) => [key, filters[key]?.trim() ?? ""] as const)
      .filter(([, value]) => value.length > 0)
  );
}

function writeUrl(filters: Partial<FilterState>, offset: number) {
  if (typeof window === "undefined") {
    return;
  }
  const url = new URL(window.location.href);
  for (const key of filterKeys) {
    url.searchParams.delete(key);
  }
  url.searchParams.delete("offset");
  for (const [key, value] of Object.entries(filters)) {
    if (value) {
      url.searchParams.set(key, value);
    }
  }
  if (offset > 0) {
    url.searchParams.set("offset", String(offset));
  }
  window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}`);
}
