import type { Metadata, Viewport } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale } from "next-intl/server";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Cover Assistant", template: "%s · Cover Assistant" },
  description: "AI insurance onboarding assistant",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

// The request's language (i18n/request.ts): the agent's cookie, else Accept-Language. The customer app
// switches to the session's own language once it loads.
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
