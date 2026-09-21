"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { agentApi, ApiError } from "@/lib/api";
import { appendMessage, upsertSession, sortSessions } from "@/lib/session";
import type { InputBody, SessionDetail, SessionSummary } from "@/lib/types";
import { useEventStream } from "@/lib/useEventStream";
import { ArtifactPanel } from "./ArtifactPanel";
import { Conversation } from "./Conversation";
import { NewSession } from "./NewSession";
import { SessionList } from "./SessionList";

const BUSY_TIMEOUT_MS = 30_000;

function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

export function AgentConsole() {
  const [me, setMe] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [view, setView] = useState<"list" | "chat" | "artifacts">("list"); // narrow screens only
  const selectedRef = useRef<string | null>(null);
  const now = useNow();

  // ---- session list (column 1)
  const loadList = useCallback(() => {
    agentApi
      .listSessions()
      .then((r) => {
        setSessions(sortSessions(r.sessions));
        setListError(null);
      })
      .catch((e: unknown) => setListError(e instanceof ApiError ? e.message : "Could not load sessions"));
  }, []);

  useEffect(() => {
    agentApi.me().then((r) => setMe(r.agent_id), () => setMe(null));
    loadList();
  }, [loadList]);

  const listStream = useEventStream(agentApi.streamUrl, {
    onOpen: loadList,
    "session.updated": ({ session }) => {
      setSessions((prev) => upsertSession(prev, session));
      if (session.session_id === selectedRef.current) setDetail((d) => d && { ...d, session });
    },
  });

  // ---- selected session (columns 2 and 3)
  const loadDetail = useCallback((id: string) => {
    agentApi
      .getSession(id)
      .then((d) => {
        if (selectedRef.current !== id) return; // a newer selection won
        setDetail(d);
        setDetailError(null);
      })
      .catch((e: unknown) => {
        if (selectedRef.current !== id) return;
        setDetailError(e instanceof ApiError ? e.message : "Could not load the session");
      });
  }, []);

  function select(id: string) {
    selectedRef.current = id;
    setSelectedId(id);
    setDetail(null);
    setDetailError(null);
    setBusy(false);
    setView("chat");
    loadDetail(id);
  }

  // entity.updated carries only ids; refetch the detail, coalescing bursts.
  const refetchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scheduleRefetch = useCallback(() => {
    const id = selectedRef.current;
    if (!id) return;
    if (refetchTimer.current) clearTimeout(refetchTimer.current);
    refetchTimer.current = setTimeout(() => loadDetail(id), 250);
  }, [loadDetail]);
  useEffect(() => () => {
    if (refetchTimer.current) clearTimeout(refetchTimer.current);
  }, []);

  const mine = (sid: string) => sid === selectedRef.current;
  useEventStream(selectedId ? agentApi.sessionStreamUrl(selectedId) : null, {
    onOpen: () => selectedRef.current && loadDetail(selectedRef.current),
    "session.updated": ({ session }) => {
      if (mine(session.session_id)) setDetail((d) => d && { ...d, session });
    },
    "message.appended": ({ session_id, message }) => {
      if (!mine(session_id)) return;
      setDetail((d) => d && { ...d, messages: appendMessage(d.messages, message) });
      if (message.role === "assistant" || message.role === "system") setBusy(false);
    },
    "prompt.updated": ({ session_id, prompt }) => {
      if (!mine(session_id)) return;
      setDetail((d) => d && { ...d, prompt });
      setBusy(false);
    },
    "entity.updated": ({ session_id }) => {
      if (mine(session_id)) scheduleRefetch();
    },
  });

  useEffect(() => {
    if (!busy) return;
    const t = setTimeout(() => setBusy(false), BUSY_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [busy]);

  async function assign() {
    if (!selectedId) return;
    setAssigning(true);
    try {
      const s = await agentApi.assign(selectedId);
      setSessions((prev) => upsertSession(prev, s));
      setDetail((d) => (d && d.session.session_id === s.session_id ? { ...d, session: s } : d));
    } catch (e) {
      setDetailError(e instanceof ApiError ? e.message : "Could not assign the session");
    } finally {
      setAssigning(false);
    }
  }

  async function submit(body: InputBody) {
    if (!selectedId) return;
    await agentApi.sendInput(selectedId, body);
    setBusy(true);
  }

  const handoffCount = sessions.filter((s) => s.waiting_for === "AGENT").length;

  return (
    <div className={`console console--${view}`}>
      <header className="console__bar">
        <div className="brand">
          <span className="brand__mark" aria-hidden>
            ◆
          </span>
          <div>
            <strong>Agent console</strong>
            <span className="brand__sub">Onboarding sessions</span>
          </div>
        </div>
        <nav className="console__nav" aria-label="Panels">
          <button className={view === "list" ? "is-on" : ""} onClick={() => setView("list")}>
            Sessions{handoffCount ? ` (${handoffCount})` : ""}
          </button>
          <button className={view === "chat" ? "is-on" : ""} onClick={() => setView("chat")} disabled={!selectedId}>
            Chat
          </button>
          <button
            className={view === "artifacts" ? "is-on" : ""}
            onClick={() => setView("artifacts")}
            disabled={!selectedId}
          >
            Details
          </button>
        </nav>
        <div className="console__who">
          {listStream === "reconnecting" && <span className="conn">Reconnecting…</span>}
          <span className="muted">Signed in as</span> <strong>{me ?? "…"}</strong>
        </div>
      </header>

      <aside className="col col--list">
        <NewSession onCreated={loadList} />
        {listError && <p className="input-panel__error">{listError}</p>}
        <SessionList sessions={sessions} selectedId={selectedId} onSelect={select} me={me} now={now} />
      </aside>

      <section className="col col--chat">
        {!selectedId ? (
          <p className="empty">Select a session to see the conversation.</p>
        ) : detailError && !detail ? (
          <p className="empty">{detailError}</p>
        ) : !detail ? (
          <p className="empty">Loading…</p>
        ) : (
          <>
            {detailError && <p className="input-panel__error">{detailError}</p>}
            <Conversation
              detail={detail}
              me={me}
              busy={busy}
              assigning={assigning}
              onAssign={assign}
              onSubmit={submit}
            />
          </>
        )}
      </section>

      <aside className="col col--artifacts">
        {detail ? <ArtifactPanel key={detail.session.session_id} detail={detail} now={now} /> : <p className="empty">No session selected.</p>}
      </aside>
    </div>
  );
}
