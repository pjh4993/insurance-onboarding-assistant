"use client";

import { useState } from "react";
import { formatAgo, humanize } from "@/lib/format";
import type { SessionDetail } from "@/lib/types";
import { Badge, type Tone } from "../Badge";
import { KeyValue } from "../KeyValue";
import { RecommendationCardView } from "../RecommendationCardView";
import { STATUS_LABEL, waitingLabel } from "../labels";
import { StageStrip } from "../StageStrip";

const VERIFICATION_TONE: Record<string, Tone> = {
  VERIFIED: "success",
  PENDING: "accent",
  FAILED: "danger",
  UNVERIFIED: "muted",
};

/** Where the flow got to, from the entities, for terminal stages that do not say. */
function progressFromEntities(d: SessionDetail): number {
  if (d.entities.application) return 3;
  if (d.entities.recommendations.length) return 2;
  if (d.entities.needs_assessment) return 1;
  return 0;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="facts__row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function ProgressTab({ d, now }: { d: SessionDetail; now: number }) {
  const s = d.session;
  const party = d.entities.party;
  const vStatus = typeof party?.verification_status === "string" ? party.verification_status : "UNVERIFIED";
  const vMethod = typeof party?.verification_method === "string" ? party.verification_method : null;
  const vAttempts = typeof party?.verification_attempts === "number" ? party.verification_attempts : null;
  const currency = s.market === "KR" ? "KRW" : "USD";

  return (
    <div className="tab">
      <StageStrip stage={s.stage} fallback={progressFromEntities(d)} />
      {["HANDOFF", "DECLINED", "WITHDRAWN"].includes(s.stage) && (
        <p className={`banner banner--${s.stage === "HANDOFF" ? "warning" : "muted"}`}>
          {s.stage === "HANDOFF" ? "Handed off to an agent" : `Session ${humanize(s.stage).toLowerCase()}`}
        </p>
      )}
      <dl className="facts">
        <Row label="Current node">
          <code>{d.current_node ?? "—"}</code>
        </Row>
        <Row label="Waiting for">{waitingLabel(s.waiting_for)}</Row>
        <Row label="Status">{STATUS_LABEL[s.status]}</Row>
        <Row label="Mode">{s.mode}</Row>
        <Row label="Assigned">{s.assigned_agent_id ?? "—"}</Row>
        <Row label="Last activity">{formatAgo(s.last_activity_at, now)}</Row>
      </dl>

      <h4 className="tab__h">Identity</h4>
      <div className="identity">
        <Badge tone={VERIFICATION_TONE[vStatus] ?? "neutral"}>{humanize(vStatus)}</Badge>
        {vMethod && <span>via {humanize(vMethod)}</span>}
        {vAttempts !== null && vAttempts > 0 && <span className="muted">{vAttempts} failed attempt(s)</span>}
      </div>

      {d.entities.needs_assessment && (
        <>
          <h4 className="tab__h">Needs assessment</h4>
          <KeyValue data={d.entities.needs_assessment} currency={currency} />
        </>
      )}
      {d.entities.insurable_objects.length > 0 && (
        <>
          <h4 className="tab__h">Insurable objects</h4>
          {d.entities.insurable_objects.map((o, i) => (
            <div className="card-plain" key={String(o.insurable_object_id ?? i)}>
              <KeyValue data={o} currency={currency} />
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function ApplicationTab({ d }: { d: SessionDetail }) {
  const app = d.entities.application;
  const recs = [...d.entities.recommendations].sort((a, b) => a.rank - b.rank);
  const currency = d.session.market === "KR" ? "KRW" : "USD";
  return (
    <div className="tab">
      <h4 className="tab__h">Recommendations</h4>
      {recs.length === 0 ? (
        <p className="muted">No recommendations yet.</p>
      ) : (
        <div className="rec-grid rec-grid--single">
          {recs.map((r) => (
            <RecommendationCardView key={r.recommendation_id} card={r} />
          ))}
        </div>
      )}

      <h4 className="tab__h">Application</h4>
      {!app ? (
        <p className="muted">No application yet.</p>
      ) : (
        <>
          {app.submission_ref && (
            <div className="banner banner--success">
              Submitted · <strong>{app.submission_ref}</strong>
            </div>
          )}
          <dl className="facts">
            <Row label="Status">{humanize(app.status)}</Row>
            <Row label="Application ID">
              <code>{app.application_id}</code>
            </Row>
          </dl>
          {app.missing_fields.length > 0 && (
            <div className="missing">
              <span>Missing</span>
              {app.missing_fields.map((f) => (
                <Badge key={f} tone="warning">
                  {humanize(f)}
                </Badge>
              ))}
            </div>
          )}
          <h5 className="tab__h5">Answers</h5>
          <KeyValue data={app.answers} currency={currency} />
          {app.summary && (
            <>
              <h5 className="tab__h5">Summary</h5>
              <p className="summary">{app.summary}</p>
            </>
          )}
        </>
      )}

      <h4 className="tab__h">Parties</h4>
      {d.entities.application_parties.length === 0 ? (
        <p className="muted">No parties yet.</p>
      ) : (
        <ul className="parties">
          {d.entities.application_parties.map((p, i) => (
            <li key={`${p.role}-${i}`}>
              <Badge tone="neutral">{humanize(p.role)}</Badge> {p.full_name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ArtifactPanel({ detail, now }: { detail: SessionDetail; now: number }) {
  const [tab, setTab] = useState<"progress" | "application">("progress");
  return (
    <div className="artifacts">
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "progress"} onClick={() => setTab("progress")}>
          Progress
        </button>
        <button role="tab" aria-selected={tab === "application"} onClick={() => setTab("application")}>
          Application
        </button>
      </div>
      {tab === "progress" ? <ProgressTab d={detail} now={now} /> : <ApplicationTab d={detail} />}
    </div>
  );
}
