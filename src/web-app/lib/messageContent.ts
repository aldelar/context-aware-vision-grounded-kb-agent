export function coerceMessageContent(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }

  if (Array.isArray(value)) {
    const parts = value
      .map((entry) => coerceMessageContent(entry))
      .filter((entry): entry is string => entry !== null && entry !== "");
    return parts.length > 0 ? parts.join("") : null;
  }

  if (typeof value !== "object") {
    return null;
  }

  const record = value as Record<string, unknown>;
  for (const key of ["text", "value", "content", "message", "summary", "title"]) {
    const coerced = coerceMessageContent(record[key]);
    if (coerced !== null) {
      return coerced;
    }
  }

  try {
    return JSON.stringify(value);
  } catch {
    return null;
  }
}