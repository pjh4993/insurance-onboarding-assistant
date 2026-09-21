import { forwardAgent } from "@/lib/server/routes";

export const dynamic = "force-dynamic";

export function GET(req: Request) {
  return forwardAgent(req, "/api/agent/sessions");
}
