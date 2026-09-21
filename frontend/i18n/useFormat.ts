"use client";

import { useLocale, useTranslations } from "next-intl";
import { agoParts, formatDate, formatMoney, formatTime, humanize } from "@/lib/format";
import type { BillingPeriod } from "@/lib/types";
import { intlTag } from "./locales";

type EnumGroup = "productType" | "recStatus" | "verification" | "verificationMethod" | "partyRole";

/** Formatting in the active language: money, dates, "3m ago", billing periods and backend enum values. */
export function useFormat() {
  const tag = intlTag(useLocale());
  const t = useTranslations();
  return {
    money: (minor: number, currency: string) => formatMoney(minor, currency, tag),
    date: (iso: string) => formatDate(iso, tag),
    time: (iso: string) => formatTime(iso, tag),
    ago: (iso: string, now?: number) => {
      const p = agoParts(iso, now);
      return p ? t(`ago.${p.unit}`, { n: p.n }) : "";
    },
    period: (period: BillingPeriod | string) =>
      t.has(`period.${period as BillingPeriod}`) ? t(`period.${period as BillingPeriod}`) : humanize(period),
    /** A backend enum value in the active language; values the catalog does not know are humanized. */
    enumLabel: (group: EnumGroup, value: string) => {
      const key = `enum.${group}.${value}` as Parameters<typeof t.has>[0];
      return t.has(key) ? t(key as Parameters<typeof t>[0]) : humanize(value);
    },
  };
}
