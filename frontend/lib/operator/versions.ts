// Pure helpers for the operator console (unit-tested): versions, diffs, JSON display.
import type { Bump } from "./types";

export function semver(v: string): [number, number, number] | null {
  const m = /^(\d+)\.(\d+)\.(\d+)$/.exec(v);
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}

export function compareVersions(a: string, b: string): number {
  const x = semver(a) ?? [0, 0, 0];
  const y = semver(b) ?? [0, 0, 0];
  return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
}

/**
 * The version a publish of a draft at `current` gets, as the backend picks it: one `bump` above the latest
 * published version of the same major, or `current` when that major has nothing published.
 */
export function nextVersion(published: string[], current: string, bump: Bump): string {
  const major = semver(current)?.[0];
  const sameMajor = published.filter((v) => semver(v)?.[0] === major).sort(compareVersions);
  const latest = sameMajor.at(-1);
  if (!latest) return current;
  const [ma, mi, pa] = semver(latest)!;
  return bump === "patch" ? `${ma}.${mi}.${pa + 1}` : `${ma}.${mi + 1}.0`;
}

/** JSON re-indented the same way everywhere, so a diff shows content changes only. Non-JSON is returned as is. */
export function prettyJson(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

/** The JSON syntax error in `text`, or null. */
export function jsonError(text: string): string | null {
  try {
    JSON.parse(text);
    return null;
  } catch (err) {
    return err instanceof Error ? err.message : String(err);
  }
}

export type DiffLine = { kind: "same" | "add" | "del"; text: string; a?: number; b?: number };
export type DiffRow = DiffLine | { kind: "gap"; count: number };

/** A line diff (longest common subsequence). Line numbers are 1-based on each side. */
export function lineDiff(a: string, b: string): DiffLine[] {
  const x = a.split("\n");
  const y = b.split("\n");
  const n = x.length;
  const m = y.length;
  const lcs: Uint32Array[] = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] = x[i] === y[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (x[i] === y[j]) {
      out.push({ kind: "same", text: x[i], a: i + 1, b: j + 1 });
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      out.push({ kind: "del", text: x[i], a: i + 1 });
      i++;
    } else {
      out.push({ kind: "add", text: y[j], b: j + 1 });
      j++;
    }
  }
  for (; i < n; i++) out.push({ kind: "del", text: x[i], a: i + 1 });
  for (; j < m; j++) out.push({ kind: "add", text: y[j], b: j + 1 });
  return out;
}

/** The changed lines with `context` unchanged lines around each change; longer unchanged runs fold into a gap. */
export function withContext(lines: DiffLine[], context = 3): DiffRow[] {
  const keep = lines.map(() => false);
  lines.forEach((line, idx) => {
    if (line.kind === "same") return;
    for (let k = Math.max(0, idx - context); k <= Math.min(lines.length - 1, idx + context); k++) keep[k] = true;
  });
  const rows: DiffRow[] = [];
  let skipped = 0;
  lines.forEach((line, idx) => {
    if (keep[idx]) {
      if (skipped) rows.push({ kind: "gap", count: skipped });
      skipped = 0;
      rows.push(line);
    } else {
      skipped++;
    }
  });
  if (skipped) rows.push({ kind: "gap", count: skipped });
  return rows;
}

export function changeCount(lines: DiffLine[]): { added: number; removed: number } {
  return {
    added: lines.filter((l) => l.kind === "add").length,
    removed: lines.filter((l) => l.kind === "del").length,
  };
}

/** "3 minutes ago"-style age of an ISO time, relative to `now`. */
export function timeAgo(iso: string | undefined, now: number): string {
  if (!iso) return "";
  const seconds = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (Number.isNaN(seconds)) return "";
  const units: [number, string][] = [
    [86400, "day"],
    [3600, "hour"],
    [60, "minute"],
  ];
  for (const [size, name] of units) {
    if (seconds >= size) {
      const n = Math.floor(seconds / size);
      return `${n} ${name}${n === 1 ? "" : "s"} ago`;
    }
  }
  return "just now";
}
