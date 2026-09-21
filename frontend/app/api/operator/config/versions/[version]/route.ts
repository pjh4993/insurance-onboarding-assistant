import { forwardOperator } from "@/lib/server/routes";

export const dynamic = "force-dynamic";

export async function GET(req: Request, ctx: { params: Promise<{ version: string }> }) {
  const { version } = await ctx.params;
  return forwardOperator(req, `/api/operator/config/versions/${encodeURIComponent(version)}`);
}
