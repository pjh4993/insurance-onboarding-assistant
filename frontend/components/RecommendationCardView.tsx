"use client";

import { useTranslations } from "next-intl";
import { useFormat } from "@/i18n/useFormat";
import { humanize } from "@/lib/format";
import type { RecommendationCard } from "@/lib/types";
import { Badge } from "./Badge";

export function RecommendationCardView({
  card,
  actions,
}: {
  card: RecommendationCard;
  actions?: React.ReactNode;
}) {
  const t = useTranslations("rec");
  const f = useFormat();
  const ineligible = card.eligibility_result === "INELIGIBLE";
  return (
    <article className={`rec ${ineligible ? "rec--ineligible" : ""}`}>
      <header className="rec__head">
        <span className="rec__rank" aria-label={t("rank", { rank: card.rank })}>
          #{card.rank}
        </span>
        <div className="rec__title">
          <h4>{card.marketing_name}</h4>
          <span className="rec__type">{f.enumLabel("productType", card.product_type)}</span>
        </div>
        {card.status !== "PROPOSED" && (
          <Badge tone={card.status === "ACCEPTED" ? "success" : "muted"}>{f.enumLabel("recStatus", card.status)}</Badge>
        )}
      </header>

      {ineligible ? (
        <div className="rec__reasons">
          <strong>{t("notEligible")}</strong>
          <ul>
            {card.failed_reasons.length ? (
              card.failed_reasons.map((r) => <li key={r}>{humanize(r)}</li>)
            ) : (
              <li>{t("noReason")}</li>
            )}
          </ul>
        </div>
      ) : (
        <>
          {card.quote ? (
            <div className="rec__price">
              <span className="rec__amount">{f.money(card.quote.premium_minor, card.quote.currency)}</span>
              <span className="rec__period">{f.period(card.quote.billing_period)}</span>
            </div>
          ) : (
            <div className="rec__price rec__price--none">{t("quotePending")}</div>
          )}
          {card.rationale && <p className="rec__rationale">{card.rationale}</p>}
          {card.quote && (
            <dl className="rec__terms">
              <div>
                <dt>{t("cover")}</dt>
                <dd>
                  {f.date(card.quote.term_start_date)} – {f.date(card.quote.term_end_date)}
                </dd>
              </div>
              <div>
                <dt>{t("validUntil")}</dt>
                <dd>{f.date(card.quote.valid_until)}</dd>
              </div>
            </dl>
          )}
        </>
      )}
      {actions && <footer className="rec__actions">{actions}</footer>}
    </article>
  );
}
