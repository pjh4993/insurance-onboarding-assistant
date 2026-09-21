"use client";

import { useTranslations } from "next-intl";
import type { Market } from "@/lib/types";

const MARKETS = ["KR", "US"] as const satisfies readonly Market[];

/** KR / US toggle for the public landing page; same look as the language switch. */
export function MarketSwitch({
  value,
  onChange,
  disabled,
}: {
  value: Market;
  onChange: (market: Market) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("home");
  return (
    <div className="locale-switch" role="radiogroup" aria-label={t("market")}>
      {MARKETS.map((m) => (
        <button
          key={m}
          type="button"
          role="radio"
          aria-checked={value === m}
          title={t(`marketName.${m}`)}
          className={value === m ? "is-on" : ""}
          disabled={disabled}
          onClick={() => value !== m && onChange(m)}
        >
          {m}
        </button>
      ))}
    </div>
  );
}
