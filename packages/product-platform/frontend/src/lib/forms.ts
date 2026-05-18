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

export interface NumericFieldOptions {
  emptyFallback?: number;
  integer?: boolean;
}

export function parseRequiredNumberField(
  value: unknown,
  fieldName: string,
  options: NumericFieldOptions = {}
) {
  const raw = String(value ?? "").trim();
  if (!raw) {
    if (options.emptyFallback !== undefined) {
      return options.emptyFallback;
    }
    throw new Error(`${fieldName} is required.`);
  }

  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || (options.integer && !Number.isInteger(parsed))) {
    throw new Error(`${fieldName} must be a valid ${options.integer ? "integer" : "number"}.`);
  }
  return parsed;
}

export function parseOptionalNumberField(
  value: unknown,
  fieldName: string,
  options: Omit<NumericFieldOptions, "emptyFallback"> = {}
) {
  const raw = String(value ?? "").trim();
  if (!raw) {
    return null;
  }
  return parseRequiredNumberField(raw, fieldName, options);
}

export function parseIntegerListField(value: unknown, fieldName: string) {
  const raw = String(value ?? "").trim();
  if (!raw) {
    throw new Error(`${fieldName} is required.`);
  }

  return raw.split(",").map((part) => {
    const item = part.trim();
    if (!item) {
      throw new Error(`${fieldName} must be a comma-separated list of valid integers.`);
    }
    try {
      return parseRequiredNumberField(item, fieldName, { integer: true });
    } catch {
      throw new Error(`${fieldName} must be a comma-separated list of valid integers.`);
    }
  });
}
