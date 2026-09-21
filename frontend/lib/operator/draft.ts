// A bundle as the operator console edits it: parsed config.json and flow files, changed field by field, and
// written back with each value in the shape it had (a prompt written as a list of lines stays a list).
// Unit-tested.

export type Json = Record<string, unknown>;

export type BundleDoc = {
  config: Json;
  /** flow name -> its file path and parsed content */
  flows: Record<string, { path: string; data: Json }>;
};

function obj(value: unknown): Json {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Json) : {};
}

export function parseBundle(files: Record<string, string>): BundleDoc {
  const config = obj(JSON.parse(files["config.json"] ?? "{}"));
  const flows: BundleDoc["flows"] = {};
  for (const [name, path] of Object.entries(obj(config.flows))) {
    const p = String(path);
    flows[name] = { path: p, data: files[p] ? obj(JSON.parse(files[p])) : {} };
  }
  return { config, flows };
}

export function serializeBundle(doc: BundleDoc): Record<string, string> {
  const files: Record<string, string> = { "config.json": JSON.stringify(doc.config, null, 2) + "\n" };
  for (const { path, data } of Object.values(doc.flows)) files[path] = JSON.stringify(data, null, 2) + "\n";
  return files;
}

/** A text value as the editor shows it: a list of lines joined. */
export function textOf(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join("\n");
  return value === undefined || value === null ? "" : String(value);
}

/** `text` written back in the shape `previous` had: a list of lines stays a list of lines. */
export function asShapeOf(previous: unknown, text: string): string | string[] {
  return Array.isArray(previous) ? text.split("\n") : text;
}

/** A copy of `doc` with the value at `path` replaced (path starts with "config" or a flow name). */
export function setIn(doc: BundleDoc, path: (string | number)[], value: unknown): BundleDoc {
  const [root, ...rest] = path;
  const update = (node: unknown, keys: (string | number)[]): unknown => {
    if (!keys.length) return value;
    const [k, ...more] = keys;
    const base = obj(node);
    return { ...base, [k]: update(base[k], more) };
  };
  if (root === "config") return { ...doc, config: update(doc.config, rest) as Json };
  const flow = doc.flows[String(root)];
  return { ...doc, flows: { ...doc.flows, [String(root)]: { ...flow, data: update(flow.data, rest) as Json } } };
}

export function getIn(doc: BundleDoc, path: (string | number)[]): unknown {
  const [root, ...rest] = path;
  let node: unknown = root === "config" ? doc.config : doc.flows[String(root)]?.data;
  for (const k of rest) node = obj(node)[k];
  return node;
}

/** The placeholders a text uses, e.g. ["fields"] for "Tell me {fields}." */
export function placeholders(text: string): string[] {
  return [...new Set([...text.matchAll(/(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})/g)].map((m) => m[1]))];
}

/**
 * The bundle with a new language: every text in it starts as the default language's, for the operator to
 * translate. Adding a language is a minor version.
 */
export function addLanguage(doc: BundleDoc, code: string, name: string): BundleDoc {
  const from = String(doc.config.default_language ?? "en");
  const copyFrom = (entries: unknown) =>
    Object.fromEntries(
      Object.entries(obj(entries)).map(([k, v]) => [k, { ...obj(v), [code]: obj(v)[from] ?? "" }]),
    );
  const config = {
    ...doc.config,
    languages: { ...obj(doc.config.languages), [code]: { name } },
    labels: copyFrom(doc.config.labels),
    billing_periods: copyFrom(doc.config.billing_periods),
  };
  const flows = Object.fromEntries(
    Object.entries(doc.flows).map(([n, f]) => [n, { ...f, data: { ...f.data, copy: copyFrom(f.data.copy) } }]),
  );
  return { config, flows };
}
