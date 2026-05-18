import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { setApiTenantContext } from "../api/client";

Object.defineProperty(window, "scrollTo", {
  value: vi.fn(),
  writable: true
});

afterEach(() => {
  cleanup();
  setApiTenantContext({ organizationId: null, environmentId: null });
  vi.clearAllMocks();
});
