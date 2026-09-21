"use client";

import { useMemo, useState } from "react";
import type { Outline } from "@/lib/operator/refs";

const WIDTH = 400;
const ROW = 26;
const BAND = 24;
const PILL_X = 16;
const PILL_W = 250;
const ARC_X = PILL_X + PILL_W + 6;

type Props = {
  outline: Outline | null;
  /** node -> model profile of the version on screen */
  nodeModels: Record<string, string>;
  highlight: Set<string>;
  caption: string | null;
};

/**
 * The agent loop as an arc diagram: nodes top to bottom in domain bands, edges as arcs on the right (a loop back
 * up is dashed). Nodes a config entry reaches are highlighted. Every processing node can also hand off to an
 * agent; those edges are hidden unless asked for.
 */
export function AgentLoop({ outline, nodeModels, highlight, caption }: Props) {
  const [showHandoffs, setShowHandoffs] = useState(false);

  const layout = useMemo(() => {
    if (!outline) return null;
    const y = new Map<string, number>();
    const bands: { domain: string; top: number; bottom: number }[] = [];
    let cursor = 8;
    let current: string | null = null;
    for (const node of outline.nodes) {
      if (node.domain !== current) {
        if (bands.length) bands[bands.length - 1].bottom = cursor;
        current = node.domain;
        bands.push({ domain: node.domain, top: cursor, bottom: cursor });
        cursor += BAND;
      }
      y.set(node.id, cursor + ROW / 2);
      cursor += ROW;
    }
    if (bands.length) bands[bands.length - 1].bottom = cursor;
    const ends = new Set(outline.edges.filter((e) => e.target === "__end__").map((e) => e.source));
    return { y, bands, height: cursor + 12, ends };
  }, [outline]);

  if (!outline || !layout) return <div className="op-section-title">Loading the agent loop…</div>;

  const lit = (id: string) => highlight.has(id);
  const anyLit = highlight.size > 0;
  const edges = outline.edges.filter(
    (e) => e.target !== "__end__" && (showHandoffs || e.target !== "human_handoff" || e.source === "ask_customer"),
  );

  return (
    <>
      <div className="op-loop__head">
        <div className="op-section-title">Agent loop</div>
        <label className="op-loop__toggle">
          <input type="checkbox" checked={showHandoffs} onChange={(e) => setShowHandoffs(e.target.checked)} />
          handoff edges
        </label>
      </div>
      <div className={`op-loop__caption${caption ? "" : " op-loop__caption--idle"}`}>
        {caption ?? "Hover a config entry, or open Compare or Edit, to see which nodes it touches."}
      </div>
      <svg width={WIDTH} height={layout.height} role="img" aria-label="Agent loop">
        {layout.bands.map((band, i) => (
          <g key={band.domain}>
            <rect x={0} y={band.top} width={WIDTH} height={band.bottom - band.top} fill={i % 2 ? "#fafbfc" : "#ffffff"} />
            <text x={PILL_X} y={band.top + 16} fontSize={10.5} fontWeight={700} fill="#8b909a" letterSpacing="0.06em">
              {band.domain.toUpperCase()}
            </text>
          </g>
        ))}
        {edges.map((e) => {
          const y1 = layout.y.get(e.source);
          const y2 = layout.y.get(e.target);
          if (y1 === undefined || y2 === undefined) return null;
          const span = Math.abs(y2 - y1);
          const bulge = Math.min(WIDTH - ARC_X - 8, 14 + span * 0.28);
          const hot = lit(e.source) || lit(e.target);
          const back = y2 < y1;
          return (
            <path
              key={`${e.source}->${e.target}`}
              d={`M ${ARC_X} ${y1} C ${ARC_X + bulge} ${y1}, ${ARC_X + bulge} ${y2}, ${ARC_X + 4} ${y2}`}
              fill="none"
              stroke={hot ? "#ffb300" : e.kind === "resume" ? "#b59be0" : "#c9ccd2"}
              strokeWidth={hot ? 2 : 1.2}
              strokeDasharray={back ? "4 3" : undefined}
              opacity={anyLit && !hot ? 0.35 : 1}
              markerEnd="url(#op-arrow)"
            />
          );
        })}
        <defs>
          <marker id="op-arrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M 6 0 L 0 3 L 6 6 z" fill="#9ea3ab" />
          </marker>
        </defs>
        {outline.nodes.map((node) => {
          const cy = layout.y.get(node.id)!;
          const on = lit(node.id);
          const model = node.kind === "llm" ? nodeModels[node.id] : undefined;
          return (
            <g key={node.id} opacity={anyLit && !on ? 0.45 : 1}>
              <title>{`${node.id} (${node.kind})\nreads: ${node.reads.join(", ") || "no config"}`}</title>
              <rect
                x={PILL_X}
                y={cy - 10}
                width={PILL_W}
                height={20}
                rx={10}
                fill={on ? "#fff1c9" : node.kind === "llm" ? "#f3efff" : node.kind === "wait" ? "#eef6ff" : "#f4f5f7"}
                stroke={on ? "#ffb300" : "#d9dce1"}
                strokeWidth={on ? 1.8 : 1}
              />
              <text x={PILL_X + 10} y={cy + 4} fontSize={11.5} fontFamily="var(--mono)" fill="#1a1d24">
                {node.id}
              </text>
              <text x={PILL_X + PILL_W - 8} y={cy + 4} fontSize={9.5} textAnchor="end" fill="#6b7280">
                {node.kind === "llm" ? `LLM${model ? ` · ${model}` : ""}` : node.kind === "wait" ? "wait" : ""}
                {layout.ends.has(node.id) ? " ⏹" : ""}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="op-loop__legend">
        <span>▭ purple: LLM node</span>
        <span>▭ blue: waits for a person</span>
        <span>- - loop back</span>
        <span>⏹ can end</span>
        <span>purple arc: resumes after a handoff</span>
      </div>
    </>
  );
}
