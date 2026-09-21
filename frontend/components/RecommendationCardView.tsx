import { formatBillingPeriod, formatDate, formatMoney, humanize } from "@/lib/format";
import type { RecommendationCard } from "@/lib/types";
import { Badge } from "./Badge";

export function RecommendationCardView({
  card,
  actions,
}: {
  card: RecommendationCard;
  actions?: React.ReactNode;
}) {
  const ineligible = card.eligibility_result === "INELIGIBLE";
  return (
    <article className={`rec ${ineligible ? "rec--ineligible" : ""}`}>
      <header className="rec__head">
        <span className="rec__rank" aria-label={`Rank ${card.rank}`}>
          #{card.rank}
        </span>
        <div className="rec__title">
          <h4>{card.marketing_name}</h4>
          <span className="rec__type">{humanize(card.product_type)}</span>
        </div>
        {card.status !== "PROPOSED" && (
          <Badge tone={card.status === "ACCEPTED" ? "success" : "muted"}>{humanize(card.status)}</Badge>
        )}
      </header>

      {ineligible ? (
        <div className="rec__reasons">
          <strong>Not eligible</strong>
          <ul>
            {card.failed_reasons.length ? (
              card.failed_reasons.map((r) => <li key={r}>{humanize(r)}</li>)
            ) : (
              <li>No reason given</li>
            )}
          </ul>
        </div>
      ) : (
        <>
          {card.quote ? (
            <div className="rec__price">
              <span className="rec__amount">{formatMoney(card.quote.premium_minor, card.quote.currency)}</span>
              <span className="rec__period">{formatBillingPeriod(card.quote.billing_period)}</span>
            </div>
          ) : (
            <div className="rec__price rec__price--none">Quote pending</div>
          )}
          {card.rationale && <p className="rec__rationale">{card.rationale}</p>}
          {card.quote && (
            <dl className="rec__terms">
              <div>
                <dt>Cover</dt>
                <dd>
                  {formatDate(card.quote.term_start_date)} – {formatDate(card.quote.term_end_date)}
                </dd>
              </div>
              <div>
                <dt>Quote valid until</dt>
                <dd>{formatDate(card.quote.valid_until)}</dd>
              </div>
            </dl>
          )}
        </>
      )}
      {actions && <footer className="rec__actions">{actions}</footer>}
    </article>
  );
}
