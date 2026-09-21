"use client";

import { useEffect, useMemo, useState } from "react";
import { changedRefs, refLabel } from "@/lib/operator/refs";
import type { VersionDetail, VersionItem } from "@/lib/operator/types";
import { changeCount, lineDiff, prettyJson, withContext } from "@/lib/operator/versions";
import { DiffView } from "./CodeView";
import type { HighlightRefs } from "./types";

type Props = {
  detail: VersionDetail;
  versions: VersionItem[];
  load: (version: string) => Promise<VersionDetail>;
  onChanges: HighlightRefs;
  onRefs: HighlightRefs;
  onClear: () => void;
};

function defaultBase(detail: VersionDetail, versions: VersionItem[]): string | null {
  if (detail.release.based_on) return detail.release.based_on;
  const names = versions.map((v) => v.version);
  const i = names.indexOf(detail.version);
  return names[i + 1] ?? null; // versions come newest first: the one before this
}

export function CompareTab({ detail, versions, load, onChanges, onRefs, onClear }: Props) {
  const [baseVersion, setBaseVersion] = useState<string | null>(() => defaultBase(detail, versions));
  const [loaded, setLoaded] = useState<VersionDetail | null>(null);
  const [failed, setFailed] = useState<{ version: string; message: string } | null>(null);

  useEffect(() => {
    if (!baseVersion) return;
    let live = true;
    load(baseVersion).then(
      (d) => {
        if (!live) return;
        setLoaded(d);
        const refs = changedRefs(d.files, detail.files);
        onChanges(refs, `${refs.length} config entr${refs.length === 1 ? "y" : "ies"} changed since ${d.version}`);
      },
      (e: unknown) => live && setFailed({ version: baseVersion, message: e instanceof Error ? e.message : String(e) }),
    );
    return () => {
      live = false;
    };
  }, [baseVersion, load, detail.files, onChanges]);

  // Only what belongs to the version chosen now: a slower earlier load never shows.
  const base = loaded?.version === baseVersion ? loaded : null;
  const error = failed?.version === baseVersion ? failed.message : null;

  const changed = useMemo(() => (base ? changedRefs(base.files, detail.files) : []), [base, detail.files]);

  const fileDiffs = useMemo(() => {
    if (!base) return [];
    const paths = [...new Set([...Object.keys(base.files), ...Object.keys(detail.files)])].sort();
    return paths
      .map((path) => {
        const lines = lineDiff(prettyJson(base.files[path] ?? ""), prettyJson(detail.files[path] ?? ""));
        return { path, lines, count: changeCount(lines) };
      })
      .filter((f) => f.count.added || f.count.removed);
  }, [base, detail.files]);

  const others = versions.filter((v) => v.version !== detail.version);
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div className="op-banner">
        Compare <b className="op-mono">{detail.version}</b> with
        <select value={baseVersion ?? ""} onChange={(e) => setBaseVersion(e.target.value || null)}>
          <option value="">choose a version</option>
          {others.map((v) => (
            <option key={v.version} value={v.version}>
              {v.version}
            </option>
          ))}
        </select>
      </div>
      {error && <div className="op-banner op-banner--error">{error}</div>}
      {base && (
        <section className="op-card">
          <div className="op-card__title">Changed config ({changed.length})</div>
          <div className="op-card__body op-chips">
            {changed.length === 0 && <span className="op-empty">No differences</span>}
            {changed.map((ref) => (
              <span
                key={ref}
                className="op-chip"
                onMouseEnter={() => onRefs([ref], refLabel(ref))}
                onMouseLeave={onClear}
              >
                {refLabel(ref)}
              </span>
            ))}
          </div>
        </section>
      )}
      {fileDiffs.map((f) => (
        <section className="op-card" key={f.path}>
          <div className="op-card__title">
            <span className="op-mono">{f.path}</span>
            <span className="op-diffstat">
              <span className="op-diffstat__add">+{f.count.added}</span>{" "}
              <span className="op-diffstat__del">−{f.count.removed}</span>
            </span>
          </div>
          <DiffView rows={withContext(f.lines)} />
        </section>
      ))}
    </div>
  );
}
