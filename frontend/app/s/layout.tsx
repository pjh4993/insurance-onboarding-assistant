import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import "./customer.css";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("customer");
  return { title: t("title"), referrer: "no-referrer", robots: { index: false } };
}

export default function CustomerLayout({ children }: { children: React.ReactNode }) {
  return <div className="customer-shell">{children}</div>;
}
