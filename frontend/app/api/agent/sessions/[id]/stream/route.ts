import { forwardAgent } from "@/lib/server/routes";

export const dynamic = "force-dynamic";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return forwardAgent(req, `/api/agent/sessions/${encodeURIComponent(id)}/stream`, { sse: true });
}
