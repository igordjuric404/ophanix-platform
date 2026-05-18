import { describe, expect, it } from "vitest";

import { parseJsonObjectField } from "./forms";

describe("parseJsonObjectField", () => {
  it("returns the parsed object for valid JSON objects", () => {
    expect(parseJsonObjectField('{"enabled":true}', "config")).toEqual({ enabled: true });
  });

  it("returns the empty fallback only when the field is blank", () => {
    expect(parseJsonObjectField("", "config", { emptyFallback: { enabled: false } })).toEqual({
      enabled: false
    });
  });

  it("rejects invalid JSON and non-object JSON", () => {
    expect(() => parseJsonObjectField("{", "config")).toThrow("config must be valid JSON.");
    expect(() => parseJsonObjectField("[]", "config")).toThrow("config must be a JSON object.");
  });
});
