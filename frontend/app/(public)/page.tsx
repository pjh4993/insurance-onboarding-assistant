import { getLocale } from "next-intl/server";
import { PublicLanding } from "@/components/customer/PublicLanding";
import { DEFAULT_LOCALE, isLocale } from "@/i18n/locales";
import { agentConsoleHref } from "@/lib/hosts";
import { agentBaseUrl } from "@/lib/server/config";
import { hasResumableSession } from "@/lib/server/resume";

export const dynamic = "force-dynamic";

/** The public landing page: anyone can start a session here, no link needed. */
export default async function Home() {
  const [locale, resumable] = await Promise.all([getLocale(), hasResumableSession()]);
  return (
    <PublicLanding
      initialLocale={isLocale(locale) ? locale : DEFAULT_LOCALE}
      resumable={resumable}
      agentHref={agentConsoleHref(agentBaseUrl())}
    />
  );
}
