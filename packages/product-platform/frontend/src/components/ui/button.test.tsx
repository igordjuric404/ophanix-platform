import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("defaults native buttons to type=button", () => {
    render(<Button>Open menu</Button>);

    expect(screen.getByRole("button", { name: "Open menu" })).toHaveAttribute("type", "button");
  });

  it("preserves explicit submit type", () => {
    render(<Button type="submit">Save</Button>);

    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("type", "submit");
  });
});
