export interface JsonObjectFieldOptions {
  emptyFallback?: Record<string, unknown>;
}

export function parseJsonObjectField(
  value: unknown,
  fieldName: string,
  options: JsonObjectFieldOptions = {}
) {
  const raw = String(value ?? "").trim();

  if (!raw) {
    return options.emptyFallback ?? {};
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error(`${fieldName} must be valid JSON.`);
  }

  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error(`${fieldName} must be a JSON object.`);
  }

  return parsed as Record<string, unknown>;
}
