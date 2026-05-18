import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from "react";

import {
  getAuditEvent,
  listAuditEvents,
  verifyAuditEvent,
  type AuditEvent,
  type AuditVerification
} from "../api/audit";
import { useTenantQueryScope } from "../api/queryScope";
import { DetailDrawer } from "../components/drawers/DetailDrawer";

export type DrawerKind =
  | "audit-event"
  | "policy-decision"
  | "agent-snapshot"
  | "trust-change"
  | "mcp-call"
  | "runtime-action"
  | "workflow-run"
  | "approval-request";

export type DrawerStateKind = "empty" | "loading" | "ready" | "error";

export interface DetailDrawerState {
  open: boolean;
  kind: DrawerKind | null;
  resourceId: string | null;
  title: string;
  subtitle: string;
  status: string;
  activeTab: "overview" | "evidence" | "related";
  state: DrawerStateKind;
  error: string | null;
  event: AuditEvent | null;
  verification: AuditVerification | null;
  relatedEvents: AuditEvent[];
  backStack: DetailDrawerState[];
}

export interface DetailDrawerController {
  drawer: DetailDrawerState;
  openAuditEvent: (eventId: string, options?: { pushCurrent?: boolean }) => Promise<void>;
  closeDrawer: () => void;
  backDrawer: () => void;
  setActiveTab: (tab: DetailDrawerState["activeTab"]) => void;
}

const emptyDrawer: DetailDrawerState = {
  open: false,
  kind: null,
  resourceId: null,
  title: "",
  subtitle: "",
  status: "",
  activeTab: "overview",
  state: "empty",
  error: null,
  event: null,
  verification: null,
  relatedEvents: [],
  backStack: []
};

const DetailDrawerContext = createContext<DetailDrawerController | null>(null);

export function DetailDrawerProvider({ children }: { children: ReactNode }) {
  const [drawer, setDrawer] = useState<DetailDrawerState>(emptyDrawer);
  const requestIdRef = useRef(0);
  const scope = useTenantQueryScope();

  const closeDrawer = useCallback(() => {
    requestIdRef.current += 1;
    setDrawer(emptyDrawer);
    clearDrawerDeepLink();
  }, []);

  const openAuditEvent = useCallback(
    async (eventId: string, options: { pushCurrent?: boolean } = {}) => {
      const requestId = requestIdRef.current + 1;
      requestIdRef.current = requestId;
      const tenantContext = scope.context;

      setDrawer((current) => {
        const backStack =
          options.pushCurrent && current.open
            ? [snapshotDrawer(current), ...current.backStack]
            : current.backStack;
        return {
          ...emptyDrawer,
          open: true,
          kind: "audit-event",
          resourceId: eventId,
          title: "Audit Event",
          subtitle: eventId,
          status: "Loading",
          state: "loading",
          backStack
        };
      });
      writeDrawerDeepLink("audit-event", eventId);

      try {
        const event = await getAuditEvent(eventId, tenantContext);
        const [verification, relatedEvents] = await Promise.all([
          verifyAuditEvent(eventId, tenantContext),
          event.correlation_id
            ? listAuditEvents({ correlation_id: event.correlation_id }, tenantContext)
            : Promise.resolve([])
        ]);
        setDrawer((current) => {
          if (requestIdRef.current !== requestId || current.resourceId !== eventId) {
            return current;
          }
          return {
            ...drawerStateForAuditEvent(event, verification, relatedEvents),
            backStack: current.backStack
          };
        });
      } catch (error) {
        setDrawer((current) => {
          if (requestIdRef.current !== requestId || current.resourceId !== eventId) {
            return current;
          }
          return {
            ...current,
            title: "Audit Event",
            status: "Error",
            state: "error",
            error: error instanceof Error ? error.message : "Unable to load audit event."
          };
        });
      }
    },
    [scope.context]
  );

  const backDrawer = useCallback(() => {
    setDrawer((current) => {
      const [previous, ...remaining] = current.backStack;
      if (!previous) {
        return current;
      }
      if (previous.resourceId) {
        writeDrawerDeepLink("audit-event", previous.resourceId);
      }
      return { ...previous, backStack: remaining };
    });
  }, []);

  const setActiveTab = useCallback((activeTab: DetailDrawerState["activeTab"]) => {
    setDrawer((current) => ({ ...current, activeTab }));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const kind = params.get("drawer");
    const eventId = params.get("id");
    if (kind === "audit-event" && eventId) {
      void openAuditEvent(eventId);
    }
  }, [openAuditEvent]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && drawer.open) {
        event.preventDefault();
        closeDrawer();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closeDrawer, drawer.open]);

  const value = useMemo(
    () => ({ drawer, openAuditEvent, closeDrawer, backDrawer, setActiveTab }),
    [backDrawer, closeDrawer, drawer, openAuditEvent, setActiveTab]
  );

  return (
    <DetailDrawerContext.Provider value={value}>
      {children}
      <DetailDrawer controller={value} />
    </DetailDrawerContext.Provider>
  );
}

export function useDetailDrawer() {
  const context = useContext(DetailDrawerContext);
  if (!context) {
    throw new Error("useDetailDrawer must be used within DetailDrawerProvider.");
  }
  return context;
}

function drawerStateForAuditEvent(
  event: AuditEvent,
  verification: AuditVerification,
  relatedEvents: AuditEvent[]
): DetailDrawerState {
  const kind = kindForAuditEvent(event);
  const hashStatus = verification.valid ? "Hash verified" : "Hash pending";
  return {
    ...emptyDrawer,
    open: true,
    kind,
    resourceId: event.id,
    title: titleForKind(kind),
    subtitle: event.policy_id ?? event.resource_id ?? event.id,
    status: event.decision ?? event.severity ?? hashStatus,
    state: "ready",
    event,
    verification,
    relatedEvents
  };
}

function kindForAuditEvent(event: AuditEvent): DrawerKind {
  if (event.event_type === "policy.decision") {
    return "policy-decision";
  }
  if (event.event_type === "mcp.call") {
    return "mcp-call";
  }
  if (event.event_type === "runtime.action") {
    return "runtime-action";
  }
  return "audit-event";
}

function titleForKind(kind: DrawerKind) {
  const titles: Record<DrawerKind, string> = {
    "audit-event": "Audit Event",
    "policy-decision": "Policy Decision",
    "agent-snapshot": "Agent Snapshot",
    "trust-change": "Trust Change",
    "mcp-call": "MCP Call",
    "runtime-action": "Runtime Action",
    "workflow-run": "Workflow Run",
    "approval-request": "Approval Request"
  };
  return titles[kind];
}

function snapshotDrawer(drawer: DetailDrawerState): DetailDrawerState {
  return { ...drawer, backStack: [] };
}

function writeDrawerDeepLink(kind: DrawerKind, resourceId: string) {
  const url = new URL(window.location.href);
  url.searchParams.set("drawer", kind);
  url.searchParams.set("id", resourceId);
  window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}`);
}

function clearDrawerDeepLink() {
  const url = new URL(window.location.href);
  url.searchParams.delete("drawer");
  url.searchParams.delete("id");
  window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}`);
}
