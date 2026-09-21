import type { Metadata } from "next";
import "./customer.css";

export const metadata: Metadata = { title: "Your cover", referrer: "no-referrer", robots: { index: false } };

export default function CustomerLayout({ children }: { children: React.ReactNode }) {
  return <div className="customer-shell">{children}</div>;
}
