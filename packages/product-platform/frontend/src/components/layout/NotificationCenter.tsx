import { Bell, X } from "lucide-react";
import { useId, useMemo, useRef, useState } from "react";

import { useSystemDependencies, useVersionInfo } from "../../api/system";
import type { SystemDependency } from "../../api/types";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { announceHeaderPopoverOpen, useHeaderPopoverDismiss } from "./headerPopover";

type NotificationType = "critical" | "warning" | "info";
const dismissedNotificationsStorageKey = "ophanix.dismissedNotifications";

interface HeaderNotification {
  id: string;
  fingerprint: string;
  href: string;
  type: NotificationType;
  title: string;
  message: string;
}

export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const [dismissedNotifications, setDismissedNotifications] = useState(() =>
    readDismissedNotifications()
  );
  const rootRef = useRef<HTMLDivElement>(null);
  const popoverId = useId();
  const dependencies = useSystemDependencies();
  const version = useVersionInfo();
  const allNotifications = useMemo(
    () => buildSystemNotifications(dependencies.data ?? [], dependencies.isError || version.isError),
    [dependencies.data, dependencies.isError, version.isError]
  );
  const notifications = useMemo(
    () =>
      allNotifications.filter(
        (notification) => !dismissedNotifications.includes(notification.fingerprint)
      ),
    [allNotifications, dismissedNotifications]
  );
  const notificationCount = notifications.length;
  const buttonLabel =
    notificationCount > 0
      ? `Notifications, ${notificationCount} notification${notificationCount === 1 ? "" : "s"}`
      : "Notifications";

  useHeaderPopoverDismiss({
    id: popoverId,
    onOpenChange: setOpen,
    open,
    rootRef
  });

  function toggleOpen() {
    setOpen((current) => {
      const next = !current;
      if (next) {
        announceHeaderPopoverOpen(popoverId);
      }
      return next;
    });
  }

  function dismissNotification(notification: HeaderNotification) {
    setDismissedNotifications((current) => {
      if (current.includes(notification.fingerprint)) {
        return current;
      }
      const next = [...current, notification.fingerprint];
      writeDismissedNotifications(next);
      return next;
    });
  }

  return (
    <div className="relative" ref={rootRef}>
      <Button
        aria-controls={open ? popoverId : undefined}
        aria-expanded={open}
        aria-label={buttonLabel}
        className="relative h-9 w-9 p-0"
        onClick={toggleOpen}
        type="button"
        variant="outline"
      >
        <Bell className="h-4 w-4" />
        {notificationCount > 0 ? (
          <span
            aria-hidden="true"
            className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold leading-none text-destructive-foreground ring-2 ring-background"
          >
            {notificationCount > 9 ? "9+" : notificationCount}
          </span>
        ) : null}
      </Button>
      {open ? (
        <div
          className="absolute right-0 z-30 mt-2 w-72 rounded-lg border border-border/80 bg-card p-4 text-sm shadow-[var(--shadow-popover)]"
          id={popoverId}
          role="dialog"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="font-display font-semibold">Notifications</div>
          </div>
          {notificationCount > 0 ? (
            <ul className="mt-3 space-y-3">
              {notifications.map((notification) => (
                <li className="flex items-start gap-2 rounded-md border border-border/80 p-2" key={notification.id}>
                  <a
                    className="min-w-0 flex-1 rounded-sm p-1 hover:bg-accent hover:text-accent-foreground focus-visible:bg-accent focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/20"
                    href={notification.href}
                    onClick={() => setOpen(false)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-medium">{notification.title}</div>
                      <Badge tone={notificationTone(notification.type)}>{notification.type}</Badge>
                    </div>
                    <p className="mt-1 text-muted-foreground">{notification.message}</p>
                  </a>
                  <Button
                    aria-label={`Dismiss notification: ${notification.title}`}
                    className="h-7 w-7 shrink-0 p-0"
                    onClick={() => dismissNotification(notification)}
                    type="button"
                    variant="ghost"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-muted-foreground">No notifications</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function buildSystemNotifications(
  dependencies: SystemDependency[],
  statusLoadFailed: boolean
): HeaderNotification[] {
  if (statusLoadFailed) {
    return [
      {
        id: "system-status-unavailable",
        fingerprint: "system-status-unavailable",
        href: "/overview",
        type: "critical",
        title: "System status unavailable",
        message: "The app could not load system dependency status or API build metadata."
      }
    ];
  }

  return dependencies
    .filter((dependency) => dependency.status.toLowerCase() !== "healthy")
    .map((dependency) => {
      const status = dependency.status.toLowerCase();
      const type: NotificationType =
        status === "not_configured" || status === "unchecked"
          ? "info"
          : dependency.required
            ? "critical"
            : "warning";
      return {
        id: `dependency-${dependency.name}`,
        fingerprint: [
          "dependency",
          dependency.name,
          dependency.status,
          dependency.message ?? ""
        ].join(":"),
        href: notificationHref(dependency.name),
        type,
        title: `${formatDependencyName(dependency.name)} ${formatStatus(dependency.status)}`,
        message: dependency.message ?? "Dependency requires attention."
      };
    });
}

function notificationTone(type: NotificationType) {
  if (type === "critical") {
    return "danger";
  }
  if (type === "warning") {
    return "warning";
  }
  return "muted";
}

function formatDependencyName(name: string) {
  return name.replaceAll("_", " ");
}

function formatStatus(status: string) {
  return status.replaceAll("_", " ");
}

function notificationHref(dependencyName: string) {
  if (dependencyName === "model_provider") {
    return "/integrations";
  }
  if (dependencyName === "worker") {
    return "/workflows";
  }
  if (dependencyName === "event_store") {
    return "/observability";
  }
  if (dependencyName === "redis") {
    return "/settings";
  }
  return "/overview";
}

function readDismissedNotifications(storage?: Storage) {
  try {
    const resolvedStorage =
      storage ?? (typeof window === "undefined" ? undefined : window.localStorage);
    if (!resolvedStorage) {
      return [];
    }
    const raw = resolvedStorage.getItem(dismissedNotificationsStorageKey);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((value) => typeof value === "string") : [];
  } catch {
    return [];
  }
}

function writeDismissedNotifications(values: string[], storage: Storage = window.localStorage) {
  storage.setItem(dismissedNotificationsStorageKey, JSON.stringify(values));
}
