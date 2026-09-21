"use client";

import type { DiffRow } from "@/lib/operator/versions";

/** A file with line numbers. */
export function CodeView({ text }: { text: string }) {
  return (
    <pre className="op-code">
      {text.split("\n").map((line, i) => (
        <div className="op-code__line" key={i}>
          <span className="op-code__no">{i + 1}</span>
          <span className="op-code__text">{line || " "}</span>
        </div>
      ))}
    </pre>
  );
}

/** A diff with folded unchanged runs. */
export function DiffView({ rows }: { rows: DiffRow[] }) {
  return (
    <pre className="op-code">
      {rows.map((row, i) =>
        row.kind === "gap" ? (
          <div className="op-code__gap" key={i}>
            ⋯ {row.count} unchanged line{row.count === 1 ? "" : "s"}
          </div>
        ) : (
          <div className={`op-code__line op-code__line--${row.kind}`} key={i}>
            <span className="op-code__no">{row.kind === "del" ? row.a : row.b}</span>
            <span className="op-code__text">
              {row.kind === "add" ? "+ " : row.kind === "del" ? "- " : "  "}
              {row.text}
            </span>
          </div>
        ),
      )}
    </pre>
  );
}
