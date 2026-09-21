"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { sessionLocale } from "@/i18n/locales";
import { useFormat } from "@/i18n/useFormat";
import { humanize } from "@/lib/format";
import type { Locale, SessionDetail } from "@/lib/types";
import { Badge, type Tone } from "../Badge";
import { KeyValue } from "../KeyValue";
import { RecommendationCardView } from "../RecommendationCardView";
import { LocaleSwitch } from "../LocaleSwitch";
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

/** The customer's language for this session; changing it also changes the assistant's language. */
function SessionLanguage({ d, onLocale }: { d: SessionDetail; onLocale: (locale: Locale) => Promise<void> }) {
  const t = useTranslations("agent.artifacts");
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  return (
    <>
      <LocaleSwitch
        value={sessionLocale(d.session)}
        disabled={pending}
        onChange={async (l) => {
          setPending(true);
          setFailed(false);
          try {
            await onLocale(l);
          } catch {
            setFailed(true);
          } finally {
            setPending(false);
          }
        }}
      />
      {failed && <p className="input-panel__error">{t("languageFailed")}</p>}
    </>
  );
}

function ProgressTab({
  d,
  now,
  onLocale,
}: {
  d: SessionDetail;
  now: number;
  onLocale: (locale: Locale) => Promise<void>;
}) {
  const t = useTranslations();
  const f = useFormat();
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
          {s.stage === "HANDOFF"
            ? t("agent.artifacts.handedOff")
            : t("agent.artifacts.sessionEnded", { status: t(`stage.${s.stage}`) })}
        </p>
      )}
      <dl className="facts">
        <Row label={t("agent.artifacts.currentNode")}>
          <code>{d.current_node ?? "—"}</code>
        </Row>
        <Row label={t("agent.artifacts.waitingFor")}>
          {t(s.waiting_for ? `waiting.${s.waiting_for}` : "waiting.nothing")}
        </Row>
        <Row label={t("agent.artifacts.status")}>{t(`status.${s.status}`)}</Row>
        <Row label={t("agent.artifacts.mode")}>{s.mode}</Row>
        <Row label={t("agent.artifacts.assigned")}>{s.assigned_agent_id ?? "—"}</Row>
        <Row label={t("agent.artifacts.lastActivity")}>{f.ago(s.last_activity_at, now)}</Row>
        <Row label={t("agent.artifacts.language")}>
          <SessionLanguage d={d} onLocale={onLocale} />
        </Row>
      </dl>

      <h4 className="tab__h">{t("agent.artifacts.identity")}</h4>
      <div className="identity">
        <Badge tone={VERIFICATION_TONE[vStatus] ?? "neutral"}>{f.enumLabel("verification", vStatus)}</Badge>
        {vMethod && <span>{t("agent.artifacts.via", { method: f.enumLabel("verificationMethod", vMethod) })}</span>}
        {vAttempts !== null && vAttempts > 0 && (
          <span className="muted">{t("agent.artifacts.failedAttempts", { count: vAttempts })}</span>
        )}
      </div>

      {d.entities.needs_assessment && (
        <>
          <h4 className="tab__h">{t("agent.artifacts.needs")}</h4>
          <KeyValue data={d.entities.needs_assessment} currency={currency} />
        </>
      )}
      {d.entities.insurable_objects.length > 0 && (
        <>
          <h4 className="tab__h">{t("agent.artifacts.objects")}</h4>
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
  const t = useTranslations("agent.artifacts");
  const f = useFormat();
  const app = d.entities.application;
  const recs = [...d.entities.recommendations].sort((a, b) => a.rank - b.rank);
  const currency = d.session.market === "KR" ? "KRW" : "USD";
  return (
    <div className="tab">
      <h4 className="tab__h">{t("recommendations")}</h4>
      {recs.length === 0 ? (
        <p className="muted">{t("noRecommendations")}</p>
      ) : (
        <div className="rec-grid rec-grid--single">
          {recs.map((r) => (
            <RecommendationCardView key={r.recommendation_id} card={r} />
          ))}
        </div>
      )}

      <h4 className="tab__h">{t("application")}</h4>
      {!app ? (
        <p className="muted">{t("noApplication")}</p>
      ) : (
        <>
          {app.submission_ref && (
            <div className="banner banner--success">
              {t("submitted")} · <strong>{app.submission_ref}</strong>
            </div>
          )}
          <dl className="facts">
            <Row label={t("status")}>{humanize(app.status)}</Row>
            <Row label={t("applicationId")}>
              <code>{app.application_id}</code>
            </Row>
          </dl>
          {app.missing_fields.length > 0 && (
            <div className="missing">
              <span>{t("missing")}</span>
              {app.missing_fields.map((f) => (
                <Badge key={f} tone="warning">
                  {humanize(f)}
                </Badge>
              ))}
            </div>
          )}
          <h5 className="tab__h5">{t("answers")}</h5>
          <KeyValue data={app.answers} currency={currency} />
          {app.summary && (
            <>
              <h5 className="tab__h5">{t("summary")}</h5>
              <p className="summary">{app.summary}</p>
            </>
          )}
        </>
      )}

      <h4 className="tab__h">{t("parties")}</h4>
      {d.entities.application_parties.length === 0 ? (
        <p className="muted">{t("noParties")}</p>
      ) : (
        <ul className="parties">
          {d.entities.application_parties.map((p, i) => (
            <li key={`${p.role}-${i}`}>
              <Badge tone="neutral">{f.enumLabel("partyRole", p.role)}</Badge> {p.full_name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ArtifactPanel({
  detail,
  now,
  onLocale,
}: {
  detail: SessionDetail;
  now: number;
  onLocale: (locale: Locale) => Promise<void>;
}) {
  const t = useTranslations("agent.artifacts");
  const [tab, setTab] = useState<"progress" | "application">("progress");
  return (
    <div className="artifacts">
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "progress"} onClick={() => setTab("progress")}>
          {t("progress")}
        </button>
        <button role="tab" aria-selected={tab === "application"} onClick={() => setTab("application")}>
          {t("application")}
        </button>
      </div>
      {tab === "progress" ? <ProgressTab d={detail} now={now} onLocale={onLocale} /> : <ApplicationTab d={detail} />}
    </div>
  );
}
