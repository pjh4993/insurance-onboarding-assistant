import type { Metadata } from "next";
import "./operator.css";

export const metadata: Metadata = { title: "Operator console", robots: { index: false } };

// The operator console is an internal tool in English; the agent's own copy is edited in every language.
export default function OperatorLayout({ children }: { children: React.ReactNode }) {
  return <div className="op-shell">{children}</div>;
}
