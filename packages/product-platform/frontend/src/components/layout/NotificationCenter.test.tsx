import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithQueryClient } from "../../test/test-utils";
import { buildSystemNotifications } from "./NotificationCenter";
import { NotificationCenter } from "./NotificationCenter";

describe("NotificationCenter", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("opens the empty notifications popover from the header button", async () => {
    stubHealthySystemFetch();
    renderWithQueryClient(
      <>
        <button type="button">Outside</button>
        <NotificationCenter />
      </>
    );

    const button = screen.getByRole("button", { name: "Notifications" });
    expect(screen.queryByText("No notifications")).not.toBeInTheDocument();

    fireEvent.click(button);

    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("dialog")).toHaveTextContent("Notifications");
    expect(screen.getByText("No notifications")).toBeInTheDocument();

    fireEvent.click(button);

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    fireEvent.click(button);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(button).toHaveFocus();

    fireEvent.click(button);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.pointerDown(screen.getByRole("button", { name: "Outside" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows a count bubble on the bell when notifications exist", async () => {
    vi.stubGlobal("fetch", async (url: string) => {
      if (url.endsWith("/system/dependencies")) {
        return json([
          {
            name: "model_provider",
            required: false,
            status: "not_configured",
            message: "No active model provider credential is configured."
          },
          {
            name: "worker",
            required: true,
            status: "unhealthy",
            message: "Worker is down."
          }
        ]);
      }
      if (url.endsWith("/version")) {
        return json({ build_sha: "test-sha", environment: "test" });
      }
      return json({});
    });

    renderWithQueryClient(<NotificationCenter />);

    const button = await screen.findByRole("button", {
      name: "Notifications, 2 notifications"
    });
    expect(within(button).getByText("2")).toBeInTheDocument();

    fireEvent.click(button);

    expect(screen.getByRole("dialog")).toHaveTextContent("model provider not configured");
    expect(screen.getByRole("dialog")).toHaveTextContent("worker unhealthy");
    expect(screen.getByRole("link", { name: /model provider not configured/i })).toHaveAttribute(
      "href",
      "/integrations"
    );
    expect(screen.getByRole("link", { name: /worker unhealthy/i })).toHaveAttribute(
      "href",
      "/workflows"
    );
  });

  it("dismisses individual notifications and reduces the bell count", async () => {
    vi.stubGlobal("fetch", async (url: string) => {
      if (url.endsWith("/system/dependencies")) {
        return json([
          {
            name: "model_provider",
            required: false,
            status: "not_configured",
            message: "No active model provider credential is configured."
          },
          {
            name: "worker",
            required: true,
            status: "unhealthy",
            message: "Worker is down."
          }
        ]);
      }
      if (url.endsWith("/version")) {
        return json({ build_sha: "test-sha", environment: "test" });
      }
      return json({});
    });

    renderWithQueryClient(<NotificationCenter />);

    const button = await screen.findByRole("button", {
      name: "Notifications, 2 notifications"
    });
    fireEvent.click(button);

    fireEvent.click(
      screen.getByRole("button", { name: "Dismiss notification: worker unhealthy" })
    );

    expect(screen.queryByText("worker unhealthy")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Notifications, 1 notification" })
    ).toBeInTheDocument();
    expect(within(screen.getByRole("button", { name: /Notifications, 1/ })).getByText("1")).toBeInTheDocument();
    expect(window.localStorage.getItem("ophanix.dismissedNotifications")).toBeNull();
    expect(
      Object.keys(window.localStorage).some((key) =>
        key.startsWith("ophanix.dismissedNotifications.anonymous.")
      )
    ).toBe(true);
  });

  it("builds different notification types from dependency states", () => {
    expect(
      buildSystemNotifications(
        [
          {
            name: "database",
            required: true,
            status: "unhealthy",
            message: "database down"
          },
          {
            name: "redis",
            required: false,
            status: "unhealthy",
            message: "redis down"
          },
          {
            name: "model_provider",
            required: false,
            status: "not_configured",
            message: "missing credential"
          }
        ],
        false
      ).map((notification) => notification.type)
    ).toEqual(["critical", "warning", "info"]);
  });
});

function stubHealthySystemFetch() {
  vi.stubGlobal("fetch", async (url: string) => {
    if (url.endsWith("/system/dependencies")) {
      return json([{ name: "database", required: true, status: "healthy" }]);
    }
    if (url.endsWith("/version")) {
      return json({ build_sha: "test-sha", environment: "test" });
    }
    return json({});
  });
}

function json(body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      headers: { "Content-Type": "application/json" },
      status: 200
    })
  );
}
