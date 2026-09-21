"use client";

import { useState } from "react";
import { refLabel, refsInFile } from "@/lib/operator/refs";
import { prettyJson } from "@/lib/operator/versions";
import { CodeView } from "./CodeView";
import type { HighlightRefs } from "./types";

type Props = { files: Record<string, string>; onRefs: HighlightRefs; onClear: () => void };

export function FilesTab({ files, onRefs, onClear }: Props) {
  const paths = Object.keys(files).sort((a, b) => (a === "config.json" ? -1 : b === "config.json" ? 1 : a.localeCompare(b)));
  const [path, setPath] = useState(paths[0] ?? "config.json");
  const refs = refsInFile(files, path);
  return (
    <div className="op-files">
      <section className="op-card">
        <div className="op-card__title">Files</div>
        <ul className="op-tree">
          {paths.map((p) => (
            <li key={p}>
              <button type="button" aria-current={p === path} onClick={() => setPath(p)}>
                {p}
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section className="op-card">
        <div className="op-card__title">
          <span className="op-mono">{path}</span>
        </div>
        {refs.length > 0 && (
          <div className="op-card__body op-chips" style={{ borderBottom: "1px solid var(--op-line)" }}>
            {refs.map((ref) => (
              <button
                type="button"
                key={ref}
                className="op-chip"
                onMouseEnter={() => onRefs([ref], refLabel(ref))}
                onFocus={() => onRefs([ref], refLabel(ref))}
                onMouseLeave={onClear}
                onBlur={onClear}
              >
                {refLabel(ref)}
              </button>
            ))}
          </div>
        )}
        <CodeView text={prettyJson(files[path] ?? "")} />
      </section>
    </div>
  );
}
