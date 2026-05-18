import { describe, expect, it } from "vitest";

import { datetimeLocalToIso } from "./dates";

describe("datetimeLocalToIso", () => {
  it("converts datetime-local values using the browser local timezone", () => {
    const input = "2026-05-02T09:30";
    const expected = new Date(input).toISOString();

    expect(datetimeLocalToIso(input)).toBe(expected);
  });

  it("preserves explicit timezone instants as canonical ISO strings", () => {
    expect(datetimeLocalToIso("2026-05-02T09:30:00+02:00")).toBe("2026-05-02T07:30:00.000Z");
  });

  it("omits empty or invalid values", () => {
    expect(datetimeLocalToIso("")).toBeUndefined();
    expect(datetimeLocalToIso("not-a-date")).toBeUndefined();
  });
});
