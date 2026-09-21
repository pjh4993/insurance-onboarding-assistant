import type { Metadata } from "next";
import "./agent.css";

export const metadata: Metadata = { title: "Agent console", robots: { index: false } };

export default function AgentLayout({ children }: { children: React.ReactNode }) {
  return <div className="agent-shell">{children}</div>;
}
