"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { OperatorApiError, operatorApi } from "@/lib/operator/api";
import { nodesForAll, type Outline } from "@/lib/operator/refs";
import type { ConfigStatus, VersionDetail, VersionItem } from "@/lib/operator/types";
import { timeAgo } from "@/lib/operator/versions";
import { AgentLoop } from "./AgentLoop";
import { CompareTab } from "./CompareTab";
import { EditTab } from "./EditTab";
import { FilesTab } from "./FilesTab";
import { OverviewTab } from "./OverviewTab";
import type { Highlight } from "./types";

type Tab = "overview" | "files" | "compare" | "edit";
const TABS: [Tab, string][] = [
  ["overview", "Overview"],
  ["files", "Files"],
  ["compare", "Compare"],
  ["edit", "New version"],
];

function useNow(ms = 30_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

/**
 * The operator console: the agent config versions like an artifact's versions in Weights & Biases. The left
 * lists versions (latest, live), the middle shows one (overview, files, compare, a new version from it), the
 * right draws the agent loop and highlights what the config on screen touches.
 */
export function OperatorConsole() {
  const now = useNow();
  const [me, setMe] = useState<string | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [status, setStatus] = useState<ConfigStatus | null>(null);
  const [versions, setVersions] = useState<VersionItem[]>([]);
  const [outline, setOutline] = useState<Outline | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<VersionDetail | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [hover, setHover] = useState<Highlight | null>(null);
  const [changes, setChanges] = useState<Highlight | null>(null);
  const [confirmRestart, setConfirmRestart] = useState(false);
  const cache = useRef(new Map<string, VersionDetail>());

  const load = useCallback(async (version: string) => {
    const hit = cache.current.get(version);
    if (hit) return hit; // published versions never change
    const d = await operatorApi.version(version);
    cache.current.set(version, d);
    return d;
  }, []);

  const refresh = useCallback(async () => {
    const [s, v] = await Promise.all([operatorApi.status(), operatorApi.versions()]);
    setStatus(s);
    setVersions(v);
    return v;
  }, []);

  useEffect(() => {
    (async () => {
      try {
        setMe((await operatorApi.me()).operator_id);
        const [v, graph] = await Promise.all([refresh(), operatorApi.graph()]);
        setOutline(graph);
        setSelected((cur) => cur ?? v[0]?.version ?? null);
      } catch (e) {
        setFatal(
          e instanceof OperatorApiError && e.status === 401
            ? "Operator sign-in required: this console is for members of the operators group."
            : String(e instanceof Error ? e.message : e),
        );
      }
    })();
  }, [refresh]);

  useEffect(() => {
    if (!selected) return;
    let live = true;
    load(selected).then(
      (d) => live && setDetail(d),
      (e: unknown) => live && setNotice(String(e instanceof Error ? e.message : e)),
    );
    return () => {
      live = false;
    };
  }, [selected, load]);

  // Moving to another version or tab drops what the agent loop was highlighting for the previous one.
  const select = (version: string) => {
    setSelected(version);
    setChanges(null);
    setHover(null);
  };
  const openTab = (next: Tab) => {
    setTab(next);
    setChanges(null);
    setHover(null);
  };

  const shownDetail = detail?.version === selected ? detail : null;
  const nodeModels = useMemo(() => shownDetail?.summary?.nodes ?? {}, [shownDetail]);
  const highlightRefs = useCallback(
    (refs: string[], caption: string) =>
      outline ? setHover({ nodes: nodesForAll(refs, outline, nodeModels), caption }) : undefined,
    [outline, nodeModels],
  );
  const changeRefs = useCallback(
    (refs: string[], caption: string) =>
      outline && setChanges(refs.length ? { nodes: nodesForAll(refs, outline, nodeModels), caption } : null),
    [outline, nodeModels],
  );
  const clearHover = useCallback(() => setHover(null), []);
  const shown = hover ?? changes;

  const published = useMemo(() => versions.map((v) => v.version), [versions]);

  async function onPublished(version: string) {
    await refresh();
    select(version);
    openTab("overview");
    setNotice(`Published ${version}. The backend loads it after a restart.`);
  }

  async function restart() {
    setConfirmRestart(false);
    try {
      await operatorApi.restart();
      setNotice("Restarting the backend: new tasks load the next version, running turns finish on the old ones.");
    } catch (e) {
      setNotice(`Restart failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  const current = versions.find((v) => v.version === selected);
  return (
    <>
      <header className="op-bar">
        <div className="op-logo">
          <span className="op-logo__dots">
            <span />
            <span />
            <span />
            <span />
          </span>
          Operator
        </div>
        <nav className="op-crumbs" aria-label="Breadcrumb">
          <span>onboarding</span>›<span>artifacts</span>›<b>agent-config</b>
          {selected && (
            <>
              ›<code>v{selected}</code>
            </>
          )}
        </nav>
        <div className="op-bar__right">
          {status && (
            <>
              <span className="op-pill" title={status.live.source}>
                <i /> live v{status.live.version}
              </span>
              {status.restart_needed && status.next && (
                <span className="op-pill op-pill--next" title={`AGENT_CONFIG_VERSION=${status.version_spec}`}>
                  <i /> next v{status.next}
                </span>
              )}
              {status.restart_needed && status.restartable && (
                <button
                  type="button"
                  className={`op-btn ${confirmRestart ? "op-btn--primary" : "op-btn--dark"}`}
                  onClick={() => (confirmRestart ? restart() : setConfirmRestart(true))}
                  onBlur={() => setConfirmRestart(false)}
                >
                  {confirmRestart ? `Restart to load v${status.next}?` : "Restart backend"}
                </button>
              )}
            </>
          )}
          {me && <span className="op-who">{me}</span>}
        </div>
      </header>

      <div className="op-body">
        <aside className="op-side">
          <div className="op-section-title">Artifact</div>
          <div className="op-artifact">
            <div className="op-artifact__name">agent-config</div>
            <div className="op-artifact__meta">
              type: config bundle · {versions.length} version{versions.length === 1 ? "" : "s"}
            </div>
            {status && (
              <div className="op-artifact__meta op-mono op-ellipsis" title={status.base}>
                {status.base}
              </div>
            )}
          </div>
          <div className="op-section-title">Versions</div>
          <ul className="op-versions">
            {versions.map((v) => (
              <li key={v.version}>
                <button
                  type="button"
                  className={`op-version${v.version === selected ? " op-version--on" : ""}`}
                  onClick={() => select(v.version)}
                >
                  <div className="op-version__row">
                    <span className="op-version__name">v{v.version}</span>
                    {v.latest && <span className="op-alias op-alias--latest">latest</span>}
                    {v.live && <span className="op-alias op-alias--live">live</span>}
                    {!v.live && status?.restart_needed && status.next === v.version && (
                      <span className="op-alias op-alias--next">next</span>
                    )}
                  </div>
                  <div className="op-version__meta">
                    {v.release.published_by ?? "unknown"} · {timeAgo(v.release.published_at, now) || "—"}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main className="op-main">
          {fatal && <div className="op-banner op-banner--error">{fatal}</div>}
          {notice && (
            <div className="op-banner">
              {notice}
              <button type="button" className="op-btn" style={{ marginLeft: "auto" }} onClick={() => setNotice(null)}>
                Dismiss
              </button>
            </div>
          )}
          {shownDetail && current && (
            <>
              <div className="op-head">
                <h1>
                  agent-config<span>:</span>v{shownDetail.version}
                </h1>
                <div className="op-head__aliases">
                  {current.latest && <span className="op-alias op-alias--latest">latest</span>}
                  {current.live && <span className="op-alias op-alias--live">live</span>}
                </div>
                <div className="op-head__actions">
                  <button type="button" className="op-btn" onClick={() => openTab("edit")}>
                    New version from this
                  </button>
                </div>
              </div>
              <div className="op-sub">
                {shownDetail.release.published_by ?? "unknown"} published {timeAgo(shownDetail.release.published_at, now) || "—"}
                {shownDetail.release.based_on ? ` · based on v${shownDetail.release.based_on}` : ""}
              </div>
              <div className="op-tabs" role="tablist">
                {TABS.map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    role="tab"
                    aria-selected={tab === id}
                    className={`op-tab${tab === id ? " op-tab--on" : ""}`}
                    onClick={() => openTab(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {tab === "overview" && (
                <OverviewTab detail={shownDetail} now={now} onRefs={highlightRefs} onClear={clearHover} />
              )}
              {tab === "files" && <FilesTab files={shownDetail.files} onRefs={highlightRefs} onClear={clearHover} />}
              {tab === "compare" && (
                <CompareTab
                  key={shownDetail.version}
                  detail={shownDetail}
                  versions={versions}
                  load={load}
                  onChanges={changeRefs}
                  onRefs={highlightRefs}
                  onClear={clearHover}
                />
              )}
              {tab === "edit" && (
                <EditTab
                  key={shownDetail.version}
                  base={shownDetail}
                  published={published}
                  status={status}
                  onChanges={changeRefs}
                  onRefs={highlightRefs}
                  onClear={clearHover}
                  onPublished={onPublished}
                />
              )}
            </>
          )}
          {!shownDetail && !fatal && <div className="op-empty">Loading…</div>}
        </main>

        <aside className="op-loop">
          <AgentLoop
            outline={outline}
            nodeModels={nodeModels}
            highlight={shown?.nodes ?? new Set()}
            caption={shown?.caption || null}
          />
        </aside>
      </div>
    </>
  );
}
