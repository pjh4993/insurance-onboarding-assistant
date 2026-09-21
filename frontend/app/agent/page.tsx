import { AgentConsole } from "@/components/agent/AgentConsole";
import { customerBaseUrl } from "@/lib/server/config";

export const dynamic = "force-dynamic";

// Read at request time (not NEXT_PUBLIC_*), so one image serves every environment.
export default function AgentPage() {
  return <AgentConsole customerBaseUrl={customerBaseUrl()} />;
}
