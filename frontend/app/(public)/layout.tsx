import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import "../s/customer.css";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("customer");
  return { title: t("title") };
}

// Public customer pages (/ and /chat): the same look as the session-link app under /s.
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return <div className="customer-shell">{children}</div>;
}
