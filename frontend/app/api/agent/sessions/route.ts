import { forwardAgent } from "@/lib/server/routes";

export const dynamic = "force-dynamic";

export function GET(req: Request) {
  return forwardAgent(req, "/api/agent/sessions");
}

// Session creation lives under /api/agent/* so the ALB's Cognito rule covers it.
export function POST(req: Request) {
  return forwardAgent(req, "/api/sessions");
}
