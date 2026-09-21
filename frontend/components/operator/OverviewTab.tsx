"use client";

import type { VersionDetail } from "@/lib/operator/types";
import { timeAgo } from "@/lib/operator/versions";
import type { HighlightRefs } from "./types";

type Props = { detail: VersionDetail; now: number; onRefs: HighlightRefs; onClear: () => void };

export function OverviewTab({ detail, now, onRefs, onClear }: Props) {
  const { release, summary } = detail;
  const byProfile = new Map<string, string[]>();
  for (const [node, profile] of Object.entries(summary.nodes)) {
    byProfile.set(profile, [...(byProfile.get(profile) ?? []), node]);
  }
  return (
    <div className="op-grid">
      <section className="op-card">
        <div className="op-card__title">Description</div>
        <div className="op-card__body">
          {release.notes ? <div className="op-notes">{release.notes}</div> : <div className="op-empty">No notes</div>}
        </div>
      </section>

      <section className="op-card">
        <div className="op-card__title">Metadata</div>
        <div className="op-card__body">
          <dl className="op-kv">
            <dt>Version</dt>
            <dd className="op-mono">{detail.version}</dd>
            <dt>Published by</dt>
            <dd>{release.published_by ?? "—"}</dd>
            <dt>Published</dt>
            <dd title={release.published_at}>{release.published_at ? timeAgo(release.published_at, now) : "—"}</dd>
            <dt>Based on</dt>
            <dd className="op-mono">{release.based_on ?? "—"}</dd>
            <dt>Via</dt>
            <dd>{release.via ?? "—"}</dd>
            <dt>Copy entries</dt>
            <dd>{summary.copy_keys}</dd>
          </dl>
        </div>
      </section>

      <section className="op-card">
        <div className="op-card__title">Model profiles</div>
        <table className="op-table">
          <thead>
            <tr>
              <th>Profile</th>
              <th>Model</th>
              <th>Args</th>
            </tr>
          </thead>
          <tbody>
            {summary.models.map((m) => (
              <tr
                key={m.name}
                data-hot
                onMouseEnter={() => onRefs([`models:${m.name}`], `Model profile “${m.name}” (${m.model_id})`)}
                onMouseLeave={onClear}
              >
                <td className="op-mono">{m.name}</td>
                <td className="op-mono">{m.model_id}</td>
                <td className="op-mono">{JSON.stringify(m.args)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="op-card">
        <div className="op-card__title">LLM nodes</div>
        <table className="op-table">
          <thead>
            <tr>
              <th>Node</th>
              <th>Profile</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(summary.nodes).map(([node, profile]) => (
              <tr
                key={node}
                data-hot
                onMouseEnter={() => onRefs([`llm:${node}.model`], `${node} runs on “${profile}”`)}
                onMouseLeave={onClear}
              >
                <td className="op-mono">{node}</td>
                <td className="op-mono">{profile}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="op-card">
        <div className="op-card__title">Languages</div>
        <div className="op-card__body op-chips">
          {summary.languages.map((l) => (
            <span
              key={l.code}
              className="op-chip"
              onMouseEnter={() => onRefs(["languages"], `Every node that speaks or asks the LLM uses ${l.name}`)}
              onMouseLeave={onClear}
            >
              {l.code} · {l.name}
              {l.code === summary.default_language ? " (default)" : ""}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
