import { clip, MAX_TEXT, redact, redactDeep } from "./redact.mjs";

/** Convert one incoming value to its stored form, or throw a descriptive error. */
function toStored(label, spec, value) {
  const fail = (why) => {
    throw new Error(`${label}: ${why}`);
  };
  if (spec.type === "text") {
    if (typeof value !== "string") fail("must be a string");
    return redact(clip(value));
  }
  if (spec.type === "int") {
    if (!Number.isInteger(value)) fail("must be an integer");
    return value;
  }
  if (spec.type === "bool") {
    if (typeof value !== "boolean") fail("must be true or false");
    return value ? 1 : 0;
  }
  if (spec.type === "enum") {
    if (!spec.values.includes(value)) fail(`must be one of ${spec.values.join(", ")}`);
    return value;
  }
  if (spec.type === "json") {
    const stored = JSON.stringify(redactDeep(value));
    if (stored === undefined) fail("must be JSON-serializable");
    if (stored.length > MAX_TEXT) fail("is too large");
    return stored;
  }
  return fail(`has unsupported type ${spec.type}`);
}

/**
 * Validate `fields` against a table's column specs and return a
 * column → stored-value map. Unknown fields and missing required fields are errors.
 */
export function validateFields(table, columns, fields) {
  const out = {};
  for (const key of Object.keys(fields)) {
    if (key === "supersedes") continue;
    if (!(key in columns)) throw new Error(`${table}: unknown field "${key}"`);
  }
  for (const [col, spec] of Object.entries(columns)) {
    const value = fields[col];
    if (value === undefined || value === null) {
      if (!spec.optional) throw new Error(`${table}.${col}: required`);
      continue;
    }
    out[col] = toStored(`${table}.${col}`, spec, value);
  }
  if (fields.supersedes !== undefined && fields.supersedes !== null) {
    if (!Number.isInteger(fields.supersedes)) throw new Error(`${table}.supersedes: must be an integer`);
    out.supersedes = fields.supersedes;
  }
  return out;
}
