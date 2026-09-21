import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { AGENT_LOCALE_COOKIE, isLocale, negotiateLocale } from "./locales";
import { MESSAGES } from "./messages";

/**
 * The server-rendered language: the agent's cookie if set, else the browser's Accept-Language.
 * The customer app starts here too (loading and error screens) and then follows the session's locale.
 */
export default getRequestConfig(async () => {
  const cookie = (await cookies()).get(AGENT_LOCALE_COOKIE)?.value;
  const locale = isLocale(cookie) ? cookie : negotiateLocale((await headers()).get("accept-language"));
  return { locale, messages: MESSAGES[locale] };
});
