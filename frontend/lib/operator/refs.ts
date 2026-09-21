// Which parts of the agent loop a config entry touches (unit-tested). The backend's /api/operator/graph says
// which config refs each node reads (from the flow code); this maps a bundle's files onto those refs, and
// finds the refs two versions (or a draft and its base) differ in.

export type OutlineNode = { id: string; domain: string; kind: "code" | "llm" | "wait"; reads: string[] };
export type OutlineEdge = { source: string; target: string; kind: "route" | "input" | "resume" };
export type Outline = { entry: string; nodes: OutlineNode[]; edges: OutlineEdge[] };

/** A config entry, e.g. "copy:profiling.ask_more", "llm:assess_needs.instructions", "models:default". */
export type Ref = string;

type Json = Record<string, unknown>;

function parse(text: string | undefined): Json | null {
  if (!text) return null;
  try {
    const value = JSON.parse(text);
    return value && typeof value === "object" && !Array.isArray(value) ? (value as Json) : null;
  } catch {
    return null;
  }
}

function entries(value: unknown): [string, unknown][] {
  return value && typeof value === "object" && !Array.isArray(value) ? Object.entries(value as Json) : [];
}

/** Every config entry of a bundle, with its JSON text for comparing. Unparsable files contribute nothing. */
export function refsOf(files: Record<string, string>): Map<Ref, string> {
  const out = new Map<Ref, string>();
  const config = parse(files["config.json"]);
  if (!config) return out;
  const put = (ref: Ref, value: unknown) => out.set(ref, JSON.stringify(value));
  put("languages", config.languages);
  put("default_language", config.default_language);
  put("system_prompt", config.system_prompt);
  for (const [name, model] of entries(config.models)) put(`models:${name}`, model);
  for (const [field, label] of entries(config.labels)) put(`labels:${field}`, label);
  for (const [period, unit] of entries(config.billing_periods)) put(`billing_periods:${period}`, unit);
  for (const [flow, path] of entries(config.flows)) {
    const data = parse(files[String(path)]);
    if (!data) continue;
    for (const [key, text] of entries(data.copy)) put(`copy:${flow}.${key}`, text);
    for (const [node, parts] of entries(data.llm)) {
      for (const [part, value] of entries(parts)) put(`llm:${node}.${part}`, value);
    }
  }
  return out;
}

/** The refs of file `path` of a bundle, in file order. */
export function refsInFile(files: Record<string, string>, path: string): Ref[] {
  const config = parse(files["config.json"]);
  const all = [...refsOf(files).keys()];
  if (path === "config.json") return all.filter((r) => !r.startsWith("copy:") && !r.startsWith("llm:"));
  const flow = entries(config?.flows).find(([, p]) => p === path)?.[0];
  const data = parse(files[path]);
  if (!flow || !data) return [];
  const llmNodes = new Set(entries(data.llm).map(([node]) => node));
  return all.filter(
    (r) => r.startsWith(`copy:${flow}.`) || (r.startsWith("llm:") && llmNodes.has(r.slice(4).split(".")[0])),
  );
}

/** The refs whose value differs between two bundles (added, removed or changed). */
export function changedRefs(before: Record<string, string>, after: Record<string, string>): Ref[] {
  const a = refsOf(before);
  const b = refsOf(after);
  const refs = new Set([...a.keys(), ...b.keys()]);
  return [...refs].filter((r) => a.get(r) !== b.get(r)).sort();
}

/**
 * The nodes a config entry reaches. `nodeModels` is the bundle's node -> model profile (its summary), so a
 * model profile reaches the nodes that use it.
 */
export function nodesFor(ref: Ref, outline: Outline, nodeModels: Record<string, string> = {}): string[] {
  const reads = (want: (read: string) => boolean) =>
    outline.nodes.filter((n) => n.reads.some(want)).map((n) => n.id);
  const [kind, rest = ""] = ref.split(/:(.*)/s);
  switch (kind) {
    case "copy":
      return reads((r) => r === ref);
    case "llm": {
      const [node, part] = rest.split(".");
      return part === "model" ? [node] : reads((r) => r === ref);
    }
    case "models":
      return Object.entries(nodeModels)
        .filter(([, profile]) => profile === rest)
        .map(([node]) => node);
    case "labels":
      return reads((r) => r === "labels");
    case "billing_periods":
      return reads((r) => r === "billing_periods");
    case "system_prompt":
      return reads((r) => r === "system_prompt");
    case "languages":
    case "default_language":
      // Every node that says something or asks the LLM depends on the languages.
      return reads((r) => r.startsWith("copy:") || r === "system_prompt");
    default:
      return [];
  }
}

export function nodesForAll(refs: Ref[], outline: Outline, nodeModels: Record<string, string> = {}): Set<string> {
  return new Set(refs.flatMap((r) => nodesFor(r, outline, nodeModels)));
}

/** A short human label for a ref. */
export function refLabel(ref: Ref): string {
  const [kind, rest = ""] = ref.split(/:(.*)/s);
  switch (kind) {
    case "copy":
      return `copy · ${rest}`;
    case "llm":
      return `prompt · ${rest}`;
    case "models":
      return `model · ${rest}`;
    case "labels":
      return `label · ${rest}`;
    case "billing_periods":
      return `billing unit · ${rest}`;
    default:
      return ref.replace(/_/g, " ");
  }
}
