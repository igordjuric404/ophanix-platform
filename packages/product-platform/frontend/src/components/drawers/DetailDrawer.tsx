import { ArrowLeft, X } from "lucide-react";

import type { AuditEvent } from "../../api/audit";
import type { DetailDrawerController, DetailDrawerState } from "../../app/drawerContext";
import { cn } from "../../lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

const tabs: Array<{ id: DetailDrawerState["activeTab"]; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "evidence", label: "Evidence" },
  { id: "related", label: "Related" }
];

export function DetailDrawer({ controller }: { controller: DetailDrawerController }) {
  const { drawer } = controller;
  if (!drawer.open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/30" data-drawer-open>
      <aside
        aria-describedby="detail-drawer-description"
        aria-labelledby="detail-drawer-title"
        aria-modal="true"
        className="fixed right-0 top-0 flex h-full w-[min(100vw,46rem)] flex-col border-l bg-background shadow-xl"
        role="dialog"
      >
        <header className="border-b p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase text-muted-foreground">
                {drawer.kind ?? "detail"}
              </p>
              <h2 className="mt-1 text-xl font-semibold" id="detail-drawer-title">
                {drawer.title}
              </h2>
              <p className="mt-1 text-sm text-muted-foreground" id="detail-drawer-description">
                {drawer.subtitle}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {drawer.backStack.length > 0 ? (
                <Button
                  aria-label="Back"
                  className="h-9 w-9 p-0"
                  onClick={controller.backDrawer}
                  type="button"
                  variant="outline"
                >
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              ) : null}
              <Button
                aria-label="Close detail drawer"
                className="h-9 w-9 p-0"
                onClick={controller.closeDrawer}
                type="button"
                variant="ghost"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Badge tone={drawer.status.toLowerCase().includes("deny") ? "danger" : "muted"}>
              {drawer.status}
            </Badge>
            <a className="text-sm font-medium text-primary" href={`/observability?event_id=${drawer.resourceId ?? ""}`}>
              Open in Audit Explorer
            </a>
          </div>
          <nav aria-label="Detail tabs" className="mt-4 flex gap-1 rounded-md bg-muted p-1">
            {tabs.map((tab) => (
              <button
                className={cn(
                  "flex-1 rounded px-3 py-2 text-sm font-medium",
                  drawer.activeTab === tab.id
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground"
                )}
                key={tab.id}
                onClick={() => controller.setActiveTab(tab.id)}
                type="button"
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </header>
        <div className="flex-1 overflow-y-auto p-5">{renderDrawerBody(controller)}</div>
      </aside>
    </div>
  );
}

function renderDrawerBody(controller: DetailDrawerController) {
  const { drawer } = controller;
  if (drawer.state === "loading") {
    return <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">Loading detail</div>;
  }
  if (drawer.state === "error") {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-sm text-rose-800">
        {drawer.error ?? "Unable to load detail"}
      </div>
    );
  }
  if (!drawer.event) {
    return <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">No detail selected</div>;
  }
  if (drawer.activeTab === "evidence") {
    return <EvidenceTab drawer={drawer} />;
  }
  if (drawer.activeTab === "related") {
    return <RelatedTab controller={controller} />;
  }
  return <OverviewTab event={drawer.event} kind={drawer.kind} />;
}

function OverviewTab({ event, kind }: { event: AuditEvent; kind: DetailDrawerState["kind"] }) {
  const payload = event.payload_json ?? {};
  return (
    <div className="space-y-5">
      {kind === "policy-decision" ? (
        <DrawerSection title="Policy Decision">
          <MetadataGrid
            rows={[
              ["Policy", event.policy_id ?? event.resource_id],
              ["Decision", event.decision],
              ["Matched rule", stringValue(payload.matched_rule)],
              ["Reason", stringValue(payload.reason)]
            ]}
          />
        </DrawerSection>
      ) : null}
      {kind === "mcp-call" ? (
        <DrawerSection title="MCP Call">
          <MetadataGrid
            rows={[
              ["Server", event.resource_id],
              ["Tool", stringValue(payload.tool_name)],
              ["Decision", event.decision],
              [
                "Params classification",
                stringValue(payload.params_classification ?? payload.classification)
              ],
              ["Sanitizer action", stringValue(payload.sanitizer_action)]
            ]}
          />
        </DrawerSection>
      ) : null}
      {kind === "runtime-action" ? (
        <DrawerSection title="Runtime Action">
          <MetadataGrid
            rows={[
              ["Session", event.resource_id],
              ["Action", stringValue(payload.action)],
              ["Ring", stringValue(payload.ring)],
              ["Sandbox", stringValue(payload.sandbox_status ?? payload.sandbox)],
              ["Saga", stringValue(payload.saga_id)]
            ]}
          />
        </DrawerSection>
      ) : null}
      <DrawerSection title="Metadata">
        <MetadataGrid
          rows={[
            ["Event type", event.event_type],
            ["Source", event.source_component],
            ["Actor", [event.actor_type, event.actor_id].filter(Boolean).join(" / ")],
            ["Agent", event.agent_id],
            ["Resource", [event.resource_type, event.resource_id].filter(Boolean).join(" / ")],
            ["Decision", event.decision],
            ["Severity", event.severity],
            ["Correlation", event.correlation_id],
            ["Created", event.created_at]
          ]}
        />
      </DrawerSection>
    </div>
  );
}

function EvidenceTab({ drawer }: { drawer: DetailDrawerState }) {
  return (
    <div className="space-y-5">
      <DrawerSection title="Hash Verification">
        <p className="text-sm text-muted-foreground">{verificationText(drawer)}</p>
      </DrawerSection>
      <DrawerSection title="Raw Payload">
        <pre className="max-h-96 overflow-auto rounded-md bg-muted p-4 text-xs">
          {JSON.stringify(drawer.event?.payload_json ?? {}, null, 2)}
        </pre>
      </DrawerSection>
    </div>
  );
}

function RelatedTab({ controller }: { controller: DetailDrawerController }) {
  const related = controller.drawer.relatedEvents
    .filter((event) => event.id !== controller.drawer.event?.id)
    .sort((left, right) => String(left.created_at).localeCompare(String(right.created_at)));
  if (related.length === 0) {
    return <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">No related events</div>;
  }
  return (
    <ol className="space-y-3">
      {related.map((event) => (
        <li key={event.id}>
          <button
            className="w-full rounded-lg border bg-card p-4 text-left text-sm hover:bg-accent"
            onClick={() => void controller.openAuditEvent(event.id, { pushCurrent: true })}
            type="button"
          >
            <span className="font-medium">{event.event_type}</span>
            <span className="mt-1 block text-muted-foreground">{event.id}</span>
            <span className="mt-1 block text-xs text-muted-foreground">{event.created_at}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}

function DrawerSection({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <section className="rounded-lg border bg-card p-4">
      <h3 className="font-semibold">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function MetadataGrid({ rows }: { rows: Array<[string, string | null | undefined]> }) {
  return (
    <dl className="grid grid-cols-[9rem_1fr] gap-x-4 gap-y-2 text-sm">
      {rows.map(([label, value]) => (
        <div className="contents" key={label}>
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="font-medium">{value || "n/a"}</dd>
        </div>
      ))}
    </dl>
  );
}

function verificationText(drawer: DetailDrawerState) {
  if (!drawer.verification) {
    return "Hash verification has not run.";
  }
  if (drawer.verification.valid) {
    return `Valid hash chain, ${drawer.verification.checked_count ?? 0} event(s) checked.`;
  }
  return `Hash verification failed: ${drawer.verification.reason ?? "unknown"}.`;
}

function stringValue(value: unknown) {
  return typeof value === "string" || typeof value === "number" ? String(value) : undefined;
}

