import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import "./agent.css";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("agent");
  return { title: t("title"), robots: { index: false } };
}

// The agent's own language comes from the agent_locale cookie via i18n/request.ts and the root provider.
export default function AgentLayout({ children }: { children: React.ReactNode }) {
  return <div className="agent-shell">{children}</div>;
}
