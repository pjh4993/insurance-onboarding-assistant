import { forwardAgent } from "@/lib/server/routes";

export const dynamic = "force-dynamic";

// Creating a session link is an agent action in this UI, so it carries the agent identity.
export function POST(req: Request) {
  return forwardAgent(req, "/api/sessions");
}
