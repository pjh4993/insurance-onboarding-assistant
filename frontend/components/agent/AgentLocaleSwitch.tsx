"use client";

import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { AGENT_LOCALE_COOKIE, type Locale } from "@/i18n/locales";
import { LocaleSwitch } from "../LocaleSwitch";

/** The agent's own UI language: a cookie the server reads (i18n/request.ts), then a re-render. */
export function AgentLocaleSwitch() {
  const locale = useLocale();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <LocaleSwitch
      value={locale}
      disabled={pending}
      onChange={(next: Locale) => {
        document.cookie = `${AGENT_LOCALE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
        startTransition(() => router.refresh());
      }}
    />
  );
}
