import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TenantSelection } from "../../app/tenantContext";
import type { Environment } from "../../api/types";
import { renderWithQueryClient } from "../../test/test-utils";
import { EnvironmentSelector } from "./EnvironmentSelector";
import { NotificationCenter } from "./NotificationCenter";

const environments: Environment[] = [
  { id: "env_default", name: "Development", organization_id: "org_default" },
  { id: "env_prod", name: "Production", organization_id: "org_default" }
];

function tenantSelection(overrides: Partial<TenantSelection> = {}): TenantSelection {
  return {
    environments,
    error: null,
    isError: false,
    isLoading: false,
    isReady: true,
    organizations: [{ id: "org_default", name: "Ophanix Demo" }],
    selectedEnvironment: environments[0],
    selectedOrganization: { id: "org_default", name: "Ophanix Demo" },
    setSelectedEnvironmentId: vi.fn(),
    tenantContext: { organizationId: "org_default", environmentId: "env_default" },
    ...overrides
  };
}

describe("EnvironmentSelector", () => {
  it("uses a custom listbox instead of a native select", () => {
    const tenant = tenantSelection();
    render(<EnvironmentSelector tenant={tenant} />);

    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Environment Development/ }));

    expect(screen.getByRole("listbox")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: "Production" }));

    expect(tenant.setSelectedEnvironmentId).toHaveBeenCalledWith("env_prod");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes when another header popover opens or outside is clicked", async () => {
    stubHealthySystemFetch();
    renderWithQueryClient(
      <>
        <button type="button">Outside</button>
        <EnvironmentSelector tenant={tenantSelection()} />
        <NotificationCenter />
      </>
    );

    fireEvent.click(screen.getByRole("button", { name: /Environment Development/ }));
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));

    await waitFor(() => expect(screen.queryByRole("listbox")).not.toBeInTheDocument());
    expect(screen.getByRole("dialog")).toHaveTextContent("Notifications");

    fireEvent.pointerDown(screen.getByRole("button", { name: "Outside" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
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
