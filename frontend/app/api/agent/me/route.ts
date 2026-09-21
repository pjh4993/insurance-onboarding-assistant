import { resolveAgentId } from "@/lib/server/agentAuth";

export const dynamic = "force-dynamic";

// Frontend-only: tells the console who "me" is (for "Assign to me"). Not a backend endpoint.
export function GET(req: Request) {
  const agentId = resolveAgentId(req.headers);
  if (!agentId) return Response.json({ error: "Agent sign-in required" }, { status: 401 });
  return Response.json({ agent_id: agentId });
}
