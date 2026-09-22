import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale } from "next-intl/server";
// Pretendard (OFL-1.1) in unicode-range slices, so a page downloads only the Hangul it shows.
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./globals.css";

// Code and token values, shared with the docs site. Exposed as --font-plex-mono for globals.css.
const plexMono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-plex-mono" });

export const metadata: Metadata = {
  title: { default: "Cover Assistant", template: "%s · Cover Assistant" },
  description: "AI insurance onboarding assistant",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0f0f0f" },
  ],
};

// The request's language (i18n/request.ts): the agent's cookie, else Accept-Language. The customer app
// switches to the session's own language once it loads.
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  return (
    <html lang={locale} className={plexMono.variable}>
      <body>
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
